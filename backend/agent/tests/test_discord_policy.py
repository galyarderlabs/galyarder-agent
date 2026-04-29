import pytest
from g_agent.channels.discord import DiscordChannel
from g_agent.config.schema import DiscordConfig
from unittest.mock import MagicMock

def test_discord_is_allowed():
    config = DiscordConfig(token="test", intents=0, allow_from=["123456789"])
    bus = MagicMock()
    channel = DiscordChannel(config, bus)
    
    assert channel.is_allowed("123456789")
    assert not channel.is_allowed("987654321")
