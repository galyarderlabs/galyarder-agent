import pytest
from g_agent.channels.discord import DiscordChannel
from g_agent.config.schema import DiscordConfig
from unittest.mock import MagicMock

def test_discord_session_mapping_dm():
    config = DiscordConfig(token="test", intents=0)
    bus = MagicMock()
    channel = DiscordChannel(config, bus)
    
    payload = {
        "channel_id": "123",
        "guild_id": None,
    }
    mapping = channel._message_session_mapping(payload)
    assert mapping["chat_id"] == "123"
    assert mapping["scope"] == "dm"

def test_discord_session_mapping_guild():
    config = DiscordConfig(token="test", intents=0)
    bus = MagicMock()
    channel = DiscordChannel(config, bus)
    
    payload = {
        "channel_id": "123",
        "guild_id": "456",
    }
    mapping = channel._message_session_mapping(payload)
    assert mapping["chat_id"] == "123"
    assert mapping["guild_id"] == "456"
    assert mapping["scope"] == "guild_channel"

def test_discord_session_mapping_thread():
    config = DiscordConfig(token="test", intents=0)
    bus = MagicMock()
    channel = DiscordChannel(config, bus)
    
    payload = {
        "channel_id": "123",
        "guild_id": "456",
        "thread_id": "789",
    }
    mapping = channel._message_session_mapping(payload)
    assert mapping["chat_id"] == "789"
    assert mapping["thread_id"] == "789"
    assert mapping["scope"] == "thread"
