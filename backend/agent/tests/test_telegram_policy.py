import pytest
from g_agent.channels.telegram import TelegramChannel
from g_agent.config.schema import TelegramConfig
from unittest.mock import MagicMock
from pathlib import Path

def test_telegram_is_allowed_variants():
    config = TelegramConfig(token="test", allow_from=["12345", "owner@t.me"])
    bus = MagicMock()
    channel = TelegramChannel(config, bus, workspace=Path("/tmp"))
    
    assert channel.is_allowed("12345")
    assert channel.is_allowed("owner")
    assert channel.is_allowed("owner@t.me")
    assert not channel.is_allowed("67890")
    assert not channel.is_allowed("other@t.me")

def test_telegram_is_allowed_empty():
    # Empty allow_from means everyone is allowed
    config = TelegramConfig(token="test", allow_from=[])
    bus = MagicMock()
    channel = TelegramChannel(config, bus, workspace=Path("/tmp"))
    
    assert channel.is_allowed("anybody")
