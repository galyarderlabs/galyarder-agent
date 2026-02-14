"""Tests for session archive and /new command."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from g_agent.cli.commands import app
from g_agent.session.manager import SessionManager

runner = CliRunner()


def _make_session_manager(tmp_path: Path) -> SessionManager:
    """Create a SessionManager with tmp_path as data directory."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    sm = SessionManager(workspace)
    sm.sessions_dir = tmp_path / "sessions"
    sm.sessions_dir.mkdir(parents=True, exist_ok=True)
    return sm


def _write_session(sm: SessionManager, key: str, content: str = "hello") -> None:
    """Write a minimal session file."""
    from g_agent.session.manager import Session

    session = Session(key=key)
    session.add_message("user", content)
    sm.save(session)


# ── SessionManager.archive() tests ───────────────────────────────────


def test_archive_creates_copy_and_deletes_original(tmp_path):
    sm = _make_session_manager(tmp_path)
    _write_session(sm, "cli:default")

    original = sm._get_session_path("cli:default")
    assert original.exists()

    result = sm.archive("cli:default")
    assert result is True
    assert not original.exists()

    archive_dir = sm.sessions_dir / "archive"
    archived = list(archive_dir.glob("cli_default_*.jsonl"))
    assert len(archived) == 1


def test_archive_nonexistent_returns_false(tmp_path):
    sm = _make_session_manager(tmp_path)
    assert sm.archive("nonexistent:key") is False


def test_archive_all_handles_multiple_sessions(tmp_path):
    sm = _make_session_manager(tmp_path)
    _write_session(sm, "cli:default")
    _write_session(sm, "whatsapp:123")
    _write_session(sm, "telegram:456")

    count = sm.archive_all()
    assert count == 3

    archive_dir = sm.sessions_dir / "archive"
    assert len(list(archive_dir.glob("*.jsonl"))) == 3


# ── `new` command CLI tests ──────────────────────────────────────────


def _patch_session_env(monkeypatch, tmp_path: Path) -> SessionManager:
    """Patch data path so CLI commands use tmp_path for sessions."""
    data_dir = tmp_path / "g-agent"
    data_dir.mkdir()
    monkeypatch.setattr("g_agent.config.loader.get_data_path", lambda: data_dir)
    monkeypatch.setattr("g_agent.utils.helpers.get_data_path", lambda: data_dir)
    monkeypatch.setattr("g_agent.session.manager.get_data_path", lambda: data_dir)

    workspace = data_dir / "workspace"
    workspace.mkdir()

    # Write minimal config
    config_file = data_dir / "config.json"
    config_file.write_text(json.dumps({}))

    sm = SessionManager(workspace)
    return sm


def test_new_command_no_sessions_graceful_exit(tmp_path, monkeypatch):
    _patch_session_env(monkeypatch, tmp_path)
    result = runner.invoke(app, ["new", "--yes"])
    assert result.exit_code == 0
    assert "No sessions found" in result.stdout


def test_new_command_clears_cli_default(tmp_path, monkeypatch):
    sm = _patch_session_env(monkeypatch, tmp_path)
    _write_session(sm, "cli:default")

    result = runner.invoke(app, ["new", "--yes"])
    assert result.exit_code == 0
    assert "Archived 1 session" in result.stdout

    # Original deleted
    assert not sm._get_session_path("cli:default").exists()
    # Archive exists
    archive_dir = sm.sessions_dir / "archive"
    assert len(list(archive_dir.glob("*.jsonl"))) == 1


def test_new_command_channel_filter(tmp_path, monkeypatch):
    sm = _patch_session_env(monkeypatch, tmp_path)
    _write_session(sm, "cli:default")
    _write_session(sm, "whatsapp:123")
    _write_session(sm, "whatsapp:456")

    result = runner.invoke(app, ["new", "--channel", "whatsapp", "--yes"])
    assert result.exit_code == 0
    assert "2 session" in result.stdout

    # cli:default should still exist
    assert sm._get_session_path("cli:default").exists()


def test_new_command_all_flag(tmp_path, monkeypatch):
    sm = _patch_session_env(monkeypatch, tmp_path)
    _write_session(sm, "cli:default")
    _write_session(sm, "whatsapp:123")

    result = runner.invoke(app, ["new", "--all", "--yes"])
    assert result.exit_code == 0
    assert "2 session" in result.stdout


def test_new_command_no_archive_deletes_directly(tmp_path, monkeypatch):
    sm = _patch_session_env(monkeypatch, tmp_path)
    _write_session(sm, "cli:default")

    result = runner.invoke(app, ["new", "--no-archive", "--yes"])
    assert result.exit_code == 0
    assert "Cleared 1 session" in result.stdout

    # No archive directory should exist
    archive_dir = sm.sessions_dir / "archive"
    assert not archive_dir.exists() or len(list(archive_dir.glob("*.jsonl"))) == 0
