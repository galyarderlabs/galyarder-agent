"""Message tool for sending messages to users."""

import shutil
import subprocess
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from g_agent.agent.tools.base import Tool
from g_agent.bus.events import OutboundMessage


def _infer_media_type(media_path: str, explicit_type: str | None = None) -> str:
    media_type = (explicit_type or "").strip().lower()
    if media_type in {"image", "voice", "audio", "document", "sticker"}:
        return media_type
    suffix = Path(media_path).suffix.lower()
    if suffix in {".webp", ".tgs"}:
        return "sticker"
    if suffix in {".jpg", ".jpeg", ".png", ".gif"}:
        return "image"
    if suffix in {".ogg", ".opus"}:
        return "voice"
    if suffix in {".mp3", ".m4a", ".wav", ".flac"}:
        return "audio"
    return "document"


class MessageTool(Tool):
    """Tool to send messages to users on chat channels."""

    def __init__(
        self,
        send_callback: Callable[[OutboundMessage], Awaitable[None]] | None = None,
        default_channel: str = "",
        default_chat_id: str = "",
        workspace: Path | None = None,
    ):
        self._send_callback = send_callback
        self._default_channel = default_channel
        self._default_chat_id = default_chat_id
        self._workspace = workspace.expanduser().resolve() if workspace else None

    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the current message context."""
        self._default_channel = channel
        self._default_chat_id = chat_id

    def set_send_callback(self, callback: Callable[[OutboundMessage], Awaitable[None]]) -> None:
        """Set the callback for sending messages."""
        self._send_callback = callback

    @property
    def name(self) -> str:
        return "message"

    @property
    def description(self) -> str:
        return (
            "Send a message to the user. Supports plain text or media payloads "
            "(image/voice/audio/sticker/document)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The message content to send"},
                "channel": {
                    "type": "string",
                    "description": "Optional: target channel (telegram, discord, etc.)",
                },
                "chat_id": {"type": "string", "description": "Optional: target chat/user ID"},
                "media_path": {
                    "type": "string",
                    "description": "Optional local file path for media payload.",
                },
                "media_type": {
                    "type": "string",
                    "enum": ["image", "voice", "audio", "sticker", "document"],
                    "description": "Optional media type. If omitted, inferred from file extension.",
                },
                "mime_type": {
                    "type": "string",
                    "description": "Optional MIME type for media payload.",
                },
                "caption": {
                    "type": "string",
                    "description": "Optional caption (defaults to content when present).",
                },
            },
            "required": [],
        }

    async def execute(
        self,
        content: str | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
        media_path: str | None = None,
        media_type: str | None = None,
        mime_type: str | None = None,
        caption: str | None = None,
        **kwargs: Any,
    ) -> str:
        content_text = (content or "").strip()
        media_path_text = (media_path or "").strip()
        caption_text = (caption or "").strip()
        mime_text = (mime_type or "").strip()
        requested_media_type = (media_type or "").strip().lower()

        if not content_text and not media_path_text:
            return "Error: either content or media_path is required"

        if media_path_text:
            file_path = Path(media_path_text).expanduser()
            if not file_path.exists() or not file_path.is_file():
                return f"Error: media_path not found: {media_path_text}"
            media_path_text = str(file_path.resolve())
            resolved_media_type = _infer_media_type(media_path_text, media_type)
        else:
            resolved_media_type = ""
            if requested_media_type in {"voice", "audio"} and content_text:
                generated = self._synthesize_speech(content_text, requested_media_type)
                if generated:
                    media_path_text = generated
                    resolved_media_type = requested_media_type
                    if not mime_text:
                        mime_text = "audio/ogg" if requested_media_type == "voice" else "audio/wav"
                else:
                    return (
                        "Error: voice synthesis unavailable. Install espeak-ng/espeak "
                        "or provide media_path explicitly."
                    )
            elif requested_media_type == "image" and content_text:
                generated = self._render_image_card(content_text)
                if generated:
                    media_path_text = generated
                    resolved_media_type = "image"
                    if not mime_text:
                        mime_text = "image/png"
                else:
                    return (
                        "Error: image card generation unavailable. Install ImageMagick (`magick`) "
                        "or provide media_path explicitly."
                    )
            elif requested_media_type == "sticker" and content_text:
                generated = self._render_sticker_card(content_text)
                if generated:
                    media_path_text = generated
                    resolved_media_type = "sticker"
                    if not mime_text:
                        mime_text = "image/webp"
                else:
                    return (
                        "Error: sticker generation unavailable. Install ImageMagick (`magick`) "
                        "or provide media_path explicitly."
                    )
        channel = channel or self._default_channel
        chat_id = chat_id or self._default_chat_id

        if not channel or not chat_id:
            return "Error: No target channel/chat specified"

        if not self._send_callback:
            return "Error: Message sending not configured"

        metadata: dict[str, Any] = {}
        media_items: list[str] = []
        if media_path_text:
            media_items.append(media_path_text)
            metadata["media_type"] = resolved_media_type
            if mime_text:
                metadata["mime_type"] = mime_text
            caption_value = caption_text
            if resolved_media_type != "sticker" and not caption_value:
                caption_value = content_text
            if caption_value:
                metadata["caption"] = caption_value
        elif caption_text:
            metadata["caption"] = caption_text

        msg = OutboundMessage(
            channel=channel,
            chat_id=chat_id,
            content=content_text,
            media=media_items,
            metadata=metadata,
        )

        try:
            await self._send_callback(msg)
            if media_items:
                return f"Message sent to {channel}:{chat_id} ({resolved_media_type})"
            return f"Message sent to {channel}:{chat_id}"
        except Exception as e:
            return f"Error sending message: {str(e)}"

    def _synthesize_speech(self, text: str, media_type: str) -> str | None:
        """Best-effort local TTS using espeak/espeak-ng (+ optional ffmpeg conversion)."""
        engine = shutil.which("espeak-ng") or shutil.which("espeak")
        if not engine:
            return None

        target_dir = (
            self._workspace / "state" / "tts"
            if self._workspace
            else Path.home() / ".g-agent" / "workspace" / "state" / "tts"
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        stem = datetime.now().strftime("tts-%Y%m%d-%H%M%S-%f")
        wav_path = target_dir / f"{stem}.wav"
        try:
            subprocess.run(
                [engine, "-w", str(wav_path), text],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except (OSError, subprocess.SubprocessError):
            return None

        if media_type == "voice":
            ffmpeg = shutil.which("ffmpeg")
            if ffmpeg:
                ogg_path = target_dir / f"{stem}.ogg"
                try:
                    subprocess.run(
                        [
                            ffmpeg,
                            "-y",
                            "-i",
                            str(wav_path),
                            "-c:a",
                            "libopus",
                            "-b:a",
                            "48k",
                            str(ogg_path),
                        ],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    if ogg_path.exists():
                        return str(ogg_path.resolve())
                except (OSError, subprocess.SubprocessError):
                    return str(wav_path.resolve()) if wav_path.exists() else None
        return str(wav_path.resolve()) if wav_path.exists() else None

    def _render_image_card(self, text: str) -> str | None:
        """Best-effort image card rendering using ImageMagick."""
        magick = shutil.which("magick") or shutil.which("convert")
        if not magick:
            return None

        target_dir = (
            self._workspace / "state" / "cards"
            if self._workspace
            else Path.home() / ".g-agent" / "workspace" / "state" / "cards"
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        stem = datetime.now().strftime("card-%Y%m%d-%H%M%S-%f")
        output_path = target_dir / f"{stem}.png"
        wrapped = "\n".join(textwrap.wrap((text or "").strip(), width=56))[:3500]
        if not wrapped:
            wrapped = "g-agent summary"

        command = [
            magick,
            "-size",
            "1280x720",
            "xc:#0f172a",
            "-fill",
            "#f8fafc",
            "-pointsize",
            "44",
            "-gravity",
            "northwest",
            "-annotate",
            "+64+64",
            "G-AGENT BRIEF",
            "-fill",
            "#cbd5e1",
            "-pointsize",
            "30",
            "-gravity",
            "northwest",
            "-annotate",
            "+64+150",
            wrapped,
            str(output_path),
        ]
        try:
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return str(output_path.resolve()) if output_path.exists() else None

    def _render_sticker_card(self, text: str) -> str | None:
        """Best-effort sticker-style WEBP rendering using ImageMagick."""
        magick = shutil.which("magick") or shutil.which("convert")
        if not magick:
            return None

        target_dir = (
            self._workspace / "state" / "stickers"
            if self._workspace
            else Path.home() / ".g-agent" / "workspace" / "state" / "stickers"
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        stem = datetime.now().strftime("sticker-%Y%m%d-%H%M%S-%f")
        output_path = target_dir / f"{stem}.webp"
        wrapped = "\n".join(textwrap.wrap((text or "").strip(), width=18))[:1200]
        if not wrapped:
            wrapped = "g-agent"

        command = [
            magick,
            "-size",
            "512x512",
            "xc:none",
            "-fill",
            "#ffffff",
            "-stroke",
            "#111827",
            "-strokewidth",
            "1",
            "-pointsize",
            "42",
            "-gravity",
            "center",
            "-annotate",
            "+0+0",
            wrapped,
            str(output_path),
        ]
        try:
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return str(output_path.resolve()) if output_path.exists() else None
