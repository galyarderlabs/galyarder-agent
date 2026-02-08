"""Chat channels module with plugin architecture."""

from g_agent.channels.base import BaseChannel
from g_agent.channels.manager import ChannelManager

__all__ = ["BaseChannel", "ChannelManager"]
