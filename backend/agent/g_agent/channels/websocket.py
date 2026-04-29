"""Local WebSocket channel for the first-party control room."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from aiohttp import WSMsgType, web

from g_agent.bus.events import OutboundMessage
from g_agent.bus.queue import MessageBus
from g_agent.channels.base import BaseChannel
from g_agent.channels.capabilities import ChannelCapabilities
from g_agent.config.schema import WebSocketChannelConfig


WEBSOCKET_CAPABILITIES = ChannelCapabilities(
    supports_media_send=True,
    supports_media_receive=True,
    supports_threads=True,
    max_text_chars=32000,
    media_types=("image", "audio", "video", "document"),
)


class WebSocketChannel(BaseChannel):
    """A local WebSocket channel that bridges browser clients to the bus."""

    name = "websocket"
    capabilities = WEBSOCKET_CAPABILITIES

    def __init__(self, config: WebSocketChannelConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: WebSocketChannelConfig = config
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        self._stop_event = asyncio.Event()
        self._clients: dict[str, set[web.WebSocketResponse]] = {}

    def make_app(self) -> web.Application:
        """Build the aiohttp app used by the channel server."""
        app = web.Application()
        app.router.add_get(self.config.path, self._handle_ws)
        return app

    async def start(self) -> None:
        """Start the local WebSocket server."""
        self._stop_event = asyncio.Event()
        self._runner = web.AppRunner(self.make_app())
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.config.host, self.config.port)
        await self._site.start()
        self._running = True
        await self._stop_event.wait()

    async def stop(self) -> None:
        """Stop the local WebSocket server and close clients."""
        self._running = False
        self._stop_event.set()
        for clients in list(self._clients.values()):
            for client in list(clients):
                await client.close()
        self._clients.clear()
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
            self._site = None

    async def send(self, msg: OutboundMessage) -> None:
        """Send an outbound message to connected WebSocket clients."""
        clients = self._clients.get(msg.chat_id, set())
        if not clients:
            raise RuntimeError(f"WebSocket chat {msg.chat_id} is not connected")
        payload = {
            "type": "message",
            "channel": self.name,
            "chat_id": msg.chat_id,
            "content": msg.content,
            "reply_to": msg.reply_to,
            "media": list(msg.media),
            "metadata": dict(msg.metadata or {}),
        }
        stale: list[web.WebSocketResponse] = []
        for client in clients:
            if client.closed:
                stale.append(client)
                continue
            await client.send_json(payload)
        for client in stale:
            clients.discard(client)

    async def _handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        self._check_auth(request)
        chat_id = request.query.get("chat_id") or "web"
        sender_id = request.query.get("sender_id") or chat_id
        websocket = web.WebSocketResponse(heartbeat=30)
        await websocket.prepare(request)
        self._clients.setdefault(chat_id, set()).add(websocket)
        await websocket.send_json({"type": "ready", "channel": self.name, "chat_id": chat_id})

        try:
            async for message in websocket:
                if message.type == WSMsgType.TEXT:
                    try:
                        payload = json.loads(message.data)
                    except json.JSONDecodeError:
                        await websocket.send_json(
                            {"type": "error", "code": "invalid_json", "message": "invalid JSON"}
                        )
                        continue
                    await self._handle_client_payload(
                        sender_id=sender_id,
                        chat_id=chat_id,
                        payload=payload,
                    )
                elif message.type == WSMsgType.ERROR:
                    break
        finally:
            self._clients.get(chat_id, set()).discard(websocket)
        return websocket

    def _check_auth(self, request: web.Request) -> None:
        if not self.config.token:
            return
        header = request.headers.get("Authorization", "")
        token = request.query.get("token") or request.headers.get("X-G-Agent-Token", "")
        if header.startswith("Bearer "):
            token = header.removeprefix("Bearer ").strip()
        if token != self.config.token:
            raise web.HTTPUnauthorized(text="valid WebSocket token required")

    async def _handle_client_payload(
        self,
        *,
        sender_id: str,
        chat_id: str,
        payload: Any,
    ) -> None:
        if not isinstance(payload, dict):
            return
        content = str(payload.get("content") or "")
        media = payload.get("media") if isinstance(payload.get("media"), list) else []
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        await self._handle_message(
            sender_id=sender_id,
            chat_id=chat_id,
            content=content,
            media=[str(item) for item in media],
            metadata={"transport": "websocket", **metadata},
        )
