"""Shared channel capability contracts."""

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
    supports_media_send=False,
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


def split_text(text: str, max_chars: int | None) -> list[str]:
    """Split text on paragraph or line boundaries before hard wrapping."""
    if max_chars is None or max_chars <= 0 or len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current = ""

    for paragraph in text.splitlines(keepends=True):
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current.rstrip())
                current = ""
            chunks.extend(_hard_wrap(paragraph, max_chars))
            continue

        if len(current) + len(paragraph) > max_chars:
            if current:
                chunks.append(current.rstrip())
            current = paragraph
        else:
            current += paragraph

    if current:
        chunks.append(current.rstrip())

    return chunks or [""]


def _hard_wrap(text: str, max_chars: int) -> list[str]:
    """Hard-wrap a single over-limit segment."""
    return [text[i : i + max_chars].rstrip() for i in range(0, len(text), max_chars)]
