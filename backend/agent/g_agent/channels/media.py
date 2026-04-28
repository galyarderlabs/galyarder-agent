"""Normalized media envelope helpers for channels."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import hashlib


@dataclass(frozen=True)
class MediaEnvelope:
    """Normalized channel media reference."""

    kind: str = "file"
    path: str | None = None
    url: str | None = None
    mime_type: str | None = None
    filename: str | None = None
    size: int | None = None
    sha256: str | None = None
    source_channel: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_path(
        cls,
        path: str | Path,
        *,
        kind: str = "file",
        mime_type: str | None = None,
        source_channel: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "MediaEnvelope":
        """Build an envelope for a local file path."""
        path_obj = Path(path).expanduser()
        resolved = path_obj.resolve() if path_obj.exists() else path_obj
        size = resolved.stat().st_size if resolved.exists() and resolved.is_file() else None
        digest = _sha256_file(resolved) if resolved.exists() and resolved.is_file() else None
        return cls(
            kind=kind or "file",
            path=str(resolved),
            mime_type=mime_type,
            filename=resolved.name,
            size=size,
            sha256=digest,
            source_channel=source_channel,
            metadata=metadata or {},
        )

    @classmethod
    def from_metadata(cls, item: dict[str, Any], *, source_channel: str | None = None) -> "MediaEnvelope":
        """Build an envelope from legacy attachment metadata."""
        path = _optional_str(item.get("path"))
        if path:
            envelope = cls.from_path(
                path,
                kind=str(item.get("type") or item.get("kind") or "file"),
                mime_type=_optional_str(item.get("mime") or item.get("mime_type")),
                source_channel=_optional_str(item.get("sourceChannel") or source_channel),
                metadata=dict(item.get("metadata") or {}),
            )
            if item.get("url") or item.get("filename") or item.get("size") or item.get("sha256"):
                return cls(
                    kind=envelope.kind,
                    path=envelope.path,
                    url=_optional_str(item.get("url")),
                    mime_type=envelope.mime_type,
                    filename=_optional_str(item.get("filename")) or envelope.filename,
                    size=_optional_int(item.get("size")) or envelope.size,
                    sha256=_optional_str(item.get("sha256")) or envelope.sha256,
                    source_channel=envelope.source_channel,
                    metadata=envelope.metadata,
                )
            return envelope

        return cls(
            kind=str(item.get("type") or item.get("kind") or "file"),
            path=path,
            url=_optional_str(item.get("url")),
            mime_type=_optional_str(item.get("mime") or item.get("mime_type")),
            filename=_optional_str(item.get("filename")),
            size=_optional_int(item.get("size")),
            sha256=_optional_str(item.get("sha256")),
            source_channel=_optional_str(item.get("sourceChannel") or source_channel),
            metadata=dict(item.get("metadata") or {}),
        )

    def to_metadata(self) -> dict[str, Any]:
        """Convert the envelope into channel metadata."""
        payload: dict[str, Any] = {
            "type": self.kind,
            "sourceChannel": self.source_channel,
        }
        for key, value in {
            "path": self.path,
            "url": self.url,
            "mime": self.mime_type,
            "filename": self.filename,
            "size": self.size,
            "sha256": self.sha256,
        }.items():
            if value is not None:
                payload[key] = value
        if self.metadata:
            payload["metadata"] = self.metadata
        return {key: value for key, value in payload.items() if value is not None}


def normalize_media_envelopes(
    media: list[str] | None,
    *,
    source_channel: str,
    attachments: list[dict[str, Any]] | None = None,
) -> list[MediaEnvelope]:
    """Normalize legacy media paths and attachment metadata into envelopes."""
    envelopes: list[MediaEnvelope] = []
    for item in attachments or []:
        envelopes.append(MediaEnvelope.from_metadata(item, source_channel=source_channel))
    for item in media or []:
        if item and not any(envelope.path == item for envelope in envelopes):
            envelopes.append(MediaEnvelope.from_path(item, source_channel=source_channel))
    return envelopes


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
