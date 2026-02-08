from g_agent.config.loader import get_config_path
from g_agent.config.schema import Config
from g_agent.utils.helpers import PRIMARY_DATA_DIR, get_data_path


def _set_home(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    return home


def test_get_data_path_default(monkeypatch, tmp_path):
    home = _set_home(monkeypatch, tmp_path)
    monkeypatch.delenv("G_AGENT_DATA_DIR", raising=False)

    expected = home / PRIMARY_DATA_DIR
    assert get_data_path() == expected
    assert expected.exists()


def test_get_data_path_env_override_absolute(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    custom = tmp_path / "guest-profile"
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(custom))

    assert get_data_path() == custom
    assert custom.exists()


def test_get_data_path_env_override_relative(monkeypatch, tmp_path):
    home = _set_home(monkeypatch, tmp_path)
    monkeypatch.setenv("G_AGENT_DATA_DIR", ".g-agent-guest")

    expected = home / ".g-agent-guest"
    assert get_data_path() == expected
    assert expected.exists()


def test_get_config_path_follows_data_dir(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    custom = tmp_path / "guest-profile"
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(custom))

    assert get_config_path() == custom / "config.json"


def test_config_default_workspace_follows_data_dir(monkeypatch, tmp_path):
    home = _set_home(monkeypatch, tmp_path)
    monkeypatch.setenv("G_AGENT_DATA_DIR", ".g-agent-guest")

    config = Config()
    assert config.agents.defaults.workspace == str(home / ".g-agent-guest" / "workspace")
