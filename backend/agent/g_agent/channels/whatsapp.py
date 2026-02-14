"""WhatsApp channel implementation using Node.js bridge."""

import asyncio
import json
from pathlib import Path

from loguru import logger

from g_agent.bus.events import OutboundMessage
from g_agent.bus.queue import MessageBus
from g_agent.channels.base import BaseChannel
from g_agent.config.schema import WhatsAppConfig
from g_agent.providers.transcription import GroqTranscriptionProvider


class WhatsAppChannel(BaseChannel):
    """
    WhatsApp channel that connects to a Node.js bridge.

    The bridge uses @whiskeysockets/baileys to handle the WhatsApp Web protocol.
    Communication between Python and Node.js is via WebSocket.
    """

    name = "whatsapp"

    def __init__(self, config: WhatsAppConfig, bus: MessageBus, groq_api_key: str = ""):
        super().__init__(config, bus)
        self.config: WhatsAppConfig = config
        self.groq_api_key = groq_api_key
        self._ws = None
        self._connected = False

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
                        await ws.send(json.dumps({"type": "auth", "token": self.config.bridge_token}))
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
                logger.warning(f"WhatsApp bridge connection error: {e}")

                if self._running:
                    logger.info("Reconnecting in 5 seconds...")
                    await asyncio.sleep(5)

    async def stop(self) -> None:
        """Stop the WhatsApp channel."""
        self._running = False
        self._connected = False

        if self._ws:
            await self._ws.close()
            self._ws = None

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through WhatsApp."""
        if not self._ws or not self._connected:
            raise RuntimeError("WhatsApp bridge not connected")

        try:
            metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
            media_items = msg.media if isinstance(msg.media, list) else []
            media_path = ""
            if media_items:
                media_path = str(media_items[0]).strip()
                if media_path:
                    path_obj = Path(media_path).expanduser()
                    if not path_obj.exists() or not path_obj.is_file():
                        logger.warning(f"WhatsApp outbound media not found: {media_path}")
                        media_path = ""
                    else:
                        media_path = str(path_obj.resolve())

            payload = {
                "type": "send",
                "to": msg.chat_id,
                "text": msg.content,
            }
            if media_path:
                payload["mediaPath"] = media_path
                payload["mediaType"] = str(metadata.get("media_type", "")).strip()
                payload["mimeType"] = str(metadata.get("mime_type", "")).strip()
                payload["caption"] = str(metadata.get("caption", "")).strip() or msg.content
            await self._ws.send(json.dumps(payload))
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {e}")

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
            is_audio_payload = normalized_media_type in {"voice", "audio"} or normalized_mime_type.startswith(
                "audio/"
            )

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

        elif msg_type == "status":
            # Connection status update
            status = data.get("status")
            logger.info(f"WhatsApp status: {status}")

            if status == "connected":
                self._connected = True
            elif status == "disconnected":
                self._connected = False

        elif msg_type == "qr":
            # QR code for authentication
            logger.info("Scan QR code in the bridge terminal to connect WhatsApp")

        elif msg_type == "error":
            logger.error(f"WhatsApp bridge error: {data.get('error')}")

    def _jid_to_identity(self, jid: str) -> str:
        """Convert JID into stable sender identity for allowlist checks."""
        value = (jid or "").strip()
        if not value:
            return ""
        left = value.split("@", 1)[0]
        if ":" in left:
            left = left.split(":", 1)[0]
        return left
