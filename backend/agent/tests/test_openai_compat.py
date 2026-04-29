"""OpenAI compatibility helper tests."""

from g_agent.api.openai_compat import (
    chat_completion_response,
    chat_completion_stream_events,
    chat_id_from_session_key,
    last_user_content,
    model_list,
    normalize_content,
)


def test_model_list_deduplicates_models() -> None:
    payload = model_list(["main", "fallback", "main", ""])

    assert payload["object"] == "list"
    assert [item["id"] for item in payload["data"]] == ["main", "fallback"]


def test_last_user_content_uses_last_user_message() -> None:
    messages = [
        {"role": "user", "content": "old"},
        {"role": "assistant", "content": "ignored"},
        {"role": "user", "content": [{"type": "text", "text": "new"}]},
    ]

    assert last_user_content(messages) == "new"


def test_normalize_content_accepts_text_and_input_text_parts() -> None:
    content = [
        {"type": "text", "text": "hello"},
        {"type": "image_url", "image_url": {"url": "https://example.test/image.png"}},
        {"type": "input_text", "text": "world"},
        "ignored",
    ]

    assert normalize_content(content) == "hello\nworld"


def test_chat_id_from_session_key() -> None:
    assert chat_id_from_session_key("api:room-1") == "room-1"
    assert chat_id_from_session_key("room-1") == "room-1"


def test_chat_completion_response_shape() -> None:
    payload = chat_completion_response(model="model-a", response_text="done")

    assert payload["id"].startswith("chatcmpl-")
    assert payload["object"] == "chat.completion"
    assert payload["model"] == "model-a"
    assert payload["choices"][0]["message"] == {"role": "assistant", "content": "done"}
    assert payload["usage"] == {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }


def test_chat_completion_stream_events_shape() -> None:
    events = chat_completion_stream_events(model="model-a", response_text="done")

    assert len(events) == 4
    assert events[0].startswith(b"data: ")
    assert b'"object":"chat.completion.chunk"' in events[0]
    assert b'"role":"assistant"' in events[0]
    assert b'"content":"done"' in events[1]
    assert b'"finish_reason":"stop"' in events[2]
    assert events[3] == b"data: [DONE]\n\n"
