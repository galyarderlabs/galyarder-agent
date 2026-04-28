"""Tests for shared channel contracts."""

import asyncio
from pathlib import Path
from types import SimpleNamespace

from g_agent.bus.events import OutboundMessage
from g_agent.bus.queue import MessageBus
from g_agent.channels.base import BaseChannel
from g_agent.channels.capabilities import (
    DISCORD_CAPABILITIES,
    TELEGRAM_CAPABILITIES,
    WHATSAPP_CAPABILITIES,
    capabilities_for_channel,
    split_text,
)
from g_agent.channels.slash_commands import SlashCommandDispatcher
from g_agent.channels.errors import DeliveryErrorCode, DeliveryResult
from g_agent.channels.media import MediaEnvelope, normalize_media_envelopes


class DummyChannel(BaseChannel):
    name = "dummy"

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        return None


def test_base_channel_adds_normalized_media_attachments(tmp_path: Path):
    bus = MessageBus()
    channel = DummyChannel(SimpleNamespace(allow_from=[]), bus)
    media_path = tmp_path / "image.png"
    media_path.write_bytes(b"image")

    asyncio.run(
        channel._handle_message(
            sender_id="owner",
            chat_id="chat",
            content="hello",
            media=[str(media_path)],
            metadata={"attachments": [{"type": "image", "path": str(media_path)}]},
        )
    )

    msg = asyncio.run(bus.consume_inbound())

    assert msg.media == [str(media_path)]
    assert msg.metadata["attachments"][0]["type"] == "image"
    assert msg.metadata["attachments"][0]["path"] == str(media_path)
    assert msg.metadata["attachments"][0]["filename"] == "image.png"
    assert msg.metadata["attachments"][0]["size"] == 5
    assert "sha256" in msg.metadata["attachments"][0]


def test_media_envelope_from_path_records_file_details(tmp_path: Path):
    media_path = tmp_path / "clip.ogg"
    media_path.write_bytes(b"voice")

    envelope = MediaEnvelope.from_path(
        media_path,
        kind="voice",
        mime_type="audio/ogg",
        source_channel="telegram",
    )

    assert envelope.kind == "voice"
    assert envelope.path == str(media_path.resolve())
    assert envelope.filename == "clip.ogg"
    assert envelope.size == 5
    assert envelope.mime_type == "audio/ogg"
    assert envelope.source_channel == "telegram"
    assert len(envelope.sha256 or "") == 64


def test_normalize_media_envelopes_preserves_metadata_and_legacy_paths(tmp_path: Path):
    media_path = tmp_path / "photo.jpg"
    media_path.write_bytes(b"photo")

    envelopes = normalize_media_envelopes(
        [str(media_path)],
        source_channel="whatsapp",
        attachments=[{"type": "image", "path": str(media_path), "mime": "image/jpeg"}],
    )

    assert len(envelopes) == 1
    assert envelopes[0].kind == "image"
    assert envelopes[0].mime_type == "image/jpeg"


def test_channel_capability_defaults_match_core_channels():
    assert TELEGRAM_CAPABILITIES.supports_media_send is True
    assert TELEGRAM_CAPABILITIES.supports_buttons is True
    assert TELEGRAM_CAPABILITIES.parse_mode == "HTML"
    assert WHATSAPP_CAPABILITIES.supports_media_receive is True
    assert DISCORD_CAPABILITIES.supports_threads is True
    assert DISCORD_CAPABILITIES.max_text_chars == 2000
    assert "media-send" in capabilities_for_channel("telegram").summary()
    assert capabilities_for_channel("unknown").summary() == "basic text"


def test_status_command_surfaces_current_channel_capabilities(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr("g_agent.config.loader.get_data_path", lambda: data_dir)
    monkeypatch.setattr("g_agent.utils.helpers.get_data_path", lambda: data_dir)
    monkeypatch.setattr("g_agent.session.manager.get_data_path", lambda: data_dir)

    dispatcher = SlashCommandDispatcher(tmp_path)
    result = asyncio.run(
        dispatcher.try_handle("/status", "telegram:123", "telegram", "123")
    )

    assert "Channel" in result
    assert "telegram" in result
    assert "media-send" in result


def test_split_text_respects_channel_limit():
    chunks = split_text("first line\nsecond line\nthird line", 12)

    assert chunks == ["first line", "second line", "third line"]
    assert all(len(chunk) <= 12 for chunk in chunks)


def test_split_text_hard_wraps_long_segments():
    chunks = split_text("abcdefghijkl", 5)

    assert chunks == ["abcde", "fghij", "kl"]


def test_delivery_result_success_and_failure_contracts():
    success = DeliveryResult.success(channel="telegram", chat_id="123")
    failure = DeliveryResult.failure(
        channel="whatsapp",
        chat_id="62811@s.whatsapp.net",
        code=DeliveryErrorCode.DISCONNECTED,
        message="bridge not connected",
        metadata={"retryable": True},
    )

    assert success.ok is True
    assert success.code is None
    assert failure.ok is False
    assert failure.code == DeliveryErrorCode.DISCONNECTED
    assert failure.metadata["retryable"] is True
