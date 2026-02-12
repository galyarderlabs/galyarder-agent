from typing import Any

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


def test_embedded_agent_ask_sync(tmp_path, monkeypatch):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    config = Config()
    config.agents.defaults.workspace = str(tmp_path)

    agent = Agent(
        config=config,
        provider=DummyProvider(),
        plugins=[MarkerPlugin()],
    )

    result = agent.ask_sync("hello from embed")
    assert result == "embedded-ok"

