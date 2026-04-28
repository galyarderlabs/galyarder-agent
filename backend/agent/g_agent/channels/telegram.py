"""Telegram channel implementation using python-telegram-bot."""

from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from g_agent.bus.events import OutboundMessage
from g_agent.bus.queue import MessageBus
from g_agent.channels.base import BaseChannel
from g_agent.channels.slash_commands import SlashCommandDispatcher
from g_agent.config.schema import TelegramConfig

if TYPE_CHECKING:
    from g_agent.cron.service import CronService


def _markdown_to_telegram_html(text: str) -> str:
    """
    Convert markdown to Telegram-safe HTML.
    """
    if not text:
        return ""

    # 1. Extract and protect code blocks (preserve content from other processing)
    code_blocks: list[str] = []

    def save_code_block(m: re.Match) -> str:
        code_blocks.append(m.group(1))
        return f"\x00CB{len(code_blocks) - 1}\x00"

    text = re.sub(r"```[\w]*\n?([\s\S]*?)```", save_code_block, text)

    # 2. Extract and protect inline code
    inline_codes: list[str] = []

    def save_inline_code(m: re.Match) -> str:
        inline_codes.append(m.group(1))
        return f"\x00IC{len(inline_codes) - 1}\x00"

    text = re.sub(r"`([^`]+)`", save_inline_code, text)

    # 3. Headers # Title -> just the title text
    text = re.sub(r"^#{1,6}\s+(.+)$", r"\1", text, flags=re.MULTILINE)

    # 4. Blockquotes > text -> just the text (before HTML escaping)
    text = re.sub(r"^>\s*(.*)$", r"\1", text, flags=re.MULTILINE)

    # 5. Escape HTML special characters
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # 6. Links [text](url) - must be before bold/italic to handle nested cases
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)

    # 7. Bold **text** or __text__
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)

    # 8. Italic _text_ (avoid matching inside words like some_var_name)
    text = re.sub(r"(?<![a-zA-Z0-9])_([^_]+)_(?![a-zA-Z0-9])", r"<i>\1</i>", text)

    # 9. Strikethrough ~~text~~
    text = re.sub(r"~~(.+?)~~", r"<s>\1</s>", text)

    # 10. Bullet lists - item -> • item
    text = re.sub(r"^[-*]\s+", "• ", text, flags=re.MULTILINE)

    # 11. Restore inline code with HTML tags
    for i, code in enumerate(inline_codes):
        # Escape HTML in code content
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00IC{i}\x00", f"<code>{escaped}</code>")

    # 12. Restore code blocks with HTML tags
    for i, code in enumerate(code_blocks):
        # Escape HTML in code content
        escaped = code.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = text.replace(f"\x00CB{i}\x00", f"<pre><code>{escaped}</code></pre>")

    return text


