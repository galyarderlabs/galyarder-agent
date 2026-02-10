import asyncio
import json
from pathlib import Path

import pytest

from g_agent.agent.loop import AgentLoop
from g_agent.agent.runtime import TaskCheckpointStore
from g_agent.bus.queue import MessageBus
from g_agent.providers.base import LLMProvider, LLMResponse


class DummyProvider(LLMProvider):
    def __init__(self, responses: list[LLMResponse] | None = None, error: Exception | None = None):
        super().__init__(api_key=None, api_base=None)
        self._responses = list(responses or [])
        self._error = error

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        if self._error is not None:
            raise self._error
        if self._responses:
            return self._responses.pop(0)
        return LLMResponse(content="ok")

    def get_default_model(self) -> str:
        return "dummy-model"


def _load_checkpoint_files(tasks_dir: Path) -> list[dict]:
    items = []
    for path in sorted(tasks_dir.glob("*.json")):
        items.append(json.loads(path.read_text(encoding="utf-8")))
    return items


def test_checkpoint_store_lifecycle(tmp_path: Path):
    store = TaskCheckpointStore(tmp_path)
    task_id = store.start(
        kind="test",
        session_key="cli:test",
        channel="cli",
        chat_id="test",
        sender_id="user",
        input_text="hello world",
    )
    assert task_id

    assert store.append_event(task_id, "step", "running step")
    assert store.complete(task_id, "done", metadata={"iterations": 1})

    payload = store.get(task_id)
    assert payload is not None
    assert payload["status"] == "ok"
    assert payload["metadata"]["iterations"] == 1
    assert payload["events"][-1]["event"] == "complete"


def test_agent_loop_writes_success_checkpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    provider = DummyProvider(responses=[LLMResponse(content="pong")])
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="dummy-model",
        max_iterations=3,
        enable_reflection=False,
    )

    result = asyncio.run(
        loop.process_direct(
            content="ping",
            session_key="cli:ok",
            channel="cli",
            chat_id="ok",
        )
    )
    assert result == "pong"

    checkpoints = _load_checkpoint_files(tmp_path / "state" / "tasks")
    assert len(checkpoints) == 1
    checkpoint = checkpoints[0]
    assert checkpoint["status"] == "ok"
    assert checkpoint["session_key"] == "cli:ok"
    assert checkpoint["metadata"]["iterations"] == 1


def test_agent_loop_writes_error_checkpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    provider = DummyProvider(error=RuntimeError("provider failed"))
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="dummy-model",
        max_iterations=2,
        enable_reflection=False,
    )

    with pytest.raises(RuntimeError, match="provider failed"):
        asyncio.run(
            loop.process_direct(
                content="trigger error",
                session_key="cli:err",
                channel="cli",
                chat_id="err",
            )
        )

    checkpoints = _load_checkpoint_files(tmp_path / "state" / "tasks")
    assert len(checkpoints) == 1
    checkpoint = checkpoints[0]
    assert checkpoint["status"] == "error"
    assert "provider failed" in checkpoint["error"]


def test_agent_loop_marks_previous_running_as_resumed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    store = TaskCheckpointStore(tmp_path)
    old_task_id = store.start(
        kind="inbound_message",
        session_key="cli:resume",
        channel="cli",
        chat_id="resume",
        sender_id="user",
        input_text="unfinished",
    )

    provider = DummyProvider(responses=[LLMResponse(content="done now")])
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="dummy-model",
        max_iterations=2,
        enable_reflection=False,
    )

    result = asyncio.run(
        loop.process_direct(
            content="continue",
            session_key="cli:resume",
            channel="cli",
            chat_id="resume",
        )
    )
    assert result == "done now"

    old_payload = store.get(old_task_id)
    assert old_payload is not None
    assert old_payload["metadata"]["resume_count"] == 1
    assert old_payload["events"][-1]["event"] == "resume"
