import asyncio
from typing import Any

from g_agent.agent.loop import AgentLoop
from g_agent.agent.tools.base import Tool
from g_agent.bus.events import OutboundMessage
from g_agent.bus.queue import MessageBus
from g_agent.channels.base import BaseChannel
from g_agent.channels.manager import ChannelManager
from g_agent.config.schema import Config
from g_agent.providers.base import LLMProvider, LLMResponse


class DummyProvider(LLMProvider):
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        return LLMResponse(content="ok")

    def get_default_model(self) -> str:
        return "dummy-model"


class FlakyTool(Tool):
    def __init__(self, fail_count: int, error_text: str):
        self.fail_count = fail_count
        self.error_text = error_text
        self.calls = 0

    @property
    def name(self) -> str:
        return "flaky_tool"

    @property
    def description(self) -> str:
        return "flaky test tool"

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> str:
        self.calls += 1
        if self.calls <= self.fail_count:
            return self.error_text
        return "ok"


class StubChannel(BaseChannel):
    name = "stub"

    def __init__(self, bus: MessageBus):
        super().__init__(config=type("StubConfig", (), {"allow_from": []})(), bus=bus)
        self.sent: list[OutboundMessage] = []

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        self.sent.append(msg)


def test_retry_network_error(tmp_path, monkeypatch):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    loop = AgentLoop(
        bus=MessageBus(),
        provider=DummyProvider(),
        workspace=tmp_path,
        enable_reflection=False,
    )
    flaky = FlakyTool(fail_count=2, error_text="Error: timed out")
    loop.tools.register(flaky)

    result = asyncio.run(
        loop._execute_tool_with_policy(
            tool_name="flaky_tool",
            tool_args={},
            channel="cli",
            sender_id="user",
            approved_tools=set(),
            approve_all=False,
        )
    )

    assert result == "ok"
    assert flaky.calls == 3


def test_retry_auth_error_stops_after_policy_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    loop = AgentLoop(
        bus=MessageBus(),
        provider=DummyProvider(),
        workspace=tmp_path,
        enable_reflection=False,
    )
    flaky = FlakyTool(fail_count=3, error_text="Error: 401 unauthorized")
    loop.tools.register(flaky)

    result = asyncio.run(
        loop._execute_tool_with_policy(
            tool_name="flaky_tool",
            tool_args={},
            channel="cli",
            sender_id="user",
            approved_tools=set(),
            approve_all=False,
        )
    )

    assert "401 unauthorized" in result
    assert flaky.calls == 2


def test_outbound_idempotency_skips_duplicate():
    config = Config()
    bus = MessageBus()
    manager = ChannelManager(config, bus)
    stub = StubChannel(bus)
    manager.channels = {"stub": stub}

    async def run_case() -> None:
        dispatch_task = asyncio.create_task(manager._dispatch_outbound())
        await bus.publish_outbound(
            OutboundMessage(
                channel="stub",
                chat_id="1",
                content="hello",
                metadata={"idempotency_key": "k-1"},
            )
        )
        await bus.publish_outbound(
            OutboundMessage(
                channel="stub",
                chat_id="1",
                content="hello-again",
                metadata={"idempotency_key": "k-1"},
            )
        )
        await asyncio.sleep(0.15)
        dispatch_task.cancel()
        try:
            await dispatch_task
        except asyncio.CancelledError:
            pass

    asyncio.run(run_case())
    assert len(stub.sent) == 1
    assert stub.sent[0].content == "hello"


def test_outbound_without_idempotency_key_not_deduped():
    config = Config()
    bus = MessageBus()
    manager = ChannelManager(config, bus)
    stub = StubChannel(bus)
    manager.channels = {"stub": stub}

    async def run_case() -> None:
        dispatch_task = asyncio.create_task(manager._dispatch_outbound())
        await bus.publish_outbound(OutboundMessage(channel="stub", chat_id="1", content="a"))
        await bus.publish_outbound(OutboundMessage(channel="stub", chat_id="1", content="a"))
        await asyncio.sleep(0.15)
        dispatch_task.cancel()
        try:
            await dispatch_task
        except asyncio.CancelledError:
            pass

    asyncio.run(run_case())
    assert len(stub.sent) == 2
