"""Channel manager for coordinating chat channels."""

import asyncio
import time
from typing import Any

from loguru import logger

from g_agent.bus.events import OutboundMessage
from g_agent.bus.queue import MessageBus
from g_agent.channels.base import BaseChannel
from g_agent.config.schema import Config


class ChannelManager:
    """
    Manages chat channels and coordinates message routing.

    Responsibilities:
    - Initialize enabled channels (Telegram, WhatsApp, etc.)
    - Start/stop channels
    - Route outbound messages
    """

    def __init__(self, config: Config, bus: MessageBus):
        self.config = config
        self.bus = bus
        self.channels: dict[str, BaseChannel] = {}
        self._dispatch_task: asyncio.Task | None = None
        self._outbound_idempotency_ttl_s = 120.0
        self._outbound_seen: dict[str, float] = {}

        self._init_channels()

    def _init_channels(self) -> None:
        """Initialize channels based on config."""

        # Telegram channel
        if self.config.channels.telegram.enabled:
            try:
                from g_agent.channels.telegram import TelegramChannel

                self.channels["telegram"] = TelegramChannel(
                    self.config.channels.telegram,
                    self.bus,
                    groq_api_key=self.config.providers.groq.api_key,
                )
                logger.info("Telegram channel enabled")
            except ImportError as e:
                logger.warning(f"Telegram channel not available: {e}")

        # WhatsApp channel
        if self.config.channels.whatsapp.enabled:
            try:
                from g_agent.channels.whatsapp import WhatsAppChannel

                self.channels["whatsapp"] = WhatsAppChannel(
                    self.config.channels.whatsapp,
                    self.bus,
                    groq_api_key=self.config.providers.groq.api_key,
                )
                logger.info("WhatsApp channel enabled")
            except ImportError as e:
                logger.warning(f"WhatsApp channel not available: {e}")

        # Discord channel
        if self.config.channels.discord.enabled:
            try:
                from g_agent.channels.discord import DiscordChannel

                self.channels["discord"] = DiscordChannel(self.config.channels.discord, self.bus)
                logger.info("Discord channel enabled")
            except ImportError as e:
                logger.warning(f"Discord channel not available: {e}")

        # Feishu channel
        if self.config.channels.feishu.enabled:
            try:
                from g_agent.channels.feishu import FeishuChannel

                self.channels["feishu"] = FeishuChannel(self.config.channels.feishu, self.bus)
                logger.info("Feishu channel enabled")
            except ImportError as e:
                logger.warning(f"Feishu channel not available: {e}")

        # Email channel
        if self.config.channels.email.enabled:
            try:
                from g_agent.channels.email import EmailChannel

                self.channels["email"] = EmailChannel(self.config.channels.email, self.bus)
                logger.info("Email channel enabled")
            except ImportError as e:
                logger.warning(f"Email channel not available: {e}")

        # Slack channel (Socket Mode — bidirectional, not webhook)
        if self.config.channels.slack_channel.enabled:
            try:
                from g_agent.channels.slack import SlackChannel

                self.channels["slack"] = SlackChannel(self.config.channels.slack_channel, self.bus)
                logger.info("Slack channel enabled")
            except ImportError as e:
                logger.warning(f"Slack channel not available: {e}")

    async def start_all(self) -> None:
        """Start WhatsApp channel and the outbound dispatcher."""
        if not self.channels:
            logger.warning("No channels enabled")
            return

        # Start outbound dispatcher
        self._dispatch_task = asyncio.create_task(self._dispatch_outbound())

        # Start WhatsApp channel
        tasks = []
        names = []
        for name, channel in self.channels.items():
            logger.info(f"Starting {name} channel...")
            tasks.append(asyncio.create_task(channel.start()))
            names.append(name)

        # Wait for all to complete (they should run forever)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for name, result in zip(names, results):
            if isinstance(result, Exception):
                logger.error(f"{name} channel stopped with error: {result}")

    async def stop_all(self) -> None:
        """Stop all channels and the dispatcher."""
        logger.info("Stopping all channels...")

        # Stop dispatcher
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                logger.debug("Outbound dispatcher task cancelled")

        # Stop all channels
        for name, channel in self.channels.items():
            try:
                await channel.stop()
                logger.info(f"Stopped {name} channel")
            except Exception as e:
                logger.error(f"Error stopping {name}: {e}")

    async def _dispatch_outbound(self) -> None:
        """Dispatch outbound messages to the appropriate channel."""
        logger.info("Outbound dispatcher started")

        while True:
            try:
                msg = await asyncio.wait_for(self.bus.consume_outbound(), timeout=1.0)
                if self._is_duplicate_outbound(msg):
                    continue

                channel = self.channels.get(msg.channel)
                if channel:
                    try:
                        await channel.send(msg)
                    except Exception as e:
                        logger.error(f"Error sending to {msg.channel}: {e}")
                else:
                    logger.warning(f"Unknown channel: {msg.channel}")

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    def _extract_idempotency_key(self, msg: OutboundMessage) -> str:
        """Extract optional idempotency key from outbound metadata."""
        metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
        key = str(metadata.get("idempotency_key", "")).strip()
        return key

    def _is_duplicate_outbound(self, msg: OutboundMessage) -> bool:
        """Return True when outbound message has been seen recently."""
        key = self._extract_idempotency_key(msg)
        if not key:
            return False

        now = time.time()
        threshold = now - self._outbound_idempotency_ttl_s
        stale = [
            item_key for item_key, seen_at in self._outbound_seen.items() if seen_at < threshold
        ]
        for item_key in stale:
            self._outbound_seen.pop(item_key, None)

        previous = self._outbound_seen.get(key)
        if previous is not None:
            logger.warning(f"Skipping duplicate outbound message (key={key})")
            return True

        self._outbound_seen[key] = now
        return False

    def get_channel(self, name: str) -> BaseChannel | None:
        """Get a channel by name."""
        return self.channels.get(name)

    def get_status(self) -> dict[str, Any]:
        """Get status of all channels."""
        return {
            name: {"enabled": True, "running": channel.is_running}
            for name, channel in self.channels.items()
        }

    @property
    def enabled_channels(self) -> list[str]:
        """Get list of enabled channel names."""
        return list(self.channels.keys())
