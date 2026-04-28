"""Tests for Discord session and thread mapping."""

import asyncio
from types import SimpleNamespace

from g_agent.bus.queue import MessageBus
from g_agent.channels.discord import DiscordChannel
from g_agent.config.schema import DiscordConfig


class FakeHTTP:
    async def post(self, *args, **kwargs):
        return SimpleNamespace(raise_for_status=lambda: None, status_code=204)


def test_discord_message_mapping_marks_dm_scope(monkeypatch):
    channel = DiscordChannel(DiscordConfig(enabled=True, token="token"), MessageBus())
    channel._http = FakeHTTP()
    captured: dict[str, object] = {}

    async def fake_handle_message(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(channel, "_handle_message", fake_handle_message)

    payload = {
        "id": "msg-1",
        "channel_id": "dm-1",
        "author": {"id": "user-1", "bot": False},
        "content": "hello",
    }

    asyncio.run(channel._handle_message_create(payload))

    assert captured["chat_id"] == "dm-1"
    mapping = captured["metadata"]["discord"]
    assert mapping["scope"] == "dm"
    assert mapping["channel_id"] == "dm-1"
    assert mapping["thread_id"] == ""


def test_discord_message_mapping_marks_thread_scope(monkeypatch):
    channel = DiscordChannel(DiscordConfig(enabled=True, token="token"), MessageBus())
    channel._http = FakeHTTP()
    captured: dict[str, object] = {}

    async def fake_handle_message(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(channel, "_handle_message", fake_handle_message)

    payload = {
        "id": "msg-2",
        "channel_id": "thread-1",
        "channel_type": 11,
        "guild_id": "guild-1",
        "author": {"id": "user-1", "bot": False},
        "content": "thread hello",
    }

    asyncio.run(channel._handle_message_create(payload))

    assert captured["chat_id"] == "thread-1"
    mapping = captured["metadata"]["discord"]
    assert mapping["scope"] == "thread"
    assert mapping["guild_id"] == "guild-1"
    assert mapping["thread_id"] == "thread-1"
