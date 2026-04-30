"""OpenAI-compatible request and response helpers."""

import json
import time
import uuid
from typing import Any


def model_list(model_ids: list[str]) -> dict[str, Any]:
    """Build an OpenAI-compatible model list response."""
    seen: set[str] = set()
    data: list[dict[str, str]] = []
    for model_id in model_ids:
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        data.append({"id": model_id, "object": "model", "owned_by": "g-agent"})
    return {"object": "list", "data": data}


def last_user_content(messages: list[Any]) -> str:
    """Return normalized content from the last user message."""
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        return normalize_content(message.get("content"))
    return ""


def normalize_content(content: Any) -> str:
    """Normalize text-only chat content into a prompt string."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") in {"text", "input_text"}:
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()
    return ""


def extract_media(messages: list[Any]) -> list[str]:
    """Extract media URLs (including base64 data URLs) from the last user message."""
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, list):
            media = []
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "image_url":
                    url = item.get("image_url", {}).get("url")
                    if isinstance(url, str):
                        media.append(url)
            return media
    return []


def chat_id_from_session_key(session_key: str) -> str:
    """Derive the API chat id used by the runtime from a session key."""
    return session_key.split(":", 1)[1] if ":" in session_key else session_key


def chat_completion_response(*, model: str, response_text: str) -> dict[str, Any]:
    """Build a non-streaming OpenAI-compatible chat completion response."""
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": response_text},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def chat_completion_stream_events(*, model: str, response_text: str) -> list[bytes]:
    """Build SSE data frames for a non-tokenized chat completion stream."""
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    return [
        _sse_data(
            _chat_completion_chunk(
                completion_id=completion_id,
                created=created,
                model=model,
                delta={"role": "assistant"},
            )
        ),
        _sse_data(
            _chat_completion_chunk(
                completion_id=completion_id,
                created=created,
                model=model,
                delta={"content": response_text},
            )
        ),
        _sse_data(
            _chat_completion_chunk(
                completion_id=completion_id,
                created=created,
                model=model,
                delta={},
                finish_reason="stop",
            )
        ),
        b"data: [DONE]\n\n",
    ]


def _chat_completion_chunk(
    *,
    completion_id: str,
    created: int,
    model: str,
    delta: dict[str, str],
    finish_reason: str | None = None,
) -> dict[str, Any]:
    return {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }
        ],
    }


def _sse_data(payload: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n".encode()
