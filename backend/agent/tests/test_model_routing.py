import asyncio
from typing import Any

from g_agent.agent.loop import AgentLoop
from g_agent.bus.queue import MessageBus
from g_agent.config.schema import Config
from g_agent.providers.base import LLMProvider, LLMResponse


class RouteTestProvider(LLMProvider):
    def __init__(self, responses: dict[str, LLMResponse]):
        super().__init__(api_key="", api_base=None)
        self.responses = responses
        self.calls: list[str] = []

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        model_name = model or self.get_default_model()
        self.calls.append(model_name)
        return self.responses[model_name]

    def get_default_model(self) -> str:
        return "primary-model"


def test_auto_mode_prefers_proxy_for_unprefixed_model():
    cfg = Config.model_validate(
        {
            "agents": {
                "defaults": {
                    "model": "gemini-3-pro-preview",
                    "routing": {
                        "mode": "auto",
                        "fallback_models": [
                            "gemini-3-pro-preview",
                            "gemini-3-flash-preview",
                            "gemini-3-flash-preview",
                            "qwen3-coder-plus",
                        ],
                    },
                }
            },
            "providers": {
                "vllm": {
                    "api_key": "sk-local",
                    "api_base": "http://127.0.0.1:8317/v1",
                },
                "gemini": {"api_key": "gsk-live"},
            },
        }
    )
    route = cfg.resolve_model_route()
    assert route.mode == "proxy"
    assert route.provider == "vllm"
    assert route.api_base == "http://127.0.0.1:8317/v1"
    assert route.fallback_models == ["gemini-3-flash-preview", "qwen3-coder-plus"]


def test_direct_mode_forces_direct_provider():
    cfg = Config.model_validate(
        {
            "agents": {
                "defaults": {
                    "model": "gemini-3-pro-preview",
                    "routing": {"mode": "direct"},
                }
            },
            "providers": {
                "vllm": {
                    "api_key": "sk-local",
                    "api_base": "http://127.0.0.1:8317/v1",
                },
                "gemini": {"api_key": "gsk-live"},
            },
        }
    )
    route = cfg.resolve_model_route()
    assert route.mode == "direct"
    assert route.provider == "gemini"
    assert route.api_key == "gsk-live"


def test_auto_mode_honors_explicit_model_prefix():
    cfg = Config.model_validate(
        {
            "agents": {
                "defaults": {
                    "model": "gemini/gemini-2.5-pro",
                    "routing": {"mode": "auto"},
                }
            },
            "providers": {
                "vllm": {
                    "api_key": "sk-local",
                    "api_base": "http://127.0.0.1:8317/v1",
                },
                "gemini": {"api_key": "gsk-live"},
            },
        }
    )
    route = cfg.resolve_model_route()
    assert route.mode == "direct"
    assert route.provider == "gemini"


def test_agent_loop_falls_back_to_next_model_on_retryable_error(tmp_path, monkeypatch):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    provider = RouteTestProvider(
        responses={
            "primary-model": LLMResponse(
                content="Error calling LLM: litellm.NotFoundError: model not found",
                finish_reason="error",
            ),
            "backup-model": LLMResponse(content="ok"),
        }
    )
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="primary-model",
        fallback_models=["backup-model"],
        enable_reflection=False,
    )
    response, active_model = asyncio.run(
        loop._chat_with_model_failover(
            messages=[{"role": "user", "content": "test"}],
            tools=None,
        )
    )
    assert active_model == "backup-model"
    assert response.content == "ok"
    assert provider.calls == ["primary-model", "backup-model"]


def test_agent_loop_does_not_fallback_on_non_retryable_error(tmp_path, monkeypatch):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    provider = RouteTestProvider(
        responses={
            "primary-model": LLMResponse(content="Error: blocked by policy", finish_reason="error"),
            "backup-model": LLMResponse(content="ok"),
        }
    )
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="primary-model",
        fallback_models=["backup-model"],
        enable_reflection=False,
    )
    response, active_model = asyncio.run(
        loop._chat_with_model_failover(
            messages=[{"role": "user", "content": "test"}],
            tools=None,
        )
    )
    assert active_model == "primary-model"
    assert response.finish_reason == "error"
    assert provider.calls == ["primary-model"]
