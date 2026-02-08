"""Base channel interface for chat platforms."""

from abc import ABC, abstractmethod
import re
from typing import Any

from loguru import logger

from g_agent.bus.events import InboundMessage, OutboundMessage
from g_agent.bus.queue import MessageBus


class BaseChannel(ABC):
    """
    Abstract base class for chat channel implementations.
    
    Each channel (Telegram, Discord, etc.) should implement this interface
    to integrate with the Galyarder Agent message bus.
    """
    
    name: str = "base"
    
    def __init__(self, config: Any, bus: MessageBus):
        """
        Initialize the channel.
        
        Args:
            config: Channel-specific configuration.
            bus: The message bus for communication.
        """
        self.config = config
        self.bus = bus
        self._running = False
    
    @abstractmethod
    async def start(self) -> None:
        """
        Start the channel and begin listening for messages.
        
        This should be a long-running async task that:
        1. Connects to the chat platform
        2. Listens for incoming messages
        3. Forwards messages to the bus via _handle_message()
        """
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel and clean up resources."""
        pass
    
    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """
        Send a message through this channel.
        
        Args:
            msg: The message to send.
        """
        pass
    
    def is_allowed(self, sender_id: str) -> bool:
        """
        Check if a sender is allowed to use this bot.
        
        Args:
            sender_id: The sender's identifier.
        
        Returns:
            True if allowed, False otherwise.
        """
        allow_list = getattr(self.config, "allow_from", [])
        
        # If no allow list, allow everyone
        if not allow_list:
            return True

        sender_variants = self._build_identity_variants(sender_id)
        for allowed in allow_list:
            allowed_variants = self._build_identity_variants(allowed)
            if sender_variants & allowed_variants:
                return True
        return False

    def _build_identity_variants(self, raw: str) -> set[str]:
        """Build matching variants for user IDs / phone-like IDs."""
        text = str(raw or "").strip()
        variants = {text}

        if "|" in text:
            variants.update(part.strip() for part in text.split("|") if part.strip())

        if "@" in text:
            variants.add(text.split("@", 1)[0].strip())

        digits = re.sub(r"\D+", "", text)
        if digits:
            variants.add(digits)
            if digits.startswith("0") and len(digits) > 5:
                variants.add(f"62{digits[1:]}")
            if digits.startswith("62") and len(digits) > 5:
                variants.add(f"0{digits[2:]}")
            variants.add(digits.lstrip("0"))

        return {v for v in variants if v}
    
    async def _handle_message(
        self,
        sender_id: str,
        chat_id: str,
        content: str,
        media: list[str] | None = None,
        metadata: dict[str, Any] | None = None
    ) -> None:
        """
        Handle an incoming message from the chat platform.
        
        This method checks permissions and forwards to the bus.
        
        Args:
            sender_id: The sender's identifier.
            chat_id: The chat/channel identifier.
            content: Message text content.
            media: Optional list of media URLs.
            metadata: Optional channel-specific metadata.
        """
        metadata_obj = metadata or {}
        if not metadata_obj.get("from_me") and not self.is_allowed(sender_id):
            logger.warning(
                f"Access denied for sender {sender_id} on channel {self.name}. "
                f"Add them to allowFrom list in config to grant access."
            )
            return
        
        msg = InboundMessage(
            channel=self.name,
            sender_id=str(sender_id),
            chat_id=str(chat_id),
            content=content,
            media=media or [],
            metadata=metadata_obj
        )
        
        await self.bus.publish_inbound(msg)
    
    @property
    def is_running(self) -> bool:
        """Check if the channel is running."""
        return self._running
