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

    result = runner.invoke(app, ["onboard", "--no-interactive"])
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

    result = runner.invoke(app, ["onboard", "--no-interactive"])
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

    result = runner.invoke(app, ["onboard", "--no-interactive"])
    assert result.exit_code == 0

    # Custom AGENTS.md should survive
    assert agents_md.read_text() == custom_content


# ── interactive wizard tests ─────────────────────────────────────────


def test_interactive_provider_openrouter(tmp_path, monkeypatch):
    """Interactive wizard: selecting OpenRouter sets provider key and routing mode."""
    data_dir = tmp_path / "g-agent"
    data_dir.mkdir()
    monkeypatch.setattr("g_agent.config.loader.get_data_path", lambda: data_dir)
    monkeypatch.setattr("g_agent.utils.helpers.get_data_path", lambda: data_dir)

    # Input sequence: provider=1 (OpenRouter), key=sk-or-test, model=skip,
    # web search=no, telegram=no, whatsapp=no, selfie=no
    user_input = "1\nsk-or-test\n\nn\nn\nn\nn\n"
    result = runner.invoke(app, ["onboard"], input=user_input)
    assert result.exit_code == 0

    with open(data_dir / "config.json") as f:
        data = json.load(f)
    assert data["providers"]["openrouter"]["apiKey"] == "sk-or-test"
    assert data["agents"]["defaults"]["routing"]["mode"] == "direct"


def test_interactive_provider_proxy(tmp_path, monkeypatch):
    """Interactive wizard: selecting Local Proxy sets proxy routing mode."""
    data_dir = tmp_path / "g-agent"
    data_dir.mkdir()
    monkeypatch.setattr("g_agent.config.loader.get_data_path", lambda: data_dir)
    monkeypatch.setattr("g_agent.utils.helpers.get_data_path", lambda: data_dir)

    # provider=7 (proxy), key=sk-local-test, api_base=default, model=skip,
    # web search=no, telegram=no, whatsapp=no, selfie=no
    user_input = "7\nsk-local-test\n\n\nn\nn\nn\nn\n"
    result = runner.invoke(app, ["onboard"], input=user_input)
    assert result.exit_code == 0

    with open(data_dir / "config.json") as f:
        data = json.load(f)
    assert data["providers"]["proxy"]["apiKey"] == "sk-local-test"
    assert data["agents"]["defaults"]["routing"]["mode"] == "proxy"
    assert data["agents"]["defaults"]["routing"]["proxyProvider"] == "proxy"


def test_interactive_skip_all(tmp_path, monkeypatch):
    """Interactive wizard: skipping all steps creates valid config."""
    data_dir = tmp_path / "g-agent"
    data_dir.mkdir()
    monkeypatch.setattr("g_agent.config.loader.get_data_path", lambda: data_dir)
    monkeypatch.setattr("g_agent.utils.helpers.get_data_path", lambda: data_dir)

    # provider=0 (skip), model=skip, web search=no, telegram=no, whatsapp=no, selfie=no
    user_input = "0\n\nn\nn\nn\nn\n"
    result = runner.invoke(app, ["onboard"], input=user_input)
    assert result.exit_code == 0
    assert "is ready" in result.stdout

    config_file = data_dir / "config.json"
    assert config_file.exists()


def test_interactive_web_search(tmp_path, monkeypatch):
    """Interactive wizard: setting Brave API key."""
    data_dir = tmp_path / "g-agent"
    data_dir.mkdir()
    monkeypatch.setattr("g_agent.config.loader.get_data_path", lambda: data_dir)
    monkeypatch.setattr("g_agent.utils.helpers.get_data_path", lambda: data_dir)

    # provider=0, model=skip, web search=yes + key, telegram=no, whatsapp=no, selfie=no
    user_input = "0\n\ny\nbrave-test-key\nn\nn\nn\n"
    result = runner.invoke(app, ["onboard"], input=user_input)
    assert result.exit_code == 0

    with open(data_dir / "config.json") as f:
        data = json.load(f)
    assert data["tools"]["web"]["search"]["apiKey"] == "brave-test-key"


def test_interactive_telegram_channel(tmp_path, monkeypatch):
    """Interactive wizard: enabling Telegram with token and user ID."""
    data_dir = tmp_path / "g-agent"
    data_dir.mkdir()
    monkeypatch.setattr("g_agent.config.loader.get_data_path", lambda: data_dir)
    monkeypatch.setattr("g_agent.utils.helpers.get_data_path", lambda: data_dir)

    # provider=0, model=skip, web search=no,
    # telegram=yes + token + user_id, whatsapp=no, selfie=no
    user_input = "0\n\nn\ny\n123456:AABB\n99887766\nn\nn\n"
    result = runner.invoke(app, ["onboard"], input=user_input)
    assert result.exit_code == 0

    with open(data_dir / "config.json") as f:
        data = json.load(f)
    assert data["channels"]["telegram"]["enabled"] is True
    assert data["channels"]["telegram"]["token"] == "123456:AABB"
    assert "99887766" in data["channels"]["telegram"]["allowFrom"]


def test_interactive_visual_identity_with_ref_image(tmp_path, monkeypatch):
    """Interactive wizard: enabling selfie with reference image and provider."""
    data_dir = tmp_path / "g-agent"
    data_dir.mkdir()
    monkeypatch.setattr("g_agent.config.loader.get_data_path", lambda: data_dir)
    monkeypatch.setattr("g_agent.utils.helpers.get_data_path", lambda: data_dir)

    ref_path = str(tmp_path / "my_face.jpg")

    # provider=0, model=skip, web search=no, telegram=no, whatsapp=no,
    # selfie=yes, provider=1 (HuggingFace), key=hf-test-key,
    # ref_image=ref_path, description=skip
    user_input = f"0\n\nn\nn\nn\ny\n1\nhf-test-key\n{ref_path}\n\n"
    result = runner.invoke(app, ["onboard"], input=user_input)
    assert result.exit_code == 0

    with open(data_dir / "config.json") as f:
        data = json.load(f)
    assert data["visual"]["enabled"] is True
    assert data["visual"]["imageGen"]["provider"] == "huggingface"
    assert data["visual"]["imageGen"]["apiKey"] == "hf-test-key"
    assert data["visual"]["referenceImage"] == ref_path
