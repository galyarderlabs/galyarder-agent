"""Tests for the declarative provider registry."""

from g_agent.providers.registry import (
    PROVIDERS,
    find_by_model,
    find_by_name,
    find_gateway,
)

# ─── ProviderSpec data integrity ───────────────────────────────────────────


def test_all_specs_have_required_fields():
    """Every ProviderSpec must have name, env_key, and at least one keyword."""
    for spec in PROVIDERS:
        assert spec.name, f"ProviderSpec missing name: {spec}"
        assert spec.env_key, f"{spec.name}: missing env_key"
        assert len(spec.keywords) > 0, f"{spec.name}: must have ≥1 keyword"


def test_no_duplicate_names():
    """Provider names must be unique in the registry."""
    names = [s.name for s in PROVIDERS]
    assert len(names) == len(set(names)), f"Duplicate names: {names}"


def test_env_extras_are_tuples():
    """All env_extras entries must be (str, str) tuples."""
    for spec in PROVIDERS:
        for extra in spec.env_extras:
            assert len(extra) == 2, f"{spec.name}: env_extras entry not a pair: {extra}"
            assert isinstance(extra[0], str) and isinstance(extra[1], str)


# ─── find_by_model ─────────────────────────────────────────────────────────


def test_find_by_model_anthropic():
    spec = find_by_model("claude-sonnet-4-5")
    assert spec is not None
    assert spec.name == "anthropic"


def test_find_by_model_openai():
    spec = find_by_model("gpt-4o-mini")
    assert spec is not None
    assert spec.name == "openai"


def test_find_by_model_gemini():
    spec = find_by_model("gemini-2.5-pro")
    assert spec is not None
    assert spec.name == "gemini"


def test_find_by_model_deepseek():
    spec = find_by_model("deepseek-chat")
    assert spec is not None
    assert spec.name == "deepseek"


def test_find_by_model_zhipu():
    spec = find_by_model("glm-4-flash")
    assert spec is not None
    assert spec.name == "zhipu"


def test_find_by_model_groq():
    spec = find_by_model("groq/llama-3.3-70b")
    assert spec is not None
    assert spec.name == "groq"


def test_find_by_model_moonshot():
    spec = find_by_model("kimi-k2.5")
    assert spec is not None
    assert spec.name == "moonshot"


def test_find_by_model_dashscope():
    spec = find_by_model("qwen-turbo")
    assert spec is not None
    assert spec.name == "dashscope"


def test_find_by_model_unknown_returns_none():
    spec = find_by_model("totally-unknown-model-xyz")
    assert spec is None


def test_find_by_model_case_insensitive():
    spec = find_by_model("Claude-Sonnet-4-5")
    assert spec is not None
    assert spec.name == "anthropic"


# ─── by_name ───────────────────────────────────────────────────────────────


def test_by_name_existing():
    spec = find_by_name("openrouter")
    assert spec is not None
    assert spec.name == "openrouter"


def test_by_name_nonexistent():
    spec = find_by_name("does_not_exist")
    assert spec is None


def test_by_name_all_providers():
    """Every PROVIDERS entry is findable by name."""
    for spec in PROVIDERS:
        found = find_by_name(spec.name)
        assert found is spec, f"by_name failed for {spec.name}"


# ─── find_gateway ──────────────────────────────────────────────────────────


def test_find_gateway_by_provider_name_openrouter():
    spec = find_gateway("openrouter", None, None)
    assert spec is not None
    assert spec.name == "openrouter"
    assert spec.is_gateway is True


def test_find_gateway_by_api_key_prefix():
    spec = find_gateway(None, "sk-or-v1-abc123", None)
    assert spec is not None
    assert spec.name == "openrouter"


def test_find_gateway_by_api_base():
    spec = find_gateway(None, None, "https://api.aihubmix.com/v1")
    assert spec is not None
    assert spec.name == "aihubmix"


def test_find_gateway_non_gateway_returns_none():
    """Direct providers (anthropic, openai) are not gateways."""
    spec = find_gateway("anthropic", None, None)
    assert spec is None


def test_find_gateway_unknown_returns_none():
    spec = find_gateway(None, "random-key", None)
    assert spec is None


# ─── model_overrides ───────────────────────────────────────────────────────


def test_moonshot_kimi_k25_override():
    spec = find_by_name("moonshot")
    assert spec is not None
    assert len(spec.model_overrides) > 0
    # kimi-k2.5 should have temperature override
    for pattern, overrides in spec.model_overrides:
        if "kimi-k2.5" in pattern:
            assert "temperature" in overrides
            assert overrides["temperature"] == 1.0
            return
    raise AssertionError("No kimi-k2.5 override found in moonshot spec")


# ─── skip_prefixes / litellm_prefix for direct providers ──────────────────


def test_anthropic_no_litellm_prefix():
    """Anthropic has no litellm_prefix — LiteLLM recognises claude-* natively."""
    spec = find_by_name("anthropic")
    assert spec is not None
    assert spec.litellm_prefix == ""
    assert spec.skip_prefixes == ()


def test_openai_no_litellm_prefix():
    """OpenAI has no litellm_prefix — LiteLLM recognises gpt-* natively."""
    spec = find_by_name("openai")
    assert spec is not None
    assert spec.litellm_prefix == ""
    assert spec.skip_prefixes == ()


# ─── litellm_prefix ───────────────────────────────────────────────────────


def test_gemini_litellm_prefix():
    spec = find_by_name("gemini")
    assert spec is not None
    assert spec.litellm_prefix == "gemini"


def test_zhipu_litellm_prefix():
    spec = find_by_name("zhipu")
    assert spec is not None
    assert spec.litellm_prefix == "zai"


def test_openrouter_litellm_prefix():
    spec = find_by_name("openrouter")
    assert spec is not None
    assert spec.litellm_prefix == "openrouter"


# ─── gateway properties ───────────────────────────────────────────────────


def test_openrouter_is_gateway():
    spec = find_by_name("openrouter")
    assert spec is not None
    assert spec.is_gateway is True
    assert spec.strip_model_prefix is False  # keeps provider prefix in model name


def test_aihubmix_is_gateway():
    spec = find_by_name("aihubmix")
    assert spec is not None
    assert spec.is_gateway is True


def test_anthropic_is_not_gateway():
    spec = find_by_name("anthropic")
    assert spec is not None
    assert spec.is_gateway is False


# ─── env_extras ────────────────────────────────────────────────────────────


def test_moonshot_has_api_base_env_extra():
    spec = find_by_name("moonshot")
    assert spec is not None
    env_names = [name for name, _ in spec.env_extras]
    assert "MOONSHOT_API_BASE" in env_names
