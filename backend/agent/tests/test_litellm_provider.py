"""Tests for LiteLLMProvider registry-driven refactor."""

import os
from unittest.mock import MagicMock, patch

import pytest

# ─── _resolve_model tests via direct instantiation (mocked litellm) ────────


@pytest.fixture
def mock_litellm():
    """Mock litellm so we don't need to install it for unit tests."""
    mock = MagicMock()
    mock.suppress_debug_info = False
    mock.drop_params = False
    mock.api_base = None
    with patch.dict("sys.modules", {"litellm": mock}):
        yield mock


@pytest.fixture
def make_provider(mock_litellm):
    """Factory that creates a LiteLLMProvider with mocked litellm."""

    def _make(**kwargs):
        # Need to re-import after mocking
        import importlib

        import g_agent.providers.litellm_provider as mod

        importlib.reload(mod)
        return mod.LiteLLMProvider(**kwargs)

    return _make


def test_resolve_model_gateway_prefixes(make_provider):
    """Gateway mode: applies gateway prefix (keeps provider prefix since strip_model_prefix=False)."""
    provider = make_provider(
        api_key="sk-or-v1-test",
        provider_name="openrouter",
        default_model="claude-sonnet-4-5",
    )
    resolved = provider._resolve_model("anthropic/claude-sonnet-4-5")
    assert resolved.startswith("openrouter/")
    # OpenRouter keeps the original provider prefix in the model name
    assert resolved == "openrouter/anthropic/claude-sonnet-4-5"


def test_resolve_model_proxy_gateway_uses_openai_prefix(make_provider):
    """Generic proxy mode should normalize to openai/<model> for LiteLLM."""
    provider = make_provider(
        api_key="sk-local-test",
        api_base="http://127.0.0.1:8317/v1",
        provider_name="proxy",
        default_model="claude-opus-4-6-thinking",
    )
    resolved = provider._resolve_model("claude-opus-4-6-thinking")
    assert resolved == "openai/claude-opus-4-6-thinking"


def test_resolve_model_standard_auto_prefix(make_provider):
    """Standard mode: auto-prefix bare model names for known providers."""
    provider = make_provider(
        api_key="test-key",
        default_model="gemini-2.5-pro",
    )
    resolved = provider._resolve_model("gemini-2.5-pro")
    assert resolved.startswith("gemini/")


def test_resolve_model_skip_already_prefixed(make_provider):
    """Standard mode: don't double-prefix if already correct."""
    provider = make_provider(
        api_key="test-key",
        default_model="anthropic/claude-sonnet-4-5",
    )
    resolved = provider._resolve_model("anthropic/claude-sonnet-4-5")
    assert resolved == "anthropic/claude-sonnet-4-5"
    assert not resolved.startswith("anthropic/anthropic/")


def test_resolve_model_zhipu_uses_zai_prefix(make_provider):
    """Zhipu models should get zai/ prefix."""
    provider = make_provider(
        api_key="test-key",
        default_model="glm-4-flash",
    )
    resolved = provider._resolve_model("glm-4-flash")
    assert resolved.startswith("zai/")


def test_resolve_model_moonshot_prefix(make_provider):
    """Moonshot/kimi models should get moonshot/ prefix."""
    provider = make_provider(
        api_key="test-key",
        default_model="kimi-k2.5",
    )
    resolved = provider._resolve_model("kimi-k2.5")
    assert resolved.startswith("moonshot/")


# ─── _apply_model_overrides ───────────────────────────────────────────────


def test_apply_model_overrides_kimi(make_provider):
    """kimi-k2.5 should get temperature=1.0 override."""
    provider = make_provider(
        api_key="test-key",
        default_model="kimi-k2.5",
    )
    kwargs = {"temperature": 0.7}
    provider._apply_model_overrides("moonshot/kimi-k2.5", kwargs)
    assert kwargs["temperature"] == 1.0


def test_apply_model_overrides_no_match(make_provider):
    """Non-matching models should not be modified."""
    provider = make_provider(
        api_key="test-key",
        default_model="claude-sonnet-4-5",
    )
    kwargs = {"temperature": 0.7}
    provider._apply_model_overrides("claude-sonnet-4-5", kwargs)
    assert kwargs["temperature"] == 0.7


# ─── _setup_env ────────────────────────────────────────────────────────────


def test_setup_env_sets_provider_key(make_provider, monkeypatch):
    """_setup_env should set the correct env var for the provider."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    make_provider(
        api_key="sk-ant-test-123",
        default_model="claude-sonnet-4-5",
    )
    # After init, ANTHROPIC_API_KEY should be set via setdefault
    assert os.environ.get("ANTHROPIC_API_KEY") == "sk-ant-test-123"


def test_setup_env_gateway_overrides(make_provider, monkeypatch):
    """Gateway mode: should override (not setdefault) the env var."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "old-key")
    make_provider(
        api_key="sk-or-v1-new-key",
        provider_name="openrouter",
        default_model="claude-sonnet-4-5",
    )
    assert os.environ.get("OPENROUTER_API_KEY") == "sk-or-v1-new-key"


def test_setup_env_proxy_gateway_overrides_openai(make_provider, monkeypatch):
    """Generic proxy mode should write OPENAI_API_KEY for OpenAI-compatible base."""
    monkeypatch.setenv("OPENAI_API_KEY", "old-key")
    make_provider(
        api_key="sk-local-240905",
        api_base="http://127.0.0.1:8317/v1",
        provider_name="proxy",
        default_model="claude-opus-4-6-thinking",
    )
    assert os.environ.get("OPENAI_API_KEY") == "sk-local-240905"


def test_setup_env_standard_does_not_override(make_provider, monkeypatch):
    """Standard mode: setdefault should NOT override existing env."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "existing-key")
    make_provider(
        api_key="new-key",
        default_model="claude-sonnet-4-5",
    )
    assert os.environ.get("ANTHROPIC_API_KEY") == "existing-key"


# ─── extra_headers ─────────────────────────────────────────────────────────


def test_extra_headers_stored(make_provider):
    """extra_headers should be stored on the provider for later use."""
    headers = {"X-Custom": "value", "APP-Code": "abc"}
    provider = make_provider(
        api_key="test-key",
        default_model="test-model",
        extra_headers=headers,
    )
    assert provider.extra_headers == headers


def test_extra_headers_defaults_to_empty(make_provider):
    """Without extra_headers, should default to empty dict."""
    provider = make_provider(
        api_key="test-key",
        default_model="test-model",
    )
    assert provider.extra_headers == {}


# ─── constructor flags ─────────────────────────────────────────────────────


def test_drop_params_enabled(make_provider, mock_litellm):
    """litellm.drop_params must be True after init."""
    make_provider(api_key="test-key", default_model="test-model")
    assert mock_litellm.drop_params is True


def test_suppress_debug_info(make_provider, mock_litellm):
    """litellm.suppress_debug_info must be True after init."""
    make_provider(api_key="test-key", default_model="test-model")
    assert mock_litellm.suppress_debug_info is True
