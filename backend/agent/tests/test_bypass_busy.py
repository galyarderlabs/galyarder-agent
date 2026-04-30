import pytest
from pathlib import Path
from g_agent.agent.loop import AgentLoop
from g_agent.bus.queue import MessageBus, InboundMessage
from g_agent.providers.base import LLMProvider, LLMResponse
from g_agent.agent.runtime import TaskCheckpointStore

class DummyProvider(LLMProvider):
    async def chat(self, messages, tools=None, model=None, **kwargs):
        return LLMResponse(content="pong")
    def get_default_model(self) -> str:
        return "dummy"

@pytest.mark.asyncio
async def test_bypass_busy_requires_explicit_metadata(tmp_path: Path, monkeypatch):
    """Direct/API paths should NOT bypass busy by default."""
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    bus = MessageBus()
    loop = AgentLoop(
        bus=bus,
        provider=DummyProvider(),
        workspace=tmp_path,
        enable_reflection=False,
    )

    # 1. Start a "running" task manually to make the session busy
    store = TaskCheckpointStore(tmp_path)
    store.start(
        kind="inbound_message",
        session_key="cli:test",
        channel="cli",
        chat_id="test",
        sender_id="user",
        input_text="busy work",
    )

    # 2. Try to process a message normally (should be blocked)
    msg_blocked = InboundMessage(
        channel="cli",
        chat_id="test",
        sender_id="user",
        content="this should be blocked",
    )
    resp_blocked = await loop._process_message(msg_blocked)
    assert resp_blocked is not None
    assert "Sabar ya" in resp_blocked.content
    assert resp_blocked.metadata.get("is_busy_notice") is True

    # 3. Try process_direct without bypass (should also be blocked)
    result_blocked = await loop.process_direct(
        content="ping without bypass",
        session_key="cli:test",
    )
    assert "Sabar ya" in result_blocked

    # 4. Try with explicit bypass_busy=True (should work)
    result_bypass = await loop.process_direct(
        content="ping with bypass",
        session_key="cli:test",
        metadata={"bypass_busy": True},
    )
    assert result_bypass == "pong"

    await loop.shutdown()


@pytest.mark.asyncio
async def test_routine_runner_bypasses_busy(tmp_path: Path, monkeypatch):
    """Routine runner should set bypass_busy=True explicitly."""
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    bus = MessageBus()
    loop = AgentLoop(
        bus=bus,
        provider=DummyProvider(),
        workspace=tmp_path,
        enable_reflection=False,
    )

    # Make session busy
    store = TaskCheckpointStore(tmp_path)
    store.start(
        kind="inbound_message",
        session_key="cli:routine",
        channel="cli",
        chat_id="routine",
        sender_id="system-routine",
        input_text="busy",
    )

    # Simulate routine runner message with bypass_busy=True
    msg_routine = InboundMessage(
        channel="cli",
        chat_id="routine",
        sender_id="system-routine",
        content="routine task",
        metadata={"bypass_busy": True, "routine_id": "test-routine"},
    )

    resp = await loop._process_message(msg_routine)
    assert resp is not None
    assert "Sabar ya" not in resp.content
    assert resp.content == "pong"

    await loop.shutdown()
