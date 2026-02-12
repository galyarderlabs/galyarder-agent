"""Embeddable Agent API for Python applications."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from g_agent.agent.loop import AgentLoop
from g_agent.bus.queue import MessageBus
from g_agent.config.loader import load_config
from g_agent.config.schema import Config
from g_agent.plugins.loader import filter_plugins, load_installed_plugins
from g_agent.providers.base import LLMProvider
from g_agent.providers.factory import build_provider, collect_provider_factories, has_provider_factory


class Agent:
    """Small embeddable wrapper around AgentLoop for direct use in Python."""

    def __init__(
        self,
        config: Config | None = None,
        *,
        workspace: str | Path | None = None,
        provider: LLMProvider | None = None,
        plugins: list[Any] | None = None,
    ):
        self.config = config or load_config()
        if workspace is not None:
            self.config.agents.defaults.workspace = str(Path(workspace).expanduser())

        route = self.config.resolve_model_route()
        resolved_plugins = plugins or filter_plugins(
            load_installed_plugins(),
            enabled=self.config.tools.plugins.enabled,
            allow=self.config.tools.plugins.allow,
            deny=self.config.tools.plugins.deny,
        )
        provider_factories = collect_provider_factories(self.config, resolved_plugins)
        resolved_provider = provider or self._build_provider(route, provider_factories)

        self.bus = MessageBus()
        self.loop = AgentLoop(
            bus=self.bus,
            provider=resolved_provider,
            workspace=self.config.workspace_path,
            model=route.model,
            max_iterations=self.config.agents.defaults.max_tool_iterations,
            brave_api_key=self.config.tools.web.search.api_key or None,
            exec_config=self.config.tools.exec,
            restrict_to_workspace=self.config.tools.restrict_to_workspace,
            slack_webhook_url=self.config.integrations.slack.webhook_url or None,
            smtp_config=self.config.integrations.smtp,
            google_config=self.config.integrations.google,
            browser_config=self.config.tools.browser,
            tool_policy=self.config.tools.policy,
            risky_tools=self.config.tools.risky_tools,
            approval_mode=self.config.tools.approval_mode,
            enable_reflection=self.config.agents.defaults.enable_reflection,
            summary_interval=self.config.agents.defaults.summary_interval,
            fallback_models=route.fallback_models,
            plugins=resolved_plugins,
        )
        self._closed = False

    def _build_provider(self, route: Any, provider_factories: dict[str, Any]) -> LLMProvider:
        """Build default provider from config routing settings."""
        api_key = route.api_key
        if not api_key and route.provider not in {"vllm", "bedrock"}:
            api_key = self.config.get_api_key(route.model)
        model = self.config.agents.defaults.model
        is_bedrock = route.provider == "bedrock" or model.startswith("bedrock/")
        if (
            not api_key
            and not is_bedrock
            and not has_provider_factory(route.provider, provider_factories=provider_factories)
        ):
            raise ValueError(
                f"No API key configured for provider '{route.provider}'. "
                "Set providers.<name>.apiKey or pass a custom provider."
            )

        resolved_route = route.model_copy(update={"api_key": api_key})
        return build_provider(
            resolved_route,
            self.config,
            provider_factories=provider_factories,
        )

    async def ask(
        self,
        content: str,
        *,
        session_key: str = "embed:default",
        channel: str = "embed",
        chat_id: str = "embed",
    ) -> str:
        """Process one direct message through the agent."""
        self._ensure_open()
        return await self.loop.process_direct(
            content=content,
            session_key=session_key,
            channel=channel,
            chat_id=chat_id,
        )

    def ask_sync(
        self,
        content: str,
        *,
        session_key: str = "embed:default",
        channel: str = "embed",
        chat_id: str = "embed",
    ) -> str:
        """Sync wrapper for ask()."""
        self._ensure_open()
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.ask(content, session_key=session_key, channel=channel, chat_id=chat_id)
            )
        raise RuntimeError("ask_sync() cannot run inside an active event loop; use await ask(...).")

    async def _close_async(self) -> None:
        if self._closed:
            return
        await self.loop.shutdown()
        self._closed = True

    def close(self) -> None:
        """Close the embedded agent in sync contexts."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._close_async())
            return
        raise RuntimeError(
            "close() cannot run inside an active event loop; use await aclose() or async with Agent()."
        )

    async def aclose(self) -> None:
        """Close the embedded agent in async contexts."""
        await self._close_async()

    async def __aenter__(self) -> Agent:
        self._ensure_open()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self._close_async()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Agent is closed. Create a new Agent instance to continue.")
