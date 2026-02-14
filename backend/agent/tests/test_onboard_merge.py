"""Tests for non-destructive onboard merge."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from g_agent.cli.commands import app
from g_agent.config.loader import deep_merge_config

runner = CliRunner()


# ── deep_merge_config unit tests ──────────────────────────────────────


def test_deep_merge_adds_new_keys():
    existing = {"a": 1}
    defaults = {"a": 2, "b": 3}
    assert deep_merge_config(existing, defaults) == {"a": 1, "b": 3}


def test_deep_merge_nested_preserves_existing():
    existing = {"x": {"y": 1}}
    defaults = {"x": {"y": 99, "z": 2}, "w": 3}
    result = deep_merge_config(existing, defaults)
    assert result == {"x": {"y": 1, "z": 2}, "w": 3}


def test_deep_merge_empty_existing():
    defaults = {"a": 1, "b": {"c": 2}}
    assert deep_merge_config({}, defaults) == defaults


def test_deep_merge_empty_defaults():
    existing = {"a": 1, "b": {"c": 2}}
    assert deep_merge_config(existing, {}) == existing


# ── onboard CLI integration tests ────────────────────────────────────


def test_onboard_fresh_creates_config(tmp_path, monkeypatch):
    data_dir = tmp_path / "g-agent"
    data_dir.mkdir()
    monkeypatch.setattr("g_agent.config.loader.get_data_path", lambda: data_dir)
    monkeypatch.setattr("g_agent.utils.helpers.get_data_path", lambda: data_dir)

    result = runner.invoke(app, ["onboard"])
    assert result.exit_code == 0
    assert "Created config" in result.stdout

    config_file = data_dir / "config.json"
    assert config_file.exists()


def test_onboard_existing_preserves_api_key(tmp_path, monkeypatch):
    data_dir = tmp_path / "g-agent"
    data_dir.mkdir()
    monkeypatch.setattr("g_agent.config.loader.get_data_path", lambda: data_dir)
    monkeypatch.setattr("g_agent.utils.helpers.get_data_path", lambda: data_dir)

    # Create initial config with custom API key
    config_file = data_dir / "config.json"
    config_file.write_text(
        json.dumps(
            {
                "providers": {
                    "openrouter": {"apiKey": "sk-test-key-123"},
                },
            }
        )
    )

    result = runner.invoke(app, ["onboard"])
    assert result.exit_code == 0
    assert "Merged config" in result.stdout
    assert "existing values preserved" in result.stdout

    # Verify API key preserved and new defaults added
    with open(config_file) as f:
        data = json.load(f)
    assert data["providers"]["openrouter"]["apiKey"] == "sk-test-key-123"
    # New defaults should be present
    assert "agents" in data
    assert "channels" in data


def test_onboard_workspace_files_not_overwritten(tmp_path, monkeypatch):
    data_dir = tmp_path / "g-agent"
    data_dir.mkdir()
    monkeypatch.setattr("g_agent.config.loader.get_data_path", lambda: data_dir)
    monkeypatch.setattr("g_agent.utils.helpers.get_data_path", lambda: data_dir)

    workspace = data_dir / "workspace"
    workspace.mkdir(parents=True)
    agents_md = workspace / "AGENTS.md"
    custom_content = "# My Custom Agent Instructions\nDo cool stuff."
    agents_md.write_text(custom_content)

    result = runner.invoke(app, ["onboard"])
    assert result.exit_code == 0

    # Custom AGENTS.md should survive
    assert agents_md.read_text() == custom_content
