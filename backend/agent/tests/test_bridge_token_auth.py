"""Tests for WhatsApp bridge token authentication."""

from __future__ import annotations

import json

import pytest

from g_agent.config.loader import convert_keys, convert_to_camel  # noqa: I001
from g_agent.config.schema import WhatsAppConfig

# ── Schema tests ──────────────────────────────────────────────────────


def test_whatsapp_config_bridge_token_default_empty():
    config = WhatsAppConfig()
    assert config.bridge_token == ""


def test_whatsapp_config_bridge_token_roundtrip_camel_case():
    config = WhatsAppConfig(bridge_token="my-secret")
    data = convert_to_camel(config.model_dump())
    assert data["bridgeToken"] == "my-secret"

    restored = WhatsAppConfig.model_validate(convert_keys(data))
    assert restored.bridge_token == "my-secret"


# ── WhatsApp channel auth tests ───────────────────────────────────────


class _FakeWS:
    """Minimal fake WebSocket that records sent messages and exits after one iteration."""

    def __init__(self):
        self.sent: list[str] = []

    async def send(self, data):
        self.sent.append(data)

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_whatsapp_channel_sends_auth_on_connect():
    import asyncio
    from unittest.mock import patch

    from g_agent.bus.queue import MessageBus
    from g_agent.channels.whatsapp import WhatsAppChannel

    config = WhatsAppConfig(enabled=True, bridge_token="test-secret")
    bus = MessageBus()
    channel = WhatsAppChannel(config, bus)

    fake_ws = _FakeWS()

    class _FakeCM:
        async def __aenter__(self):
            return fake_ws

        async def __aexit__(self, *args):
            # Stop the loop after first connection
            channel._running = False
            return False

    with patch("websockets.connect", return_value=_FakeCM()):
        channel._running = True
        await asyncio.wait_for(channel.start(), timeout=5)

    # Verify auth message was sent
    assert len(fake_ws.sent) >= 1
    auth_msg = json.loads(fake_ws.sent[0])
    assert auth_msg == {"type": "auth", "token": "test-secret"}


@pytest.mark.asyncio
async def test_whatsapp_channel_skips_auth_when_no_token():
    import asyncio
    from unittest.mock import patch

    from g_agent.bus.queue import MessageBus
    from g_agent.channels.whatsapp import WhatsAppChannel

    config = WhatsAppConfig(enabled=True, bridge_token="")
    bus = MessageBus()
    channel = WhatsAppChannel(config, bus)

    fake_ws = _FakeWS()

    class _FakeCM:
        async def __aenter__(self):
            return fake_ws

        async def __aexit__(self, *args):
            channel._running = False
            return False

    with patch("websockets.connect", return_value=_FakeCM()):
        channel._running = True
        await asyncio.wait_for(channel.start(), timeout=5)

    # No auth message should have been sent
    assert len(fake_ws.sent) == 0
