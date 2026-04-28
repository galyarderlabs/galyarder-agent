"""Context fencing helpers for recalled memory."""

import re

_MEMORY_OPEN_RE = re.compile(r"<memory-context\b[^>]*>", re.IGNORECASE)
_MEMORY_CLOSE_RE = re.compile(r"</memory-context>", re.IGNORECASE)


def sanitize_memory_context(text: str) -> str:
    """Strip nested memory fences from provider output."""
    sanitized = _MEMORY_OPEN_RE.sub("", text or "")
    sanitized = _MEMORY_CLOSE_RE.sub("", sanitized)
    return sanitized.strip()


def fence_memory_context(provider_name: str, text: str) -> str:
    """Wrap recalled memory so it is treated as reference context."""
    sanitized = sanitize_memory_context(text)
    if not sanitized:
        return ""
    safe_name = re.sub(r"[^a-zA-Z0-9_.-]+", "-", provider_name or "memory").strip("-")
    safe_name = safe_name or "memory"
    return (
        f'<memory-context provider="{safe_name}" role="reference-only">\n'
        f"{sanitized}\n"
        "</memory-context>"
    )
