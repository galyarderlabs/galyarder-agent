import asyncio
import json
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
    store.record_tool_call(
        tool="web_search", success=False, latency_ms=900, attempts=2, error="429"
    )
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


def test_metrics_store_dashboard_and_export(tmp_path: Path):
    store = MetricsStore(tmp_path / "events.jsonl")
    store.record_llm_call(model="gemini-3", success=True, latency_ms=450)
    store.record_tool_call(
        tool='web_search"prod"', success=False, latency_ms=700, attempts=2, error="429"
    )
    store.record_recall(query="timezone", hits=2)
    store.record_cron_run(
        name="daily-digest",
        payload_kind="digest",
        success=True,
        latency_ms=180,
        delivered=True,
        proactive=True,
    )

    dashboard = store.dashboard_summary(hours=24, top_n_tools=3)
    assert dashboard["events_total"] == 4
    assert dashboard["llm_calls"] == 1
    assert dashboard["tool_calls"] == 1
    assert dashboard["top_tool_1_name"] == 'web_search"prod"'

    json_path = tmp_path / "exports" / "metrics.json"
    result_json = store.export_snapshot(json_path, hours=24)
    assert result_json["ok"] is True
    assert result_json["format"] == "json"
    exported_json = json.loads(json_path.read_text(encoding="utf-8"))
    assert exported_json["llm"]["calls"] == 1

    dashboard_path = tmp_path / "exports" / "metrics.dashboard.json"
    result_dashboard = store.export_snapshot(dashboard_path, hours=24)
    assert result_dashboard["ok"] is True
    assert result_dashboard["format"] == "dashboard_json"
    exported_dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    assert exported_dashboard["tool_calls"] == 1
    assert exported_dashboard["cron_runs"] == 1

    prom_path = tmp_path / "exports" / "metrics.prom"
    result_prom = store.export_snapshot(prom_path, hours=24)
    assert result_prom["ok"] is True
    assert result_prom["format"] == "prometheus"
    prom_text = prom_path.read_text(encoding="utf-8")
    assert "g_agent_llm_calls_total 1" in prom_text
    assert 'g_agent_top_tool_calls{tool="web_search\\"prod\\""} 1' in prom_text


def test_metrics_store_export_rejects_unknown_format(tmp_path: Path):
    store = MetricsStore(tmp_path / "events.jsonl")
    result = store.export_snapshot(
        tmp_path / "exports" / "metrics.unknown",
        hours=24,
        output_format="yaml",
    )
    assert result["ok"] is False
    assert "Unknown output format" in result["error"]
