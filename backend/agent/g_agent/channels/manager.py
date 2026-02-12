"""Channel manager for coordinating chat channels."""

import asyncio
import time
from typing import Any

from loguru import logger

from g_agent.bus.events import OutboundMessage
from g_agent.bus.queue import MessageBus
from g_agent.channels.base import BaseChannel
from g_agent.config.schema import Config
from g_agent.plugins.base import PluginContext
from g_agent.plugins.loader import filter_plugins, load_installed_plugins, register_channel_plugins


class ChannelManager:
    """
    Manages chat channels and coordinates message routing.

    Responsibilities:
    - Initialize enabled channels (Telegram, WhatsApp, etc.)
    - Start/stop channels
    - Route outbound messages
    """

    def __init__(self, config: Config, bus: MessageBus, plugins: list[Any] | None = None):
        self.config = config
        self.bus = bus
        self.channels: dict[str, BaseChannel] = {}
        self.plugins = plugins if plugins is not None else filter_plugins(
            load_installed_plugins(),
            enabled=self.config.tools.plugins.enabled,
            allow=self.config.tools.plugins.allow,
            deny=self.config.tools.plugins.deny,
        )
        self._dispatch_task: asyncio.Task | None = None
        self._channel_tasks: dict[str, asyncio.Task[None]] = {}
        self._outbound_retry_tasks: set[asyncio.Task[None]] = set()
        self._running = False
        self._channel_restart_delay_s = 5.0
        self._channel_restart_backoff_max_s = 60.0
        self._channel_restart_window_s = 120.0
        self._channel_restart_max_attempts_window = 8
        self._channel_restart_cooldown_s = 180.0
        self._channel_stable_reset_s = 180.0
        self._channel_restart_history: dict[str, list[float]] = {}
        self._outbound_retry_base_delay_s = 1.0
        self._outbound_retry_backoff_max_s = 30.0
        self._outbound_retry_max_attempts = 3
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

        if self.plugins:
            context = PluginContext(
                workspace=self.config.workspace_path,
                config=self.config,
                bus=self.bus,
            )
            register_channel_plugins(self.plugins, context, channels=self.channels)

    async def start_all(self) -> None:
        """Start all channels and the outbound dispatcher."""
        if not self.channels:
            logger.warning("No channels enabled")
            return

        if self._running:
            logger.warning("Channel manager already running")
            return

        self._running = True

        # Start outbound dispatcher
        self._dispatch_task = asyncio.create_task(self._dispatch_outbound())

        # Start channel supervisors
        tasks = []
        for name, channel in self.channels.items():
            logger.info(f"Starting {name} channel...")
            task = asyncio.create_task(self._run_channel_supervisor(name, channel))
            self._channel_tasks[name] = task
            tasks.append(task)

        # Wait for all supervisors to complete (normally on stop_all)
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop_all(self) -> None:
        """Stop all channels and the dispatcher."""
        logger.info("Stopping all channels...")
        self._running = False

        # Stop dispatcher
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                logger.debug("Outbound dispatcher task cancelled")
            self._dispatch_task = None

        # Stop all channels
        for name, channel in self.channels.items():
            try:
                await channel.stop()
                logger.info(f"Stopped {name} channel")
            except Exception as e:
                logger.error(f"Error stopping {name}: {e}")

        if self._channel_tasks:
            for task in self._channel_tasks.values():
                task.cancel()
            await asyncio.gather(*self._channel_tasks.values(), return_exceptions=True)
            self._channel_tasks.clear()

        if self._outbound_retry_tasks:
            for task in list(self._outbound_retry_tasks):
                task.cancel()
            await asyncio.gather(*list(self._outbound_retry_tasks), return_exceptions=True)
            self._outbound_retry_tasks.clear()

        self._channel_restart_history.clear()

    async def _run_channel_supervisor(self, name: str, channel: BaseChannel) -> None:
        """Run one channel with restart-on-failure supervision."""
        backoff = self._channel_restart_delay_s
        restart_history = self._channel_restart_history.setdefault(name, [])
        while self._running:
            started_at = time.monotonic()
            try:
                await channel.start()
                if not self._running:
                    break
                runtime_s = time.monotonic() - started_at
                if runtime_s >= self._channel_stable_reset_s:
                    backoff = self._channel_restart_delay_s
                logger.warning(
                    f"{name} channel stopped unexpectedly after {runtime_s:.1f}s; "
                    f"restarting in {backoff:.1f}s"
                )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                if not self._running:
                    break
                runtime_s = time.monotonic() - started_at
                if runtime_s >= self._channel_stable_reset_s:
                    backoff = self._channel_restart_delay_s
                logger.error(
                    f"{name} channel crashed after {runtime_s:.1f}s: {exc}; "
                    f"restarting in {backoff:.1f}s"
                )
            finally:
                if self._running:
                    try:
                        await channel.stop()
                    except Exception as stop_exc:
                        logger.debug(f"{name} channel stop hook failed during restart: {stop_exc}")

            if not self._running:
                break

            now = time.monotonic()
            window_floor = now - self._channel_restart_window_s
            restart_history[:] = [stamp for stamp in restart_history if stamp >= window_floor]
            restart_history.append(now)

            if len(restart_history) > self._channel_restart_max_attempts_window:
                logger.error(
                    f"{name} channel restart burst detected "
                    f"({len(restart_history)} restarts / {self._channel_restart_window_s:.0f}s); "
                    f"cooldown {self._channel_restart_cooldown_s:.1f}s"
                )
                await asyncio.sleep(self._channel_restart_cooldown_s)
                backoff = self._channel_restart_delay_s
                continue

            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, self._channel_restart_backoff_max_s)

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
                        self._record_outbound_seen(msg)
                    except Exception as e:
                        logger.error(f"Error sending to {msg.channel}: {e}")
                        self._schedule_outbound_retry(msg, str(e))
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

        return False

    def _record_outbound_seen(self, msg: OutboundMessage) -> None:
        """Record successful outbound idempotency key."""
        key = self._extract_idempotency_key(msg)
        if not key:
            return
        self._outbound_seen[key] = time.time()

    @staticmethod
    def _outbound_attempt(msg: OutboundMessage) -> int:
        """Extract internal dispatch attempt counter from metadata."""
        metadata = msg.metadata if isinstance(msg.metadata, dict) else {}
        raw = metadata.get("_dispatch_attempt", 0)
        try:
            return max(0, int(raw))
        except (TypeError, ValueError):
            return 0

    def _schedule_outbound_retry(self, msg: OutboundMessage, reason: str) -> None:
        """Schedule best-effort outbound retry with capped exponential backoff."""
        attempt = self._outbound_attempt(msg)
        if attempt >= self._outbound_retry_max_attempts:
            logger.error(
                "Dropping outbound message after retries: "
                f"channel={msg.channel}, chat_id={msg.chat_id}, reason={reason}"
            )
            return

        next_attempt = attempt + 1
        delay = min(
            self._outbound_retry_base_delay_s * (2**attempt),
            self._outbound_retry_backoff_max_s,
        )
        metadata = dict(msg.metadata if isinstance(msg.metadata, dict) else {})
        metadata["_dispatch_attempt"] = next_attempt
        retry_msg = OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=msg.content,
            reply_to=msg.reply_to,
            media=list(msg.media),
            metadata=metadata,
        )

        async def _requeue() -> None:
            try:
                await asyncio.sleep(delay)
                await self.bus.publish_outbound(retry_msg)
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.debug(f"Outbound retry scheduling failed: {exc}")

        task = asyncio.create_task(_requeue())
        self._outbound_retry_tasks.add(task)
        task.add_done_callback(lambda done_task: self._outbound_retry_tasks.discard(done_task))
        logger.warning(
            "Retrying outbound message: "
            f"channel={msg.channel}, chat_id={msg.chat_id}, attempt={next_attempt}, "
            f"delay={delay:.1f}s, reason={reason}"
        )

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
