import asyncio
from pathlib import Path
from typing import Any

from g_agent.agent.loop import AgentLoop
from g_agent.agent.memory import MemoryStore
from g_agent.agent.tools.base import Tool
from g_agent.agent.tools.integrations import RecallTool
from g_agent.bus.queue import MessageBus
from g_agent.observability.metrics import MetricsStore
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


class OkTool(Tool):
    @property
    def name(self) -> str:
        return "ok_tool"

    @property
    def description(self) -> str:
        return "Returns ok."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> str:
        return "ok"


def test_metrics_store_snapshot(tmp_path: Path):
    store = MetricsStore(tmp_path / "events.jsonl")
    store.record_llm_call(model="gemini", success=True, latency_ms=800)
    store.record_llm_call(model="gemini", success=False, latency_ms=1200, error="timeout")
    store.record_tool_call(tool="web_search", success=True, latency_ms=300, attempts=1)
    store.record_tool_call(tool="web_search", success=False, latency_ms=900, attempts=2, error="429")
    store.record_recall(query="timezone", hits=1)
    store.record_recall(query="random", hits=0)
    store.record_cron_run(
        name="calendar-watch",
        payload_kind="system_event",
        success=True,
        latency_ms=220,
        delivered=True,
        proactive=True,
    )

    snap = store.snapshot(hours=24)
    assert snap["totals"]["events"] == 7
    assert snap["llm"]["calls"] == 2
    assert snap["tools"]["calls"] == 2
    assert snap["recall"]["queries"] == 2
    assert snap["cron"]["runs"] == 1
    assert snap["tools"]["top_tools"][0]["tool"] == "web_search"


def test_agent_and_recall_record_metrics(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    provider = DummyProvider()
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="dummy-model",
        enable_reflection=False,
    )
    loop.tools.register(OkTool())

    tool_result = asyncio.run(
        loop._execute_tool_with_policy(
            tool_name="ok_tool",
            tool_args={},
            channel="cli",
            sender_id="user",
            approved_tools=set(),
            approve_all=False,
        )
    )
    assert tool_result == "ok"

    response = asyncio.run(
        loop.process_direct(
            content="hello metrics",
            session_key="cli:metrics",
            channel="cli",
            chat_id="metrics",
        )
    )
    assert response == "ok"

    memory = MemoryStore(tmp_path)
    memory.remember_fact("timezone: UTC", category="identity")
    recall_tool = RecallTool(workspace=tmp_path)
    recall_output = asyncio.run(recall_tool.execute(query="timezone"))
    assert "timezone" in recall_output.lower()

    store = MetricsStore(tmp_path / "state" / "metrics" / "events.jsonl")
    snap = store.snapshot(hours=24)
    assert snap["llm"]["calls"] >= 1
    assert snap["tools"]["calls"] >= 1
    assert snap["recall"]["queries"] >= 1
