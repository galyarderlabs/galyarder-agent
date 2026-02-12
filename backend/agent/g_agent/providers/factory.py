"""Provider factory helpers with plugin override support."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from g_agent.config.schema import Config, LLMRoute
from g_agent.plugins.base import PluginContext
from g_agent.plugins.loader import register_provider_plugins
from g_agent.providers.base import LLMProvider
from g_agent.providers.litellm_provider import LiteLLMProvider

ProviderFactory = Callable[[LLMRoute, Config], LLMProvider]


def collect_provider_factories(config: Config, plugins: list[Any] | None = None) -> dict[str, ProviderFactory]:
    """Collect provider factories registered by plugins."""
    provider_factories: dict[str, ProviderFactory] = {}
    if not plugins:
        return provider_factories

    context = PluginContext(
        workspace=config.workspace_path,
        config=config,
    )
    register_provider_plugins(plugins, context, providers=provider_factories)
    return provider_factories


def has_provider_factory(
    route_provider: str,
    *,
    provider_factories: dict[str, ProviderFactory] | None = None,
) -> bool:
    """Return True when plugin provider factories can handle this route."""
    if not provider_factories:
        return False
    return route_provider in provider_factories or "default" in provider_factories


def build_provider(
    route: LLMRoute,
    config: Config,
    *,
    provider_factories: dict[str, ProviderFactory] | None = None,
) -> LLMProvider:
    """Build runtime provider for a resolved route."""
    if provider_factories:
        builder = provider_factories.get(route.provider) or provider_factories.get("default")
        if builder is not None:
            return builder(route, config)

    provider_cfg = config.get_provider(route.model)
    return LiteLLMProvider(
        api_key=route.api_key,
        api_base=route.api_base,
        default_model=route.model,
        extra_headers=provider_cfg.extra_headers if provider_cfg else None,
        provider_name=route.provider,
    )
