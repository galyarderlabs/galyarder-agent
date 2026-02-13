import asyncio
import json
from pathlib import Path

from g_agent.agent.tools.message import MessageTool
from g_agent.bus.events import OutboundMessage
from g_agent.bus.queue import MessageBus
from g_agent.channels.whatsapp import WhatsAppChannel
from g_agent.config.schema import WhatsAppConfig


def test_message_tool_sends_media_payload(tmp_path: Path):
    captured: list[OutboundMessage] = []

    async def _send(msg: OutboundMessage) -> None:
        captured.append(msg)

    media_file = tmp_path / "sample.jpg"
    media_file.write_bytes(b"fake-image")

    tool = MessageTool(send_callback=_send, default_channel="telegram", default_chat_id="123")
    result = asyncio.run(
        tool.execute(
            content="See this",
            media_path=str(media_file),
        )
    )

    assert "Message sent to telegram:123 (image)" == result
    assert len(captured) == 1
    message = captured[0]
    assert message.media == [str(media_file.resolve())]
    assert message.metadata.get("media_type") == "image"
    assert message.metadata.get("caption") == "See this"


def test_message_tool_accepts_media_without_text(tmp_path: Path):
    captured: list[OutboundMessage] = []

    async def _send(msg: OutboundMessage) -> None:
        captured.append(msg)

    voice_file = tmp_path / "clip.ogg"
    voice_file.write_bytes(b"voice")

    tool = MessageTool(
        send_callback=_send, default_channel="whatsapp", default_chat_id="62811@s.whatsapp.net"
    )
    result = asyncio.run(
        tool.execute(
            media_path=str(voice_file),
            media_type="voice",
        )
    )

    assert "Message sent to whatsapp:62811@s.whatsapp.net (voice)" == result
    assert len(captured) == 1
    assert captured[0].content == ""
    assert captured[0].metadata.get("media_type") == "voice"




def test_whatsapp_channel_builds_media_payload(tmp_path: Path):
    config = WhatsAppConfig(enabled=True, bridge_url="ws://localhost:3001", allow_from=[])
    channel = WhatsAppChannel(config=config, bus=MessageBus())

    sent_payloads: list[dict[str, str]] = []

    class DummyWS:
        async def send(self, raw: str) -> None:
            sent_payloads.append(json.loads(raw))

    media_file = tmp_path / "sticker.webp"
    media_file.write_bytes(b"webp")

    channel._ws = DummyWS()
    channel._connected = True

    asyncio.run(
        channel.send(
            OutboundMessage(
                channel="whatsapp",
                chat_id="62811@s.whatsapp.net",
                content="",
                media=[str(media_file)],
                metadata={"media_type": "sticker", "caption": ""},
            )
        )
    )

    assert len(sent_payloads) == 1
    payload = sent_payloads[0]
    assert payload["type"] == "send"
    assert payload["to"] == "62811@s.whatsapp.net"
    assert payload["mediaType"] == "sticker"
    assert payload["mediaPath"] == str(media_file.resolve())


def test_message_tool_voice_without_engine_returns_error(monkeypatch):
    async def _send(msg: OutboundMessage) -> None:  # pragma: no cover - should not be called
        raise AssertionError("send callback should not be called")

    monkeypatch.setattr("g_agent.agent.tools.message.shutil.which", lambda _: None)
    tool = MessageTool(send_callback=_send, default_channel="telegram", default_chat_id="123")
    result = asyncio.run(
        tool.execute(
            content="hello world",
            media_type="voice",
        )
    )
    assert "voice synthesis unavailable" in result.lower()


def test_message_tool_image_without_magick_returns_error(monkeypatch):
    async def _send(msg: OutboundMessage) -> None:  # pragma: no cover - should not be called
        raise AssertionError("send callback should not be called")

    monkeypatch.setattr(
        "g_agent.agent.tools.message.shutil.which",
        lambda name: None if name in {"magick", "convert"} else None,
    )
    tool = MessageTool(send_callback=_send, default_channel="telegram", default_chat_id="123")
    result = asyncio.run(
        tool.execute(
            content="daily summary",
            media_type="image",
        )
    )
    assert "image card generation unavailable" in result.lower()


