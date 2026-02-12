"""Plugin discovery and registration helpers."""

from __future__ import annotations

from importlib import metadata as importlib_metadata
from typing import Any, Callable, Iterable

from loguru import logger

from g_agent.plugins.base import PluginBase, PluginContext

EntryPointProvider = Callable[[str], Iterable[Any]]


def _default_entry_points(group: str) -> list[Any]:
    """Return entry points for the given group with py311/py312 compatibility."""
    all_entry_points = importlib_metadata.entry_points()
    if hasattr(all_entry_points, "select"):
        return list(all_entry_points.select(group=group))
    return list(all_entry_points.get(group, []))


def _is_plugin_instance(value: Any) -> bool:
    """Return True when value looks like a plugin instance."""
    if isinstance(value, PluginBase):
        return True
    return callable(getattr(value, "register_tools", None)) or callable(
        getattr(value, "register_channels", None)
    ) or callable(
        getattr(value, "register_providers", None)
    )


def _is_channel_like(value: Any) -> bool:
    """Return True when value looks like a channel implementation."""
    return (
        callable(getattr(value, "start", None))
        and callable(getattr(value, "stop", None))
        and callable(getattr(value, "send", None))
    )


def _coerce_plugin(entry_name: str, loaded: Any) -> Any:
    """Convert loaded entrypoint object into a plugin instance."""
    candidate = loaded
    if isinstance(candidate, type):
        candidate = candidate()
    elif callable(candidate) and not _is_plugin_instance(candidate):
        candidate = candidate()

    if not _is_plugin_instance(candidate):
        raise TypeError(
            f"Entry point '{entry_name}' did not resolve to a plugin instance "
            "(missing register_tools/register_channels/register_providers)."
        )

    if not getattr(candidate, "name", ""):
        setattr(candidate, "name", entry_name)
    return candidate


def plugin_label(plugin: Any) -> str:
    """Stable plugin display label."""
    label = str(getattr(plugin, "name", "")).strip()
    return label or plugin.__class__.__name__


def load_installed_plugins(
    group: str = "g_agent.plugins",
    entry_points_provider: EntryPointProvider | None = None,
) -> list[Any]:
    """Load plugins from Python entry points."""
    provider = entry_points_provider or _default_entry_points
    loaded_plugins: list[Any] = []
    seen_labels: set[str] = set()

    for entry_point in sorted(provider(group), key=lambda item: getattr(item, "name", "")):
        entry_name = getattr(entry_point, "name", "<unknown>")
        try:
            raw = entry_point.load()
            plugin = _coerce_plugin(entry_name, raw)
            label = plugin_label(plugin)
            if label in seen_labels:
                logger.warning(f"Skipping duplicate plugin '{label}' from entry point '{entry_name}'")
                continue
            seen_labels.add(label)
            loaded_plugins.append(plugin)
            logger.info(f"Loaded plugin '{label}' from entry point '{entry_name}'")
        except Exception as exc:
            logger.warning(f"Failed to load plugin entry point '{entry_name}': {exc}")
    return loaded_plugins


def filter_plugins(
    plugins: list[Any],
    *,
    enabled: bool = True,
    allow: list[str] | None = None,
    deny: list[str] | None = None,
) -> list[Any]:
    """Filter loaded plugins using enabled/allow/deny policy."""
    if not enabled:
        return []

    allow_set = {item.strip().lower() for item in (allow or []) if item and item.strip()}
    deny_set = {item.strip().lower() for item in (deny or []) if item and item.strip()}
    selected: list[Any] = []
    for plugin in plugins:
        label = plugin_label(plugin)
        key = label.lower()
        if allow_set and key not in allow_set:
            logger.debug(f"Skipping plugin '{label}' (not in allow list)")
            continue
        if key in deny_set:
            logger.debug(f"Skipping plugin '{label}' (deny list)")
            continue
        selected.append(plugin)
    return selected


def register_tool_plugins(
    plugins: list[Any],
    context: PluginContext,
    *,
    registry: Any,
) -> None:
    """Call register_tools() on loaded plugins."""
    for plugin in plugins:
        hook = getattr(plugin, "register_tools", None)
        if not callable(hook):
            continue
        try:
            hook(registry, context)
        except Exception as exc:
            logger.warning(f"Plugin '{plugin_label(plugin)}' tool registration failed: {exc}")


def register_channel_plugins(
    plugins: list[Any],
    context: PluginContext,
    *,
    channels: dict[str, Any],
) -> None:
    """Call register_channels() on loaded plugins and validate channel map."""
    for plugin in plugins:
        hook = getattr(plugin, "register_channels", None)
        if not callable(hook):
            continue
        before = set(channels.keys())
        try:
            hook(channels, context)
        except Exception as exc:
            logger.warning(f"Plugin '{plugin_label(plugin)}' channel registration failed: {exc}")
            continue

        for name in set(channels.keys()) - before:
            channel = channels.get(name)
            if _is_channel_like(channel):
                logger.info(f"Plugin '{plugin_label(plugin)}' registered channel '{name}'")
                continue
            channels.pop(name, None)
            logger.warning(
                f"Plugin '{plugin_label(plugin)}' attempted to register invalid channel '{name}'"
            )


def register_provider_plugins(
    plugins: list[Any],
    context: PluginContext,
    *,
    providers: dict[str, Any],
) -> None:
    """Call register_providers() on loaded plugins and validate provider factories."""
    for plugin in plugins:
        hook = getattr(plugin, "register_providers", None)
        if not callable(hook):
            continue
        before = set(providers.keys())
        try:
            hook(providers, context)
        except Exception as exc:
            logger.warning(f"Plugin '{plugin_label(plugin)}' provider registration failed: {exc}")
            continue

        for name in list(providers.keys()):
            factory = providers.get(name)
            if callable(factory):
                continue
            providers.pop(name, None)
            logger.warning(
                f"Plugin '{plugin_label(plugin)}' attempted to register invalid provider '{name}'"
            )

        for name in sorted(set(providers.keys()) - before):
            logger.info(f"Plugin '{plugin_label(plugin)}' registered provider '{name}'")