class TelegramChannel(BaseChannel):
    """
    Telegram channel using long polling.

    Simple and reliable - no webhook/public IP needed.
    """

    name = "telegram"

    def __init__(
        self,
        config: TelegramConfig,
        bus: MessageBus,
        groq_api_key: str = "",
        *,
        workspace: Path | None = None,
        model_name: str = "",
        brave_api_key: str = "",
        cron_service: CronService | None = None,
        tool_names: list[str] | None = None,
    ):
        super().__init__(config, bus)
        self.config: TelegramConfig = config
        self.groq_api_key = groq_api_key
        self._app: Application | None = None
        self._chat_ids: dict[str, int] = {}  # Map sender_id to chat_id for replies

        # Slash command dispatcher (instant responses, no LLM)
        self._slash: SlashCommandDispatcher | None = None
        if workspace:
            self._slash = SlashCommandDispatcher(
                workspace,
                model_name=model_name,
                brave_api_key=brave_api_key,
                cron_service=cron_service,
                tool_names=tool_names or [],
                version=os.environ.get("G_AGENT_VERSION", "dev"),
            )

    async def start(self) -> None:
        """Start the Telegram bot with long polling."""
        if not self.config.token:
            logger.error("Telegram bot token not configured")
            return

        self._running = True

        while self._running:
            try:
                # Build the application with more resilient network settings
                builder = (
                    Application.builder()
                    .token(self.config.token)
                    .connect_timeout(20.0)
                    .read_timeout(30.0)
                    .write_timeout(30.0)
                    .pool_timeout(30.0)
                    .get_updates_connect_timeout(20.0)
                    .get_updates_read_timeout(30.0)
                    .get_updates_write_timeout(30.0)
                    .get_updates_pool_timeout(30.0)
                )

                if self.config.proxy:
                    builder = builder.proxy(self.config.proxy).get_updates_proxy(self.config.proxy)

                self._app = builder.build()

                from telegram.ext import CallbackQueryHandler

                # Add message handler for text, photos, voice, documents
                self._app.add_handler(
                    MessageHandler(
                        (
                            filters.TEXT
                            | filters.PHOTO
                            | filters.VOICE
                            | filters.AUDIO
                            | filters.Document.ALL
                            | filters.Sticker.ALL
                        ),
                        self._on_message,
                    )
                )
                self._app.add_handler(CallbackQueryHandler(self._handle_callback_query))

                logger.info("Starting Telegram bot (polling mode)...")

                # Initialize and start polling
                await self._app.initialize()
                await self._app.start()

                # Get bot info
                bot_info = await self._app.bot.get_me()
                logger.info(f"Telegram bot @{bot_info.username} connected")

                # Auto-register bot commands in Telegram UI
                from telegram import BotCommand

                await self._app.bot.set_my_commands(
                    [
                        BotCommand("start", "Start conversation"),
                        BotCommand("new", "New session"),
                        BotCommand("reset", "Clear context & start fresh"),
                        BotCommand("compact", "Summarize current session"),
                        BotCommand("context", "Current session info"),
                        BotCommand("status", "System diagnostics"),
                        BotCommand("whoami", "Your profile"),
                        BotCommand("memory", "View stored memories"),
                        BotCommand("model", "Active model"),
                        BotCommand("tools", "List active tools"),
                        BotCommand("cron", "Scheduled jobs"),
                        BotCommand("packs", "Workflow packs"),
                        BotCommand("search", "Web search"),
                        BotCommand("help", "Commands & guide"),
                        BotCommand("commands", "Full command list"),
                    ]
                )

                # Start polling (this runs until stopped)
                await self._app.updater.start_polling(
                    allowed_updates=["message", "callback_query"],
                    drop_pending_updates=True,  # Ignore old messages on startup
                )

                # Keep running until stopped
                while self._running:
                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Telegram channel error: {e}")
                if self._app:
                    try:
                        if self._app.updater:
                            await self._app.updater.stop()
                        await self._app.stop()
                        await self._app.shutdown()
                    except Exception as cleanup_error:
                        logger.debug(f"Telegram cleanup after error failed: {cleanup_error}")
                    self._app = None
                if self._running:
                    logger.info("Retrying Telegram connection in 5 seconds...")
                    await asyncio.sleep(5)

    async def stop(self) -> None:
        """Stop the Telegram bot."""
        self._running = False

        if self._app:
            logger.info("Stopping Telegram bot...")
            if self._app.updater:
                await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            self._app = None

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Telegram."""
        if not self._app:
            raise RuntimeError("Telegram bot not running")

        try:
            # chat_id should be the Telegram chat ID (integer)
            chat_id = int(msg.chat_id)

            # Handle action commands (typing indicator) — early return
            tg_metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
            tg_action = str(tg_metadata.get("action", "")).strip()
            if tg_action == "typing":
                from telegram.constants import ChatAction

                await self._app.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
                return

            reply_to_message_id = None
            if self.config.reply_to_message and msg.reply_to:
                try:
                    reply_to_message_id = int(msg.reply_to)
                except ValueError:
                    pass

            media = self._resolve_outbound_media(msg)
            if media:
                path, media_type, caption = media
                with open(path, "rb") as media_file:
                    if media_type == "image":
                        await self._app.bot.send_photo(
                            chat_id=chat_id,
                            photo=media_file,
                            caption=caption or None,
                            reply_to_message_id=reply_to_message_id,
                        )
                    elif media_type == "voice":
                        await self._app.bot.send_voice(
                            chat_id=chat_id,
                            voice=media_file,
                            caption=caption or None,
                            reply_to_message_id=reply_to_message_id,
                        )
                    elif media_type == "audio":
                        await self._app.bot.send_audio(
                            chat_id=chat_id,
                            audio=media_file,
                            caption=caption or None,
                            reply_to_message_id=reply_to_message_id,
                        )
                    elif media_type == "sticker":
                        await self._app.bot.send_sticker(
                            chat_id=chat_id,
                            sticker=media_file,
                            reply_to_message_id=reply_to_message_id,
                        )
                        if caption:
                            await self._app.bot.send_message(
                                chat_id=chat_id,
                                text=caption,
                                reply_to_message_id=reply_to_message_id,
                            )
                    else:
                        await self._app.bot.send_document(
                            chat_id=chat_id,
                            document=media_file,
                            caption=caption or None,
                            reply_to_message_id=reply_to_message_id,
                        )
                return

            # Convert markdown to Telegram HTML
            html_content = _markdown_to_telegram_html(msg.content)
            await self._app.bot.send_message(
                chat_id=chat_id,
                text=html_content,
                parse_mode="HTML",
                reply_to_message_id=reply_to_message_id,
            )
        except ValueError:
            logger.error(f"Invalid chat_id: {msg.chat_id}")
            raise
        except Exception as e:
            # Fallback to plain text if HTML parsing fails
            logger.warning(f"HTML parse failed, falling back to plain text: {e}")
            try:
                await self._app.bot.send_message(chat_id=int(msg.chat_id), text=msg.content)
            except Exception as e2:
                logger.error(f"Error sending Telegram message: {e2}")
                raise

    def _resolve_outbound_media(self, msg: OutboundMessage) -> tuple[Path, str, str] | None:
        """Resolve outbound media tuple (path, type, caption)."""
        metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
        media_items = msg.media if isinstance(msg.media, list) else []
        if not media_items:
            return None
        raw_path = str(media_items[0]).strip()
        if not raw_path:
            return None

        path = Path(raw_path).expanduser()
        if not path.exists() or not path.is_file():
            logger.error(f"Telegram outbound media not found: {raw_path}")
            raise FileNotFoundError(f"Telegram outbound media not found: {raw_path}")

        media_type = str(metadata.get("media_type", "")).strip().lower()
        if media_type not in {"image", "voice", "audio", "sticker", "document"}:
            suffix = path.suffix.lower()
            if suffix in {".jpg", ".jpeg", ".png", ".gif"}:
                media_type = "image"
            elif suffix in {".ogg", ".opus"}:
                media_type = "voice"
            elif suffix in {".mp3", ".m4a", ".wav", ".flac"}:
                media_type = "audio"
            elif suffix in {".webp", ".tgs"}:
                media_type = "sticker"
            else:
                media_type = "document"

        caption = str(metadata.get("caption", "")).strip() or (msg.content or "").strip()
        if media_type == "sticker":
            caption = caption[:4000]
        else:
            caption = caption[:1024]
        return path, media_type, caption

    async def _handle_callback_query(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle inline button clicks for slash commands."""
        query = update.callback_query
        if not query or not query.data:
            return

        await query.answer()

        user = update.effective_user
        if not user:
            logger.warning("Callback query without effective_user, ignoring")
            return

        sender_id = str(user.id)
        if user.username:
            sender_id = f"{sender_id}|{user.username}"

        chat_id = query.message.chat_id if query.message else None
        if not chat_id:
            logger.warning("Callback query without chat_id, ignoring")
            return

        session_key = f"telegram:{chat_id}"

        if not (query.data.startswith("/") and self._slash):
            return

        # Bypass LLM and route to slash command handler
        raw_cmd = query.data.strip().split(maxsplit=1)[0][1:].lower()
        allowed_commands = ["start", "help"]
        if not self.is_allowed(sender_id) and raw_cmd not in allowed_commands:
            response: str | dict | None = (
                "⛔ <b>Access denied:</b> <i>you are not authorized to use commands.</i>"
            )
        else:
            try:
                response = self._slash.try_handle(
                    query.data,
                    session_key,
                    "telegram",
                    str(chat_id),
                    sender_username=user.username or "",
                    sender_id=sender_id,
                )
            except Exception as e:
                logger.error(f"Callback slash command failed: {e}")
                response = f"⚠️ Error: {e}"

        if response is None:
            return

        text: str = response if isinstance(response, str) else response.get("text", "")
        reply_markup = None
        if isinstance(response, dict):
            buttons = response.get("buttons")
            if buttons:
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup

                kb = []
                for row in buttons:
                    kb_row = []
                    for btn in row:
                        kb_row.append(
                            InlineKeyboardButton(text=btn["text"], callback_data=btn["data"])
                        )
                    kb.append(kb_row)
                reply_markup = InlineKeyboardMarkup(kb)

        # Try editing the original message first; fall back to new message
        try:
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=reply_markup)
        except Exception as edit_err:
            if "Message is not modified" not in str(edit_err):
                logger.warning(f"edit_message_text failed ({edit_err}), sending new message")
                try:
                    await self._app.bot.send_message(
                        chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=reply_markup
                    )
                except Exception as send_err:
                    logger.error(f"Fallback send_message also failed: {send_err}")

    async def _on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle incoming messages (text, photos, voice, documents)."""
        if not update.message or not update.effective_user:
            return

        message = update.message
        user = update.effective_user
        chat_id = message.chat_id

        # Use stable numeric ID, but keep username for allowlist compatibility
        sender_id = str(user.id)
        if user.username:
            sender_id = f"{sender_id}|{user.username}"

        # Store chat_id for replies
        self._chat_ids[sender_id] = chat_id

        # Intercept slash commands — instant response, bypass LLM
        if self._slash and message.text and message.text.strip().startswith("/"):
            raw_cmd = message.text.strip().split(maxsplit=1)[0][1:].lower()

            # Security gate: only allow list can use most commands
            allowed_commands = ["start", "help"]
            if not self.is_allowed(sender_id) and raw_cmd not in allowed_commands:
                response = "⛔ Access denied: you are not authorized to use commands."
            else:
                session_key = f"telegram:{chat_id}"
                response = self._slash.try_handle(
                    message.text,
                    session_key,
                    "telegram",
                    str(chat_id),
                    sender_username=user.username or "",
                    sender_id=sender_id,
                )

            if response is not None:
                text = response
                reply_markup = None
                if isinstance(response, dict):
                    text = response.get("text", "")
                    buttons = response.get("buttons")
                    if buttons:
                        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

                        kb = []
                        for row in buttons:
                            kb_row = []
                            for btn in row:
                                kb_row.append(
                                    InlineKeyboardButton(
                                        text=btn["text"], callback_data=btn["data"]
                                    )
                                )
                            kb.append(kb_row)
                        reply_markup = InlineKeyboardMarkup(kb)

                try:
                    await self._app.bot.send_message(
                        chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Failed to send slash command response: {e}")
                return

        # Build content from text and/or media
        content_parts = []
        media_paths = []
        attachments: list[dict[str, str]] = []

        # Text content
        if message.text:
            content_parts.append(message.text)
        if message.caption:
            content_parts.append(message.caption)

        # Handle media files
        media_file = None
        media_type = None

        if message.photo:
            media_file = message.photo[-1]  # Largest photo
            media_type = "image"
        elif message.voice:
            media_file = message.voice
            media_type = "voice"
        elif message.audio:
            media_file = message.audio
            media_type = "audio"
        elif message.document:
            media_file = message.document
            media_type = "document"
        elif message.sticker:
            media_file = message.sticker
            media_type = "sticker"

        # Download media if present
        if media_file and self._app:
            try:
                file = await self._app.bot.get_file(media_file.file_id)
                ext = self._get_extension(media_type, getattr(media_file, "mime_type", None))

                # Save to active profile media dir
                from g_agent.config.loader import get_data_dir

                media_dir = get_data_dir() / "media"
                media_dir.mkdir(parents=True, exist_ok=True)

                file_path = media_dir / f"{media_file.file_id[:16]}{ext}"
                await file.download_to_drive(str(file_path))

                media_paths.append(str(file_path))
                mime = getattr(media_file, "mime_type", None) or ""
                attachments.append(
                    {
                        "type": str(media_type or "file"),
                        "path": str(file_path),
                        "mime": str(mime),
                        "caption": str(message.caption or ""),
                        "sourceChannel": "telegram",
                    }
                )

                # Handle voice transcription
                if media_type == "voice" or media_type == "audio":
                    from g_agent.providers.transcription import GroqTranscriptionProvider

                    transcriber = GroqTranscriptionProvider(api_key=self.groq_api_key)
                    transcription = await transcriber.transcribe(file_path)
                    if transcription:
                        logger.info(f"Transcribed {media_type}: {transcription[:50]}...")
                        content_parts.append(f"[transcription: {transcription}]")
                    else:
                        content_parts.append(f"[{media_type}: {file_path}]")
                else:
                    content_parts.append(f"[{media_type}: {file_path}]")

                logger.debug(f"Downloaded {media_type} to {file_path}")
            except Exception as e:
                logger.error(f"Failed to download media: {e}")
                content_parts.append(f"[{media_type}: download failed]")

        content = "\n".join(content_parts) if content_parts else "[empty message]"

        logger.debug(f"Telegram message from {sender_id}: {content[:50]}...")

        # Forward to the message bus
        await self._handle_message(
            sender_id=sender_id,
            chat_id=str(chat_id),
            content=content,
            media=media_paths,
            metadata={
                "message_id": message.message_id,
                "user_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "is_group": message.chat.type != "private",
                "from_me": False,
                "attachments": attachments,
            },
        )

    def _get_extension(self, media_type: str, mime_type: str | None) -> str:
        """Get file extension based on media type."""
        if mime_type:
            ext_map = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/gif": ".gif",
                "audio/ogg": ".ogg",
                "audio/mpeg": ".mp3",
                "audio/mp4": ".m4a",
                "image/webp": ".webp",
                "video/webm": ".webm",
            }
            if mime_type in ext_map:
                return ext_map[mime_type]

        type_map = {
            "image": ".jpg",
            "voice": ".ogg",
            "audio": ".mp3",
            "document": "",
            "sticker": ".webp",
        }
        return type_map.get(media_type, "")