def test_message_tool_sticker_without_magick_returns_error(monkeypatch):
    async def _send(msg: OutboundMessage) -> None:  # pragma: no cover - should not be called
        raise AssertionError("send callback should not be called")

    monkeypatch.setattr(
        "g_agent.agent.tools.message.shutil.which",
        lambda name: None if name in {"magick", "convert"} else None,
    )
    tool = MessageTool(send_callback=_send, default_channel="telegram", default_chat_id="123")
    result = asyncio.run(
        tool.execute(
            content="daily summary",
            media_type="sticker",
        )
    )
    assert "sticker generation unavailable" in result.lower()


def test_message_tool_sticker_no_default_caption(tmp_path: Path, monkeypatch):
    captured: list[OutboundMessage] = []

    async def _send(msg: OutboundMessage) -> None:
        captured.append(msg)

    sticker_file = tmp_path / "auto.webp"
    sticker_file.write_bytes(b"webp")

    def fake_render(self: MessageTool, text: str) -> str:
        return str(sticker_file.resolve())

    monkeypatch.setattr(MessageTool, "_render_sticker_card", fake_render)

    tool = MessageTool(send_callback=_send, default_channel="telegram", default_chat_id="123")
    result = asyncio.run(tool.execute(content="hello sticker", media_type="sticker"))

    assert "Message sent to telegram:123 (sticker)" == result
    assert len(captured) == 1
    assert captured[0].metadata.get("media_type") == "sticker"
    assert "caption" not in captured[0].metadata


def test_message_tool_voice_tts_wav_falls_back_to_audio(tmp_path: Path, monkeypatch):
    captured: list[OutboundMessage] = []

    async def _send(msg: OutboundMessage) -> None:
        captured.append(msg)

    wav_file = tmp_path / "tts.wav"
    wav_file.write_bytes(b"fake-wav")

    def fake_synthesize(self: MessageTool, text: str, media_type: str) -> str:
        assert text == "voice fallback check"
        assert media_type == "voice"
        return str(wav_file.resolve())

    monkeypatch.setattr(MessageTool, "_synthesize_speech", fake_synthesize)

    tool = MessageTool(
        send_callback=_send, default_channel="whatsapp", default_chat_id="62811@s.whatsapp.net"
    )
    result = asyncio.run(tool.execute(content="voice fallback check", media_type="voice"))

    assert "Message sent to whatsapp:62811@s.whatsapp.net (audio)" == result
    assert len(captured) == 1
    assert captured[0].metadata.get("media_type") == "audio"
    assert captured[0].metadata.get("mime_type") == "audio/wav"


def test_whatsapp_channel_transcribes_audio_by_media_fields(tmp_path: Path, monkeypatch):
    config = WhatsAppConfig(enabled=True, bridge_url="ws://localhost:3001", allow_from=[])
    channel = WhatsAppChannel(config=config, bus=MessageBus(), groq_api_key="")

    media_file = tmp_path / "voice.ogg"
    media_file.write_bytes(b"voice")

    class FakeTranscriber:
        def __init__(self, api_key: str | None = None):
            self.api_key = api_key

        async def transcribe(self, file_path: str | Path) -> str:
            assert str(file_path) == str(media_file)
            return "transcribed text"

    monkeypatch.setattr("g_agent.channels.whatsapp.GroqTranscriptionProvider", FakeTranscriber)

    captured: dict[str, object] = {}

    async def fake_handle_message(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(channel, "_handle_message", fake_handle_message)

    payload = {
        "type": "message",
        "sender": "62811@s.whatsapp.net",
        "chatId": "62811@s.whatsapp.net",
        "content": "[Audio Clip]",
        "mediaType": "voice",
        "mimeType": "audio/ogg",
        "mediaPath": str(media_file),
    }

    asyncio.run(channel._handle_bridge_message(json.dumps(payload)))

    assert "content" in captured
    assert "[transcription: transcribed text]" in str(captured["content"])
