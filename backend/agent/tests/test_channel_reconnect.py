import asyncio
import json
from collections.abc import Callable

from g_agent.bus.queue import MessageBus
from g_agent.channels.telegram import TelegramChannel
from g_agent.channels.whatsapp import WhatsAppChannel
from g_agent.config.schema import TelegramConfig, WhatsAppConfig


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
