"""Shared channel delivery result and error contracts."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class DeliveryErrorCode(StrEnum):
    """Normalized channel delivery error codes."""

    AUTH_FAILED = "auth_failed"
    DISCONNECTED = "disconnected"
    UNSUPPORTED_MEDIA = "unsupported_media"
    MEDIA_NOT_FOUND = "media_not_found"
    MESSAGE_TOO_LONG = "message_too_long"
    RATE_LIMITED = "rate_limited"
    SANDBOX_DENIED = "sandbox_denied"
    SEND_FAILED = "send_failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DeliveryResult:
    """Normalized outcome for a channel delivery attempt."""

    ok: bool
    channel: str
    chat_id: str
    code: DeliveryErrorCode | None = None
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(
        cls,
        *,
        channel: str,
        chat_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> "DeliveryResult":
        """Build a successful delivery result."""
        return cls(ok=True, channel=channel, chat_id=chat_id, metadata=metadata or {})

    @classmethod
    def failure(
        cls,
        *,
        channel: str,
        chat_id: str,
        code: DeliveryErrorCode,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> "DeliveryResult":
        """Build a failed delivery result."""
        return cls(
            ok=False,
            channel=channel,
            chat_id=chat_id,
            code=code,
            message=message,
            metadata=metadata or {},
        )
