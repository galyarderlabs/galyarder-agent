"""Chat channels module with plugin architecture."""

from g_agent.channels.base import BaseChannel
from g_agent.channels.capabilities import ChannelCapabilities
from g_agent.channels.errors import DeliveryErrorCode, DeliveryResult
from g_agent.channels.manager import ChannelManager
from g_agent.channels.media import MediaEnvelope

__all__ = [
    "BaseChannel",
    "ChannelCapabilities",
    "ChannelManager",
    "DeliveryErrorCode",
    "DeliveryResult",
    "MediaEnvelope",
]
