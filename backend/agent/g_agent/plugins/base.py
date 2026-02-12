"""Plugin SDK base classes for g-agent runtime extensions."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from g_agent.agent.tools.registry import ToolRegistry
    from g_agent.bus.queue import MessageBus
    from g_agent.channels.base import BaseChannel
    from g_agent.config.schema import Config
    from g_agent.providers.base import LLMProvider


@dataclass(slots=True)
class PluginContext:
    """Runtime context passed to plugins during registration."""

    workspace: Path
    config: Config | None = None
    bus: MessageBus | None = None
    provider: LLMProvider | None = None
    extras: dict[str, Any] = field(default_factory=dict)


class PluginBase:
    """Base class for g-agent plugins."""

    name: str = "unnamed-plugin"

    def register_tools(self, registry: "ToolRegistry", context: PluginContext) -> None:
        """Register custom tools into the runtime tool registry."""
        return

    def register_channels(
        self,
        channels: dict[str, "BaseChannel"],
        context: PluginContext,
    ) -> None:
        """Register custom channels into the runtime channel map."""
        return

