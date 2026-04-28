"""WhatsApp channel implementation using Node.js bridge."""

import asyncio
import json
from pathlib import Path

from loguru import logger

from g_agent.bus.events import OutboundMessage
from g_agent.bus.queue import MessageBus
from g_agent.channels.base import BaseChannel
from g_agent.channels.capabilities import WHATSAPP_CAPABILITIES
from g_agent.config.schema import WhatsAppConfig
from g_agent.providers.transcription import GroqTranscriptionProvider


class WhatsAppChannel(BaseChannel):
    """
    WhatsApp channel that connects to a Node.js bridge.

    The bridge uses @whiskeysockets/baileys to handle the WhatsApp Web protocol.
    Communication between Python and Node.js is via WebSocket.
    """

    name = "whatsapp"
    capabilities = WHATSAPP_CAPABILITIES

    def __init__(self, config: WhatsAppConfig, bus: MessageBus, groq_api_key: str = ""):
        super().__init__(config, bus)
        self.config: WhatsAppConfig = config
        self.groq_api_key = groq_api_key
        self._ws = None
        self._connected = False
        self._request_seq = 0
        self._ack_timeout_s = 15.0
        self._pending_send_acks: dict[str, asyncio.Future[dict]] = {}

    async def start(self) -> None:
        """Start the WhatsApp channel by connecting to the bridge."""
        import websockets

        bridge_url = self.config.bridge_url

        logger.info(f"Connecting to WhatsApp bridge at {bridge_url}...")

        self._running = True

        while self._running:
            try:
                async with websockets.connect(bridge_url) as ws:
                    self._ws = ws
                    self._connected = True
                    logger.info("Connected to WhatsApp bridge")

                    if self.config.bridge_token:
                        await ws.send(
                            json.dumps({"type": "auth", "token": self.config.bridge_token})
                        )
                        logger.info("Sent bridge auth token")

                    # Listen for messages
                    async for message in ws:
                        try:
                            await self._handle_bridge_message(message)
                        except Exception as e:
                            logger.error(f"Error handling bridge message: {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._connected = False
                self._ws = None
                self._fail_all_pending_acks(f"bridge connection error: {e}")
                logger.warning(f"WhatsApp bridge connection error: {e}")

                if self._running:
                    logger.info("Reconnecting in 5 seconds...")
                    await asyncio.sleep(5)

    async def stop(self) -> None:
        """Stop the WhatsApp channel."""
        self._running = False
        self._connected = False
        self._fail_all_pending_acks("channel stopping")

        if self._ws:
            await self._ws.close()
            self._ws = None

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through WhatsApp and wait for bridge ACK."""
        if not self._ws or not self._connected:
            raise RuntimeError("WhatsApp bridge not connected")

        metadata = msg.metadata if isinstance(msg.metadata, dict) else {}

        # Handle action commands (typing indicator) — fire-and-forget, no ACK needed
        action = str(metadata.get("action", "")).strip()
        if action:
            payload = {"type": "action", "to": msg.chat_id, "action": action}
            await self._ws.send(json.dumps(payload))
            return

        media_items = msg.media if isinstance(msg.media, list) else []
        media_path = ""
        if media_items:
            media_path = str(media_items[0]).strip()
            if media_path:
                path_obj = Path(media_path).expanduser()
                if not path_obj.exists() or not path_obj.is_file():
                    raise FileNotFoundError(f"WhatsApp outbound media not found: {media_path}")
                media_path = str(path_obj.resolve())
            else:
                raise FileNotFoundError(f"WhatsApp outbound media not found: {media_items[0]}")

        request_id = self._next_request_id()
        payload = {
            "type": "send",
            "to": msg.chat_id,
            "text": msg.content,
            "request_id": request_id,
        }
        if media_path:
            payload["mediaPath"] = media_path
            payload["mediaType"] = str(metadata.get("media_type", "")).strip()
            payload["mimeType"] = str(metadata.get("mime_type", "")).strip()
            payload["caption"] = str(metadata.get("caption", "")).strip() or msg.content

        logger.bind(
            request_id=request_id,
            chat_id=msg.chat_id,
            has_media=bool(media_path),
            media_path=media_path,
            media_type=payload.get("mediaType", ""),
        ).info("WhatsApp send request")

        try:
            await self._ws.send(json.dumps(payload))
            ack = await self._wait_for_send_ack(
                request_id=request_id, timeout_s=self._ack_timeout_s
            )
        except TimeoutError as e:
            logger.error(f"WhatsApp send ack timeout: request_id={request_id} error={e}")
            raise RuntimeError(str(e)) from e
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: request_id={request_id} error={e}")
            raise

        ack_type = str(ack.get("type", "")).strip().lower()
        if ack_type == "sent":
            logger.info(f"WhatsApp send ack received: request_id={request_id} status=sent")
            return

        error_text = str(ack.get("error", "bridge send failed")).strip() or "bridge send failed"
        category = str(ack.get("category", "send_error")).strip() or "send_error"
        logger.error(
            f"WhatsApp send ack error: request_id={request_id} category={category} error={error_text}"
        )
        raise RuntimeError(error_text)

    async def _handle_bridge_message(self, raw: str) -> None:
        """Handle a message from the bridge."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from bridge: {raw[:100]}")
            return

        msg_type = data.get("type")

        if msg_type == "message":
            # Incoming message from WhatsApp
            sender_jid = str(data.get("sender", ""))
            chat_jid = str(data.get("chatId", "") or sender_jid)
            sender_id = self._jid_to_identity(sender_jid or chat_jid)
            content = data.get("content", "")
            media_type = data.get("mediaType", "")
            media_path = data.get("mediaPath", "")
            mime_type = data.get("mimeType")
            caption = data.get("caption")
            media_paths: list[str] = []
            attachments: list[dict[str, str]] = []

            if media_path:
                path_obj = Path(str(media_path))
                if path_obj.exists() and path_obj.is_file():
                    media_paths.append(str(path_obj))
                    attachments.append(
                        {
                            "type": str(media_type or "file"),
                            "path": str(path_obj),
                            "mime": str(mime_type or ""),
                            "caption": str(caption or ""),
                            "sourceChannel": "whatsapp",
                        }
                    )
                else:
                    logger.warning(f"WhatsApp media path not found: {media_path}")

            normalized_media_type = str(media_type or "").strip().lower()
            normalized_mime_type = str(mime_type or "").strip().lower()
            is_audio_payload = normalized_media_type in {
                "voice",
                "audio",
            } or normalized_mime_type.startswith("audio/")

            # Handle audio transcription when an audio attachment is present.
            if is_audio_payload and media_paths:
                try:
                    transcriber = GroqTranscriptionProvider(api_key=self.groq_api_key or None)
                    transcription = await transcriber.transcribe(media_paths[0])
                    if transcription:
                        content = (
                            f"{content}\n[transcription: {transcription}]"
                            if content
                            else f"[transcription: {transcription}]"
                        )
                except Exception as e:
                    logger.warning(f"WhatsApp transcription failed: {e}")

            await self._handle_message(
                sender_id=sender_id,
                chat_id=chat_jid,  # Use full JID for replies
                content=content,
                media=media_paths,
                metadata={
                    "message_id": data.get("id"),
                    "timestamp": data.get("timestamp"),
                    "is_group": data.get("isGroup", False),
                    "from_me": bool(data.get("fromMe", False)),
                    "sender_jid": sender_jid,
                    "chat_jid": chat_jid,
                    "media_type": media_type,
                    "mime_type": mime_type,
                    "attachments": attachments,
                },
            )

        elif msg_type in {"sent", "error"}:
            request_id = str(data.get("request_id") or data.get("requestId") or "").strip()
            if request_id:
                future = self._pending_send_acks.pop(request_id, None)
                if future is None:
                    logger.warning(
                        f"WhatsApp bridge ack for unknown request_id={request_id}: {data}"
                    )
                    return
                if not future.done():
                    future.set_result(data)
                return

            if msg_type == "error":
                logger.error(f"WhatsApp bridge error: {data.get('error')}")
            else:
                # Expected for fire-and-forget actions (typing indicators)
                logger.debug(f"WhatsApp bridge sent ack without request_id: {data}")
            return

        elif msg_type == "status":
            # Connection status update
            status = data.get("status")
            logger.info(f"WhatsApp status: {status}")

            if status == "connected":
                self._connected = True
            elif status == "disconnected":
                self._connected = False
                self._fail_all_pending_acks("bridge disconnected")

        elif msg_type == "qr":
            # QR code for authentication
            logger.info("Scan QR code in the bridge terminal to connect WhatsApp")

    def _next_request_id(self) -> str:
        """Generate monotonic request id for bridge send correlation."""
        self._request_seq += 1
        return f"req-{self._request_seq}"

    async def _wait_for_send_ack(self, *, request_id: str, timeout_s: float) -> dict:
        """Wait for bridge sent/error ACK tied to request_id."""
        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict] = loop.create_future()
        self._pending_send_acks[request_id] = future
        try:
            return await asyncio.wait_for(future, timeout=timeout_s)
        except asyncio.TimeoutError as e:
            self._pending_send_acks.pop(request_id, None)
            raise TimeoutError(f"timeout waiting ack for request_id={request_id}") from e

    def _fail_all_pending_acks(self, reason: str) -> None:
        """Fail all pending ACK futures when bridge/session goes down."""
        if not self._pending_send_acks:
            return
        error = RuntimeError(reason)
        for future in list(self._pending_send_acks.values()):
            if not future.done():
                future.set_exception(error)
        self._pending_send_acks.clear()

    def _jid_to_identity(self, jid: str) -> str:
        """Convert JID into stable sender identity for allowlist checks."""
        value = (jid or "").strip()
        if not value:
            return ""
        left = value.split("@", 1)[0]
        if ":" in left:
            left = left.split(":", 1)[0]
        return left
