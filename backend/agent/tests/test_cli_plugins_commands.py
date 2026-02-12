from typing import Any

from typer.testing import CliRunner

from g_agent.cli.commands import app
from g_agent.config.loader import save_config
from g_agent.config.schema import Config
from g_agent.plugins.base import PluginBase, PluginContext

runner = CliRunner()


class ToolOnlyPlugin(PluginBase):
    name = "tool-plugin"

    def register_tools(self, registry: Any, context: PluginContext) -> None:
        return


class ChannelOnlyPlugin(PluginBase):
    name = "channel-plugin"

    def register_channels(self, channels: dict[str, Any], context: PluginContext) -> None:
        return


class ProviderOnlyPlugin(PluginBase):
    name = "provider-plugin"

    def register_providers(self, providers: dict[str, Any], context: PluginContext) -> None:
        providers["default"] = lambda _route, _config: None


def _prepare_config(
    tmp_path,
    monkeypatch,
    *,
    enabled: bool = True,
    allow: list[str] | None = None,
    deny: list[str] | None = None,
) -> None:
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    config = Config()
    config.tools.plugins.enabled = enabled
    config.tools.plugins.allow = allow or []
    config.tools.plugins.deny = deny or []
    save_config(config)


def test_plugins_list_shows_policy_status(tmp_path, monkeypatch):
    _prepare_config(tmp_path, monkeypatch, allow=["tool-plugin"], deny=["channel-plugin"])

    monkeypatch.setattr(
        "g_agent.plugins.loader.load_installed_plugins",
        lambda *_args, **_kwargs: [ToolOnlyPlugin(), ChannelOnlyPlugin()],
    )

    result = runner.invoke(app, ["plugins", "list"])
    assert result.exit_code == 0
    assert "tool-plugin" in result.stdout
    assert "channel-plugin" in result.stdout
    assert "active" in result.stdout.lower()
    assert "blocked" in result.stdout.lower()


def test_plugins_doctor_strict_fails_when_policy_blocks_all(tmp_path, monkeypatch):
    _prepare_config(tmp_path, monkeypatch, allow=["missing-plugin"])

    monkeypatch.setattr(
        "g_agent.plugins.loader.load_installed_plugins",
        lambda *_args, **_kwargs: [ToolOnlyPlugin()],
    )

    result = runner.invoke(app, ["plugins", "doctor", "--strict"])
    assert result.exit_code == 1
    assert "Active plugins" in result.stdout
    assert "0 active from 1" in result.stdout
    assert "discovered" in result.stdout


def test_plugins_list_handles_empty_discovery(tmp_path, monkeypatch):
    _prepare_config(tmp_path, monkeypatch)

    monkeypatch.setattr(
        "g_agent.plugins.loader.load_installed_plugins",
        lambda *_args, **_kwargs: [],
    )

    result = runner.invoke(app, ["plugins", "list"])
    assert result.exit_code == 0
    assert "No plugins discovered" in result.stdout


def test_plugins_list_shows_provider_hook(tmp_path, monkeypatch):
    _prepare_config(tmp_path, monkeypatch)

    monkeypatch.setattr(
        "g_agent.plugins.loader.load_installed_plugins",
        lambda *_args, **_kwargs: [ProviderOnlyPlugin()],
    )

    result = runner.invoke(app, ["plugins", "list"])
    assert result.exit_code == 0
    assert "provider-plugin" in result.stdout
    assert "providers" in result.stdout
