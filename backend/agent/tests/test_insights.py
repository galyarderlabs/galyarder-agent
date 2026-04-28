"""Test cases for the G-Agent InsightsEngine."""

import asyncio
import json
from pathlib import Path

from g_agent.channels.slash_commands import SlashCommandDispatcher
from g_agent.observability.insights import InsightsEngine
from g_agent.observability.metrics import MetricsStore
from g_agent.session.sqlite_store import SessionSQLiteStore


def _patch_data_dir(monkeypatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr("g_agent.config.loader.get_data_path", lambda: data_dir)
    monkeypatch.setattr("g_agent.utils.helpers.get_data_path", lambda: data_dir)
    monkeypatch.setattr("g_agent.session.manager.get_data_path", lambda: data_dir)


def test_insights_engine_empty_db(tmp_path: Path):
    store = SessionSQLiteStore(tmp_path / "sessions.db")
    engine = InsightsEngine(store)
    report = engine.generate(days=30)

    assert report["empty"] is True
    assert report["days"] == 30
    assert report["source_filter"] is None


def test_insights_engine_generates_report(tmp_path: Path):
    store = SessionSQLiteStore(tmp_path / "sessions.db")

    # Create session 1
    s1 = store.get_or_create_session("cli:default")
    store.append_message(s1["id"], "user", "run a command", input_tokens=10)
    store.append_message(
        s1["id"],
        "assistant",
        "done",
        output_tokens=20,
        model="gpt-4o",
        metadata={
            "tool_calls": [
                {
                    "function": {
                        "name": "exec",
                        "arguments": {"command": "ls"},
                    }
                }
            ]
        },
    )

    # Create session 2
    s2 = store.get_or_create_session("telegram:123")
    store.append_message(s2["id"], "user", "hello", input_tokens=5)
    store.append_message(s2["id"], "assistant", "hi", output_tokens=10, model="claude-3-haiku")

    engine = InsightsEngine(store)
    report = engine.generate(days=30)

    assert report["empty"] is False

    # Overview
    overview = report["overview"]
    assert overview["total_sessions"] == 2
    assert overview["total_messages"] == 4
    assert overview["total_input_tokens"] == 15
    assert overview["total_output_tokens"] == 30
    assert overview["total_tokens"] == 45
    assert overview["total_tool_calls"] == 0

    # Models
    models = {m["model"]: m for m in report["models"]}
    assert "gpt-4o" in models
    assert models["gpt-4o"]["total_tokens"] == 30
    assert "claude-3-haiku" in models
    assert models["claude-3-haiku"]["total_tokens"] == 15

    # Platforms
    platforms = {p["platform"]: p for p in report["platforms"]}
    assert "cli" in platforms
    assert "telegram" in platforms

    # Tools
    tools = {t["tool"]: t for t in report["tools"]}
    assert "exec" in tools
    assert tools["exec"]["count"] == 1

    # Formatting
    terminal_output = engine.format_gateway(report)
    assert "G-Agent Insights" in terminal_output
    assert "gpt-4o" in terminal_output
    assert "claude-3-haiku" in terminal_output
    assert "telegram" in terminal_output
    assert "exec" in terminal_output


def test_slash_insights_routes_through_shared_command_router(tmp_path: Path, monkeypatch):
    _patch_data_dir(monkeypatch, tmp_path)
    dispatcher = SlashCommandDispatcher(tmp_path)

    result = asyncio.run(dispatcher.try_handle("/insights 7", "cli:default", "cli", "default"))

    assert result == "No sessions found in the last 7 days."


def test_insights_engine_reports_provider_failures_and_skill_usage(tmp_path: Path):
    store = SessionSQLiteStore(tmp_path / "sessions.db")
    session = store.get_or_create_session("cli:default")
    store.append_message(session["id"], "user", "use a skill")
    store.append_message(
        session["id"],
        "assistant",
        "loaded",
        metadata={
            "tool_calls": [
                {
                    "tool_name": "skill_view",
                    "arguments": {"name": "release"},
                },
                {
                    "function": {
                        "name": "skill_manage",
                        "arguments": json.dumps({"name": "release"}),
                    }
                },
            ]
        },
    )

    metrics = MetricsStore(tmp_path / "state" / "metrics" / "events.jsonl")
    metrics.record_llm_call(model="openai/gpt-4o", success=True, latency_ms=100)
    metrics.record_llm_call(
        model="gemini-3-pro",
        success=False,
        latency_ms=300,
        error="quota",
    )
    metrics.record_tool_call(tool="exec", success=False, latency_ms=50, error="denied")
    (tmp_path / "state" / "metrics" / "events.jsonl").write_text(
        (tmp_path / "state" / "metrics" / "events.jsonl").read_text(encoding="utf-8")
        + "{bad json\n",
        encoding="utf-8",
    )

    engine = InsightsEngine(store, workspace=tmp_path)
    report = engine.generate(days=30)

    providers = {item["provider"]: item for item in report["providers"]}
    assert providers["openai"]["calls"] == 1
    assert providers["gemini-3-pro"]["errors"] == 1

    failed_targets = {item["target"] for item in report["failed_calls"]}
    assert "gemini-3-pro" in failed_targets
    assert "exec" in failed_targets

    skills = report["skills"]
    assert skills["summary"]["total_skill_loads"] == 1
    assert skills["summary"]["total_skill_edits"] == 1
    assert skills["top_skills"][0]["skill"] == "release"

    output = engine.format_gateway(report)
    assert "Providers" in output
    assert "Top Skills" in output
    assert "Recent Failed Calls" in output
