import asyncio
from pathlib import Path

from g_agent.providers.transcription import GroqTranscriptionProvider


class _DummyResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class _DummyClient:
    def __init__(self, captured: dict, payload: dict):
        self.captured = captured
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url: str, headers: dict, files: dict, timeout: float):
        self.captured["url"] = url
        self.captured["headers"] = headers
        self.captured["files"] = files
        self.captured["timeout"] = timeout
        return _DummyResponse(self.payload)


def test_groq_transcribe_payload_defaults(monkeypatch, tmp_path: Path):
    audio_path = tmp_path / "sample.ogg"
    audio_path.write_bytes(b"audio-data")

    captured: dict[str, object] = {}
    payload = {"text": "halo hasil transkripsi"}

    monkeypatch.setattr(
        "g_agent.providers.transcription.httpx.AsyncClient",
        lambda: _DummyClient(captured, payload),
    )

    provider = GroqTranscriptionProvider(api_key="gsk_test")
    result = asyncio.run(provider.transcribe(audio_path))

    assert result == "halo hasil transkripsi"
    assert captured["url"] == "https://api.groq.com/openai/v1/audio/transcriptions"
    assert captured["timeout"] == 60.0
    assert captured["headers"] == {"Authorization": "Bearer gsk_test"}

    files = captured["files"]
    assert files["file"][0] == "sample.ogg"
    assert files["model"] == (None, "whisper-large-v3-turbo")
    assert files["temperature"] == (None, "0")
    assert files["response_format"] == (None, "verbose_json")


def test_groq_transcribe_payload_env_overrides(monkeypatch, tmp_path: Path):
    audio_path = tmp_path / "sample.m4a"
    audio_path.write_bytes(b"audio-data")

    monkeypatch.setenv("GROQ_TRANSCRIPTION_MODEL", "whisper-large-v3")
    monkeypatch.setenv("GROQ_TRANSCRIPTION_TEMPERATURE", "0.2")
    monkeypatch.setenv("GROQ_TRANSCRIPTION_RESPONSE_FORMAT", "json")

    captured: dict[str, object] = {}
    payload = {"text": "override ok"}

    monkeypatch.setattr(
        "g_agent.providers.transcription.httpx.AsyncClient",
        lambda: _DummyClient(captured, payload),
    )

    provider = GroqTranscriptionProvider(api_key="gsk_test")
    result = asyncio.run(provider.transcribe(audio_path))

    assert result == "override ok"
    files = captured["files"]
    assert files["model"] == (None, "whisper-large-v3")
    assert files["temperature"] == (None, "0.2")
    assert files["response_format"] == (None, "json")
