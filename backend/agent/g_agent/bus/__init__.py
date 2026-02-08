"""Message bus module for decoupled channel-agent communication."""

from g_agent.bus.events import InboundMessage, OutboundMessage
from g_agent.bus.queue import MessageBus

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]
