import asyncio
import json
from collections.abc import Callable

from g_agent.bus.events import OutboundMessage
from g_agent.bus.queue import MessageBus
from g_agent.channels.base import BaseChannel
from g_agent.channels.manager import ChannelManager
from g_agent.channels.telegram import TelegramChannel
from g_agent.channels.whatsapp import WhatsAppChannel
from g_agent.config.schema import Config, TelegramConfig, WhatsAppConfig


class _FakeWsStream:
    def __init__(self, messages: list[str], on_first_message: Callable[[], None] | None = None):
        self._messages = messages
        self._index = 0
        self._on_first_message = on_first_message
        self._emitted_once = False
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        if self._index >= len(self._messages):
            raise StopAsyncIteration
        payload = self._messages[self._index]
        self._index += 1
        if not self._emitted_once and self._on_first_message:
            self._emitted_once = True
            self._on_first_message()
        return payload

    async def close(self) -> None:
        self.closed = True


class _FakeConnectCtx:
    def __init__(self, ws: _FakeWsStream):
        self._ws = ws

    async def __aenter__(self) -> _FakeWsStream:
        return self._ws

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


def test_whatsapp_channel_reconnects_after_bridge_failure(monkeypatch):
    bus = MessageBus()
    channel = WhatsAppChannel(
        config=WhatsAppConfig(enabled=True, bridge_url="ws://local-bridge"),
        bus=bus,
    )

    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr("g_agent.channels.whatsapp.asyncio.sleep", fake_sleep)

    attempts = {"count": 0}
    ws = _FakeWsStream(
        messages=[json.dumps({"type": "status", "status": "connected"})],
        on_first_message=lambda: setattr(channel, "_running", False),
    )

    def fake_connect(url: str):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("bridge unavailable")
        assert url == "ws://local-bridge"
        return _FakeConnectCtx(ws)

    import websockets

    monkeypatch.setattr(websockets, "connect", fake_connect)

    asyncio.run(channel.start())

    assert attempts["count"] == 2
    assert sleep_calls == [5]
    assert channel._connected is True


class _FakeUpdater:
    def __init__(self):
        self.start_polling_calls = 0
        self.stop_calls = 0

    async def start_polling(self, **kwargs) -> None:
        self.start_polling_calls += 1

    async def stop(self) -> None:
        self.stop_calls += 1


class _FakeBot:
    async def get_me(self):
        return type("BotInfo", (), {"username": "g-agent-test-bot"})()


class _FakeTelegramApp:
    def __init__(self, fail_initialize: bool = False):
        self.fail_initialize = fail_initialize
        self.updater = _FakeUpdater()
        self.bot = _FakeBot()
        self.handlers: list[object] = []
        self.start_calls = 0
        self.stop_calls = 0
        self.shutdown_calls = 0

    def add_handler(self, handler: object) -> None:
        self.handlers.append(handler)

    async def initialize(self) -> None:
        if self.fail_initialize:
            raise RuntimeError("init failed")

    async def start(self) -> None:
        self.start_calls += 1

    async def stop(self) -> None:
        self.stop_calls += 1

    async def shutdown(self) -> None:
        self.shutdown_calls += 1


class _FakeApplicationBuilder:
    def __init__(self, apps: list[_FakeTelegramApp]):
        self._apps = apps
        self.build_calls = 0

    def token(self, _value: str):
        return self

    def connect_timeout(self, _value: float):
        return self

    def read_timeout(self, _value: float):
        return self

    def write_timeout(self, _value: float):
        return self

    def pool_timeout(self, _value: float):
        return self

    def get_updates_connect_timeout(self, _value: float):
        return self

    def get_updates_read_timeout(self, _value: float):
        return self

    def get_updates_write_timeout(self, _value: float):
        return self

    def get_updates_pool_timeout(self, _value: float):
        return self

    def proxy(self, _value: str):
        return self

    def get_updates_proxy(self, _value: str):
        return self

    def build(self) -> _FakeTelegramApp:
        app = self._apps[self.build_calls]
        self.build_calls += 1
        return app


class _FakeApplicationFactory:
    builder_instance: _FakeApplicationBuilder | None = None

    @classmethod
    def builder(cls) -> _FakeApplicationBuilder:
        assert cls.builder_instance is not None
        return cls.builder_instance


