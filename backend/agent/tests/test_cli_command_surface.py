from __future__ import annotations

import subprocess
import sys

import pytest
from typer.testing import CliRunner

from g_agent import __version__
from g_agent.cli.commands import app

runner = CliRunner()


def test_top_level_without_args_shows_help():
    result = runner.invoke(app, [])
    assert result.exit_code in {0, 2}
    assert "Usage: g-agent" in result.stdout


@pytest.mark.parametrize(
    ("group_name", "expected_help"),
    [
        ("channels", "Manage channels"),
        ("plugins", "Inspect runtime plugins"),
        ("google", "Manage Google Workspace integration"),
        ("cron", "Manage scheduled tasks"),
        ("policy", "Manage tool policy presets"),
    ],
)
def test_group_command_without_subcommand_shows_help(group_name: str, expected_help: str):
    result = runner.invoke(app, [group_name])
    assert result.exit_code == 0
    assert f"Usage: g-agent {group_name}" in result.stdout
    assert expected_help in result.stdout
    assert "Missing command." not in result.stdout


def test_help_alias_forwards_target_to_subprocess(monkeypatch):
    calls: list[dict[str, object]] = []

    def fake_run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess:
        calls.append({"cmd": list(cmd), "check": check})
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["g-agent"])

    result = runner.invoke(app, ["help", "channels"])

    assert result.exit_code == 0
    assert calls == [{"cmd": ["g-agent", "channels", "--help"], "check": False}]


def test_login_alias_forwards_to_channels_login(monkeypatch):
    calls: list[dict[str, object]] = []

    def fake_run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess:
        calls.append({"cmd": list(cmd), "check": check})
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["g-agent"])

    result = runner.invoke(app, ["login"])

    assert result.exit_code == 0
    assert calls == [{"cmd": ["g-agent", "channels", "login"], "check": False}]


def test_version_alias_matches_global_flag_output():
    from_command = runner.invoke(app, ["version"])
    from_flag = runner.invoke(app, ["--version"])

    assert from_command.exit_code == 0
    assert from_flag.exit_code == 0
    assert f"v{__version__}" in from_command.stdout
    assert f"v{__version__}" in from_flag.stdout
