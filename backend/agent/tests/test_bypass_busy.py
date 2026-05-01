from datetime import timedelta
from pathlib import Path

import pytest

from g_agent.agent.loop import AgentLoop
from g_agent.agent.runtime import TaskCheckpointStore
from g_agent.bus.queue import InboundMessage, MessageBus
from g_agent.providers.base import LLMProvider, LLMResponse

class DummyProvider(LLMProvider):
    def __init__(self, responses: list[LLMResponse] | None = None):
        super().__init__(api_key=None, api_base=None)
        self._responses = list(responses or [])

    async def chat(self, messages, tools=None, model=None, **kwargs):
        if self._responses:
            return self._responses.pop(0)
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
async def test_approval_intent_bypasses_busy_guard_for_pending_tool(
    tmp_path: Path, monkeypatch
):
    """Approval follow-ups should replay pending calls even while a task is running."""
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    bus = MessageBus()
    loop = AgentLoop(
        bus=bus,
        provider=DummyProvider(),
        workspace=tmp_path,
        enable_reflection=False,
        approval_mode="confirm",
        risky_tools=["write_file"],
    )
    session = loop.sessions.get_or_create("whatsapp:thread-approval")
    loop._store_pending_approval(
        session,
        "write_file",
        {"path": str(tmp_path / "note.txt"), "content": "ok"},
    )
    loop.runtime.start(
        kind="inbound_message",
        session_key="whatsapp:thread-approval",
        channel="whatsapp",
        chat_id="thread-approval",
        sender_id="user",
        input_text="pending write",
    )

    async def _fake_execute(name, args):
        assert name == "write_file"
        return "File written successfully"

    loop.tools.execute = _fake_execute
    loop.provider = DummyProvider(responses=[LLMResponse(content="izin write_file sudah dijalankan")])

    msg = InboundMessage(
        channel="whatsapp",
        chat_id="thread-approval",
        sender_id="user",
        content="approve write_file",
    )
    resp = await loop._process_message(msg)

    assert resp is not None
    assert "Sabar ya" not in resp.content
    assert "Approval executed" in resp.content
    assert "write_file" in resp.content
    assert "File written successfully" in resp.content
    session = loop.sessions.get_or_create("whatsapp:thread-approval")
    assert session.metadata.get("pending_approvals") == []
    assert loop.runtime.latest_running_for_session("whatsapp:thread-approval") is None

    await loop.shutdown()


@pytest.mark.asyncio
async def test_slash_approve_replays_first_pending_tool_without_llm(
    tmp_path: Path, monkeypatch
):
    """Bare /approve should execute the oldest pending approval directly."""
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    bus = MessageBus()
    loop = AgentLoop(
        bus=bus,
        provider=DummyProvider(responses=[LLMResponse(content="should not be used")]),
        workspace=tmp_path,
        enable_reflection=False,
        approval_mode="confirm",
        risky_tools=["docs_append_text"],
    )
    session = loop.sessions.get_or_create("telegram:thread-approval")
    loop._store_pending_approval(
        session,
        "docs_append_text",
        {"document_id": "catatan_keiya", "text": "ok"},
    )
    loop.runtime.start(
        kind="inbound_message",
        session_key="telegram:thread-approval",
        channel="telegram",
        chat_id="thread-approval",
        sender_id="user",
        input_text="pending docs write",
    )

    async def _fake_execute(name, args):
        assert name == "docs_append_text"
        return "Document updated"

    loop.tools.execute = _fake_execute

    msg = InboundMessage(
        channel="telegram",
        chat_id="thread-approval",
        sender_id="user",
        content="/approve",
    )
    resp = await loop._process_message(msg)

    assert resp is not None
    assert "Approval executed" in resp.content
    assert "docs_append_text" in resp.content
    assert "Document updated" in resp.content
    assert "should not be used" not in resp.content
    session = loop.sessions.get_or_create("telegram:thread-approval")
    assert session.metadata.get("pending_approvals") == []
    assert loop.runtime.latest_running_for_session("telegram:thread-approval") is None

    await loop.shutdown()


@pytest.mark.asyncio
async def test_stale_running_task_does_not_block_channel_session(
    tmp_path: Path, monkeypatch
):
    """Old running checkpoints should be marked stale instead of blocking forever."""
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    bus = MessageBus()
    loop = AgentLoop(
        bus=bus,
        provider=DummyProvider(),
        workspace=tmp_path,
        enable_reflection=False,
    )
    loop.runtime = TaskCheckpointStore(tmp_path, stale_after=timedelta(seconds=0))

    stale_task_id = loop.runtime.start(
        kind="inbound_message",
        session_key="whatsapp:thread-1",
        channel="whatsapp",
        chat_id="thread-1",
        sender_id="user",
        input_text="old work",
    )

    msg = InboundMessage(
        channel="whatsapp",
        chat_id="thread-1",
        sender_id="user",
        content="oi",
    )
    resp = await loop._process_message(msg)

    assert resp is not None
    assert resp.content == "pong"
    stale_payload = loop.runtime.get(stale_task_id)
    assert stale_payload is not None
    assert stale_payload["status"] == "stale"
    assert stale_payload["events"][-1]["event"] == "stale"
    assert loop.runtime.latest_running_for_session("whatsapp:thread-1") is None

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
