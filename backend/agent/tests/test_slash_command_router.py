"""Tests for chat slash command routing."""

import asyncio
import json
from pathlib import Path

from g_agent.channels.slash_commands import SlashCommandDispatcher
from g_agent.command.context import CommandContext
from g_agent.command.router import CommandRouter
from g_agent.session.manager import SessionManager


def _patch_data_dir(monkeypatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr("g_agent.config.loader.get_data_path", lambda: data_dir)
    monkeypatch.setattr("g_agent.utils.helpers.get_data_path", lambda: data_dir)
    monkeypatch.setattr("g_agent.session.manager.get_data_path", lambda: data_dir)


def test_unknown_slash_command_returns_helpful_response(tmp_path: Path, monkeypatch):
    _patch_data_dir(monkeypatch, tmp_path)
    dispatcher = SlashCommandDispatcher(tmp_path)

    result = asyncio.run(
        dispatcher.try_handle("/does-not-exist", "cli:default", "cli", "default")
    )

    assert result == "⚠️ Unknown command. Try /commands."


def test_command_router_parses_quoted_args_consistently(tmp_path: Path):
    router = CommandRouter()
    seen: dict[str, str] = {}

    async def handler(ctx: CommandContext) -> str:
        seen["args"] = ctx.args
        return "ok"

    router.register("history", handler, aliases=["h"])
    ctx = CommandContext(
        workspace=tmp_path,
        channel="cli",
        chat_id="default",
        session_key="cli:default",
    )

    result = asyncio.run(router.handle('/h "database schema" /tmp/project', ctx))

    assert result == "ok"
    assert seen["args"] == "database schema /tmp/project"


def test_approve_command_passes_through_to_agent_loop(tmp_path: Path, monkeypatch):
    _patch_data_dir(monkeypatch, tmp_path)
    dispatcher = SlashCommandDispatcher(tmp_path)

    result = asyncio.run(
        dispatcher.try_handle("/approve all", "cli:default", "cli", "default")
    )

    assert result is None


def test_slash_history_uses_shared_quoted_arg_parser(tmp_path: Path, monkeypatch):
    _patch_data_dir(monkeypatch, tmp_path)
    manager = SessionManager(tmp_path)
    session = manager.get_or_create("cli:default")
    session.add_message("user", "database schema lives in /tmp/project")
    manager.save(session)

    dispatcher = SlashCommandDispatcher(tmp_path)
    result = asyncio.run(
        dispatcher.try_handle('/history "database schema"', "cli:default", "cli", "default")
    )

    assert "database schema" in result
    assert "No history found" not in result


def test_deny_command_clears_pending_approval(tmp_path: Path, monkeypatch):
    _patch_data_dir(monkeypatch, tmp_path)
    manager = SessionManager(tmp_path)
    session = manager.get_or_create("cli:default")
    session.metadata["pending_approvals"] = [
        {"tool_name": "exec", "tool_args": {"command": "uptime"}},
        {"tool_name": "message", "tool_args": {"text": "hello"}},
    ]
    manager.save(session)

    dispatcher = SlashCommandDispatcher(tmp_path)
    result = asyncio.run(
        dispatcher.try_handle("/deny exec", "cli:default", "cli", "default")
    )

    assert "Denied pending approval" in result
    reloaded = SessionManager(tmp_path).get_or_create("cli:default")
    assert reloaded.metadata["pending_approvals"] == [
        {"tool_name": "message", "tool_args": {"text": "hello"}},
    ]


def test_logs_command_reads_bounded_checkpoint_output(tmp_path: Path, monkeypatch):
    _patch_data_dir(monkeypatch, tmp_path)
    tasks_dir = tmp_path / "state" / "tasks"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "task.json").write_text(
        json.dumps(
            {
                "status": "error",
                "created_at": "2026-04-27T10:30:00",
                "kind": "inbound_message",
                "input_preview": "x" * 200,
                "error": "token=secret-value " + "y" * 200,
            }
        )
    )

    dispatcher = SlashCommandDispatcher(tmp_path)
    result = asyncio.run(dispatcher.try_handle("/logs", "cli:default", "cli", "default"))

    assert "Recent Activity" in result
    assert "inbound_message" in result
    assert "secret-value" not in result
    assert "<redacted>" in result
    assert len(result) < 600
