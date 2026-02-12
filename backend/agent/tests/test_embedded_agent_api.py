import asyncio
from typing import Any

import pytest

from g_agent.agent import Agent
from g_agent.config.schema import Config
from g_agent.plugins.base import PluginBase, PluginContext
from g_agent.providers.base import LLMProvider, LLMResponse


class DummyProvider(LLMProvider):
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        return LLMResponse(content="embedded-ok")

    def get_default_model(self) -> str:
        return "dummy-model"


class MarkerPlugin(PluginBase):
    name = "marker-plugin"

    def register_tools(self, registry: Any, context: PluginContext) -> None:
        context.extras["plugin_marker"] = "loaded"


class ProviderDefaultPlugin(PluginBase):
    name = "provider-default-plugin"

    def register_providers(self, providers: dict[str, Any], context: PluginContext) -> None:
        providers["default"] = lambda _route, _config: DummyProvider()


def _build_agent(tmp_path, monkeypatch) -> Agent:
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    config = Config()
    config.agents.defaults.workspace = str(tmp_path)
    return Agent(
        config=config,
        provider=DummyProvider(),
        plugins=[MarkerPlugin()],
    )


def test_embedded_agent_ask_sync(tmp_path, monkeypatch):
    agent = _build_agent(tmp_path, monkeypatch)
    result = agent.ask_sync("hello from embed")
    assert result == "embedded-ok"


def test_embedded_agent_close_blocks_future_calls(tmp_path, monkeypatch):
    agent = _build_agent(tmp_path, monkeypatch)

    agent.close()
    agent.close()

    with pytest.raises(RuntimeError, match="Agent is closed"):
        agent.ask_sync("hello again")


def test_embedded_agent_async_context_manager(tmp_path, monkeypatch):
    agent = _build_agent(tmp_path, monkeypatch)

    async def _run() -> str:
        async with agent:
            return await agent.ask("hello from async context")

    result = asyncio.run(_run())
    assert result == "embedded-ok"

    with pytest.raises(RuntimeError, match="Agent is closed"):
        agent.ask_sync("one more message")


def test_embedded_agent_allows_plugin_provider_without_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    config = Config()
    config.agents.defaults.workspace = str(tmp_path)
    config.agents.defaults.model = "claude-opus-4-6-thinking"
    config.providers.anthropic.api_key = ""
    config.providers.openrouter.api_key = ""
    config.providers.openai.api_key = ""
    config.providers.proxy.api_key = ""
    config.providers.vllm.api_key = ""

    agent = Agent(config=config, plugins=[ProviderDefaultPlugin()])
    assert agent.ask_sync("hello plugin provider") == "embedded-ok"
