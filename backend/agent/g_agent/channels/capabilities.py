"""Shared channel capability contracts."""

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ChannelCapabilities:
    """Runtime capabilities and limits exposed by a channel."""

    supports_media_send: bool = False
    supports_media_receive: bool = False
    supports_buttons: bool = False
    supports_typing: bool = False
    supports_threads: bool = False
    supports_reactions: bool = False
    max_text_chars: int | None = None
    parse_mode: str | None = None
    media_types: tuple[str, ...] = field(default_factory=tuple)

    def split_text(self, text: str) -> list[str]:
        """Split text according to this channel's text limit."""
        return split_text(text, self.max_text_chars)

    def summary(self) -> str:
        """Return a compact owner-facing capability summary."""
        flags: list[str] = []
        if self.supports_media_send:
            flags.append("media-send")
        if self.supports_media_receive:
            flags.append("media-receive")
        if self.supports_buttons:
            flags.append("buttons")
        if self.supports_typing:
            flags.append("typing")
        if self.supports_threads:
            flags.append("threads")
        if self.supports_reactions:
            flags.append("reactions")
        if self.max_text_chars:
            flags.append(f"max-text={self.max_text_chars}")
        if self.parse_mode:
            flags.append(f"parse={self.parse_mode}")
        return ", ".join(flags) if flags else "basic text"


DEFAULT_CHANNEL_CAPABILITIES = ChannelCapabilities()

TELEGRAM_CAPABILITIES = ChannelCapabilities(
    supports_media_send=True,
    supports_media_receive=True,
    supports_buttons=True,
    supports_typing=True,
    max_text_chars=4096,
    parse_mode="HTML",
    media_types=("image", "voice", "audio", "sticker", "document"),
)

WHATSAPP_CAPABILITIES = ChannelCapabilities(
    supports_media_send=True,
    supports_media_receive=True,
    supports_typing=True,
    max_text_chars=4096,
    media_types=("image", "voice", "audio", "sticker", "document"),
)

DISCORD_CAPABILITIES = ChannelCapabilities(
    supports_media_send=True,
    supports_media_receive=True,
    supports_typing=True,
    supports_threads=True,
    supports_reactions=False,
    max_text_chars=2000,
    media_types=("image", "audio", "document"),
)

EMAIL_CAPABILITIES = ChannelCapabilities(
    supports_media_send=False,
    supports_media_receive=False,
    max_text_chars=None,
    media_types=(),
)

SLACK_CAPABILITIES = ChannelCapabilities(
    supports_media_send=False,
    supports_media_receive=False,
    supports_typing=False,
    supports_threads=True,
    supports_reactions=True,
    max_text_chars=40000,
    media_types=(),
)

_CAPABILITIES_BY_CHANNEL = {
    "discord": DISCORD_CAPABILITIES,
    "email": EMAIL_CAPABILITIES,
    "slack": SLACK_CAPABILITIES,
    "telegram": TELEGRAM_CAPABILITIES,
    "whatsapp": WHATSAPP_CAPABILITIES,
}


def capabilities_for_channel(channel: str) -> ChannelCapabilities:
    """Return known capabilities for a channel name."""
    return _CAPABILITIES_BY_CHANNEL.get(channel.lower(), DEFAULT_CHANNEL_CAPABILITIES)


def split_text(text: str, max_chars: int | None) -> list[str]:
    """Split text on paragraph or line boundaries before hard wrapping,
    ensuring markdown code blocks are closed/reopened across chunks.
    """
    if max_chars is None or max_chars <= 0 or len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current_chunk = ""
    in_code_block = False
    code_block_lang = ""

    # Split by lines to preserve structure where possible
    lines = text.splitlines(keepends=True)

    for line in lines:
        # Track code block state
        if line.strip().startswith("```"):
            if in_code_block:
                in_code_block = False
                code_block_lang = ""
            else:
                in_code_block = True
                # Try to capture language
                lang_match = re.match(r"```(\w+)", line.strip())
                code_block_lang = lang_match.group(1) if lang_match else ""

        # If this line alone is too long, we must hard wrap it
        if len(line) > max_chars:
            if current_chunk:
                # Close code block if needed before pushing chunk
                if in_code_block:
                    current_chunk = current_chunk.rstrip() + "\n```"
                chunks.append(current_chunk.rstrip())
                current_chunk = "```" + code_block_lang + "\n" if in_code_block else ""

            # Hard wrap the long line
            sub_chunks = _hard_wrap(line, max_chars - (4 if in_code_block else 0))
            for i, sc in enumerate(sub_chunks):
                if in_code_block:
                    sc = "```" + code_block_lang + "\n" + sc + "\n```"
                chunks.append(sc)
            continue

        # Check if adding this line exceeds the limit
        # Reserved space: 4 chars for "```\n" closure
        reserved = 4 if in_code_block else 0
        if len(current_chunk) + len(line) + reserved > max_chars:
            if current_chunk:
                # Close code block in current chunk
                if in_code_block:
                    current_chunk = current_chunk.rstrip() + "\n```"
                chunks.append(current_chunk.rstrip())
                # Reopen code block in next chunk
                current_chunk = "```" + code_block_lang + "\n" if in_code_block else ""
            
            current_chunk += line
        else:
            current_chunk += line

    if current_chunk and current_chunk.strip():
        if in_code_block:
            current_chunk = current_chunk.rstrip() + "\n```"
        chunks.append(current_chunk.rstrip())

    return chunks or [""]


def _hard_wrap(text: str, max_chars: int) -> list[str]:
    """Hard-wrap a single over-limit segment."""
    if max_chars <= 0:
        return [text]
    return [text[i : i + max_chars].rstrip() for i in range(0, len(text), max_chars)]