def test_telegram_channel_reconnects_after_startup_error(monkeypatch):
    bus = MessageBus()
    channel = TelegramChannel(
        config=TelegramConfig(enabled=True, token="token-123"),
        bus=bus,
    )

    first_app = _FakeTelegramApp(fail_initialize=True)
    second_app = _FakeTelegramApp(fail_initialize=False)
    builder = _FakeApplicationBuilder([first_app, second_app])
    _FakeApplicationFactory.builder_instance = builder
    monkeypatch.setattr("g_agent.channels.telegram.Application", _FakeApplicationFactory)

    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)
        if seconds == 1:
            channel._running = False

    monkeypatch.setattr("g_agent.channels.telegram.asyncio.sleep", fake_sleep)

    asyncio.run(channel.start())

    assert builder.build_calls == 2
    assert sleep_calls == [5, 1]
    assert first_app.updater.stop_calls == 1
    assert first_app.stop_calls == 1
    assert first_app.shutdown_calls == 1
    assert second_app.start_calls == 1
    assert second_app.updater.start_polling_calls == 1
    assert channel.is_running is False


async def _wait_until(condition: Callable[[], bool], timeout_s: float = 1.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_s
    while not condition():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("Condition not met within timeout")
        await asyncio.sleep(0.01)


class _HarnessChannel(BaseChannel):
    name = "harness"

    def __init__(
        self,
        *,
        name: str,
        bus: MessageBus,
        failures_before_connect: int = 0,
        drop_once_after_connect: bool = False,
    ):
        super().__init__(config=type("Cfg", (), {"allow_from": []})(), bus=bus)
        self.name = name
        self.failures_before_connect = max(0, int(failures_before_connect))
        self.drop_once_after_connect = bool(drop_once_after_connect)
        self.start_attempts = 0
        self.connect_cycles = 0
        self.connected = False
        self.sent: list[OutboundMessage] = []

    async def start(self) -> None:
        self._running = True
        dropped_once = False

        while self._running:
            self.start_attempts += 1
            if self.start_attempts <= self.failures_before_connect:
                await asyncio.sleep(0.01)
                continue

            self.connected = True
            self.connect_cycles += 1

            if self.drop_once_after_connect and not dropped_once:
                dropped_once = True
                await asyncio.sleep(0.01)
                self.connected = False
                continue

            while self._running and self.connected:
                await asyncio.sleep(0.01)

            self.connected = False

    async def stop(self) -> None:
        self._running = False
        self.connected = False

    async def send(self, msg: OutboundMessage) -> None:
        if not self.connected:
            raise RuntimeError(f"{self.name} disconnected")
        self.sent.append(msg)


def test_channel_manager_integration_reconnect_harness_dispatches_after_recovery():
    async def run_case() -> None:
        bus = MessageBus()
        config = Config()
        manager = ChannelManager(config, bus)
        telegram_channel = _HarnessChannel(
            name="telegram",
            bus=bus,
            failures_before_connect=1,
        )
        whatsapp_channel = _HarnessChannel(
            name="whatsapp",
            bus=bus,
            failures_before_connect=1,
            drop_once_after_connect=True,
        )
        manager.channels = {
            "telegram": telegram_channel,
            "whatsapp": whatsapp_channel,
        }

        start_task = asyncio.create_task(manager.start_all())
        await _wait_until(
            lambda: telegram_channel.connected and whatsapp_channel.connect_cycles >= 2,
            timeout_s=2.0,
        )
        await _wait_until(lambda: whatsapp_channel.connected, timeout_s=1.0)

        assert telegram_channel.start_attempts >= 2
        assert whatsapp_channel.start_attempts >= 3

        await bus.publish_outbound(
            OutboundMessage(channel="telegram", chat_id="tg-1", content="ping-telegram")
        )
        await bus.publish_outbound(
            OutboundMessage(channel="whatsapp", chat_id="wa-1", content="ping-whatsapp")
        )

        await _wait_until(
            lambda: len(telegram_channel.sent) == 1 and len(whatsapp_channel.sent) == 1,
            timeout_s=1.0,
        )

        await manager.stop_all()
        await asyncio.wait_for(start_task, timeout=1.0)

        assert telegram_channel.is_running is False
        assert whatsapp_channel.is_running is False
        assert telegram_channel.connected is False
        assert whatsapp_channel.connected is False

    asyncio.run(run_case())
