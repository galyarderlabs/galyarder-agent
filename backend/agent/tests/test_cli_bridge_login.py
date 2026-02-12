from __future__ import annotations

import subprocess
from pathlib import Path

from typer.testing import CliRunner

from g_agent.cli.commands import app
from g_agent.config.loader import save_config
from g_agent.config.schema import Config

runner = CliRunner()


def test_channels_login_passes_bridge_env_from_config(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(data_dir))

    config = Config()
    config.channels.whatsapp.bridge_url = "ws://127.0.0.1:3456"
    save_config(config)

    fake_bridge_dir = tmp_path / "bridge"
    fake_bridge_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("g_agent.cli.commands._bridge_port_pids", lambda _port: [])
    monkeypatch.setattr("g_agent.cli.commands._is_bridge_port_in_use", lambda *_args, **_kwargs: False)
    monkeypatch.setattr("g_agent.cli.commands._bridge_bind_error", lambda _port: None)
    monkeypatch.setattr("g_agent.cli.commands._get_bridge_dir", lambda force_rebuild=False: fake_bridge_dir)

    calls: list[dict[str, object]] = []

    def fake_run(
        cmd: list[str],
        cwd: Path | None = None,
        check: bool = False,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess:
        calls.append(
            {
                "cmd": list(cmd),
                "cwd": cwd,
                "check": check,
                "env": dict(env or {}),
            }
        )
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("subprocess.run", fake_run)

    result = runner.invoke(app, ["channels", "login"])

    assert result.exit_code == 0
    assert calls and calls[0]["cmd"] == ["npm", "start"]
    assert calls[0]["cwd"] == fake_bridge_dir
    assert calls[0]["check"] is True
    env = calls[0]["env"]
    assert env["BRIDGE_PORT"] == "3456"
    assert env["AUTH_DIR"] == str(data_dir / "whatsapp-auth")


def test_channels_login_restart_existing_stops_listener_then_starts(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(data_dir))

    config = Config()
    config.channels.whatsapp.bridge_url = "ws://127.0.0.1:4567"
    save_config(config)

    fake_bridge_dir = tmp_path / "bridge"
    fake_bridge_dir.mkdir(parents=True, exist_ok=True)

    calls_state = {"pids_checks": 0}

    def fake_bridge_port_pids(_port: int) -> list[str]:
        calls_state["pids_checks"] += 1
        if calls_state["pids_checks"] == 1:
            return ["1111"]
        return []

    stop_calls: list[dict[str, object]] = []

    def fake_stop_bridge_processes(port: int, pids: list[str], *, timeout_seconds: float = 3.0) -> list[str]:
        stop_calls.append({"port": port, "pids": list(pids), "timeout_seconds": timeout_seconds})
        return []

    monkeypatch.setattr("g_agent.cli.commands._bridge_port_pids", fake_bridge_port_pids)
    monkeypatch.setattr("g_agent.cli.commands._stop_bridge_processes", fake_stop_bridge_processes)
    monkeypatch.setattr("g_agent.cli.commands._is_bridge_port_in_use", lambda *_args, **_kwargs: False)
    monkeypatch.setattr("g_agent.cli.commands._bridge_bind_error", lambda _port: None)
    monkeypatch.setattr("g_agent.cli.commands._get_bridge_dir", lambda force_rebuild=False: fake_bridge_dir)

    run_calls: list[dict[str, object]] = []

    def fake_run(
        cmd: list[str],
        cwd: Path | None = None,
        check: bool = False,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess:
        run_calls.append({"cmd": list(cmd), "cwd": cwd, "check": check, "env": dict(env or {})})
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("subprocess.run", fake_run)

    result = runner.invoke(app, ["channels", "login", "--restart-existing"])

    assert result.exit_code == 0
    assert stop_calls == [{"port": 4567, "pids": ["1111"], "timeout_seconds": 3.0}]
    assert run_calls and run_calls[0]["cmd"] == ["npm", "start"]


def test_channels_login_restart_existing_fails_when_stop_does_not_clear_port(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(data_dir))

    config = Config()
    config.channels.whatsapp.bridge_url = "ws://127.0.0.1:5678"
    save_config(config)

    monkeypatch.setattr("g_agent.cli.commands._bridge_port_pids", lambda _port: ["2222"])
    monkeypatch.setattr(
        "g_agent.cli.commands._stop_bridge_processes",
        lambda _port, _pids, *, timeout_seconds=3.0: ["2222"],
    )
    monkeypatch.setattr("g_agent.cli.commands._is_bridge_port_in_use", lambda *_args, **_kwargs: False)
    monkeypatch.setattr("g_agent.cli.commands._bridge_bind_error", lambda _port: None)
    monkeypatch.setattr(
        "g_agent.cli.commands._get_bridge_dir",
        lambda force_rebuild=False: (_ for _ in ()).throw(AssertionError("should not build bridge")),
    )

    result = runner.invoke(app, ["channels", "login", "--restart-existing"])

    assert result.exit_code == 1
    assert "Could not stop existing bridge process on port 5678: 2222" in result.stdout
