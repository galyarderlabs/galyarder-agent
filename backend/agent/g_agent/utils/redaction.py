import re


def redact_secrets(text: str) -> str:
    """Redact obvious secret-like values from text."""
    if not text:
        return ""
    redacted = text
    # Keys/Tokens
    redacted = re.sub(
        r"(?i)\b(api[_-]?key|token|secret|password|passwd|authorization)\b\s*([:=]|is)?\s*['\"]?[^'\"\s,{}]{5,}['\"]?",
        lambda m: f"{m.group(1)}=<redacted>",
        redacted,
    )
    # Bearer tokens
    redacted = re.sub(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{12,}", "Bearer <redacted>", redacted)
    # OpenAI sk-
    redacted = re.sub(r"\bsk-[a-zA-Z0-9]{16,}", "sk-<redacted>", redacted)
    return redacted
