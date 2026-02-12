import asyncio
from typing import Any

from g_agent.agent.loop import AgentLoop
from g_agent.agent.tools.base import Tool
from g_agent.bus.events import OutboundMessage
from g_agent.bus.queue import MessageBus
from g_agent.channels.base import BaseChannel
from g_agent.channels.manager import ChannelManager
from g_agent.config.schema import Config
from g_agent.plugins.base import PluginBase, PluginContext
from g_agent.plugins.loader import load_installed_plugins
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
        return LLMResponse(content="ok")

    def get_default_model(self) -> str:
        return "dummy-model"


class PluginEchoTool(Tool):
    @property
    def name(self) -> str:
        return "plugin_echo"

    @property
    def description(self) -> str:
        return "Plugin test tool"

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs: Any) -> str:
        return "plugin-ok"


class PluginTestChannel(BaseChannel):
    name = "plugin-test"

    def __init__(self, bus: MessageBus):
        super().__init__(config=type("StubConfig", (), {"allow_from": []})(), bus=bus)
        self.sent: list[OutboundMessage] = []

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def send(self, msg: OutboundMessage) -> None:
        self.sent.append(msg)


class ToolPlugin(PluginBase):
    name = "tool-plugin"

    def register_tools(self, registry: Any, context: PluginContext) -> None:
        assert context.workspace
        registry.register(PluginEchoTool())


class ChannelPlugin(PluginBase):
    name = "channel-plugin"

    def register_channels(self, channels: dict[str, BaseChannel], context: PluginContext) -> None:
        assert context.config is not None
        assert context.bus is not None
        channels["plugin-test"] = PluginTestChannel(context.bus)


class FakeEntryPoint:
    def __init__(self, name: str, target: Any):
        self.name = name
        self._target = target

    def load(self) -> Any:
        return self._target


def _plugin_factory() -> PluginBase:
    plugin = ToolPlugin()
    plugin.name = "factory-plugin"
    return plugin


def test_load_installed_plugins_supports_class_and_factory():
    plugins = load_installed_plugins(
        entry_points_provider=lambda _group: [
            FakeEntryPoint("class_plugin", ToolPlugin),
            FakeEntryPoint("factory_plugin", _plugin_factory),
            FakeEntryPoint("invalid", object()),
        ]
    )
    names = [str(getattr(plugin, "name", "")) for plugin in plugins]
    assert "tool-plugin" in names
    assert "factory-plugin" in names
    assert len(plugins) == 2


def test_agent_loop_registers_plugin_tools(tmp_path, monkeypatch):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    loop = AgentLoop(
        bus=MessageBus(),
        provider=DummyProvider(),
        workspace=tmp_path,
        enable_reflection=False,
        plugins=[ToolPlugin()],
    )

    assert loop.tools.has("plugin_echo")
    assert asyncio.run(loop.tools.execute("plugin_echo", {})) == "plugin-ok"


def test_channel_manager_registers_plugin_channels():
    config = Config()
    bus = MessageBus()
    manager = ChannelManager(config, bus, plugins=[ChannelPlugin()])

    assert "plugin-test" in manager.channels
    assert isinstance(manager.channels["plugin-test"], PluginTestChannel)

