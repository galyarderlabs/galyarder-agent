"""Test cases for the G-Agent InsightsEngine."""

import asyncio
from pathlib import Path

from g_agent.channels.slash_commands import SlashCommandDispatcher
from g_agent.observability.insights import InsightsEngine
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
                        "arguments": {"command": "ls"}
                    }
                }
            ]
        }
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
    assert overview["total_tool_calls"] == 0  # tool_calls in sessions table are updated separately in real usage
    
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
