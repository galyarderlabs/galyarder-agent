# Plugins (Phase 1)

`g-agent` now supports runtime extension plugins via Python entry points.

## What plugins can extend

- register custom tools
- register custom channels

## Entry point group

Use this entry point group in your plugin package:

```toml
[project.entry-points."g_agent.plugins"]
my_plugin = "my_package.plugin:MyPlugin"
```

`MyPlugin` can be:

- a plugin instance
- a plugin class (no-arg constructor)
- a factory function returning a plugin instance

## Plugin base class

Use `PluginBase` and `PluginContext` from `g_agent.plugins`:

```python
from g_agent.plugins import PluginBase, PluginContext


class MyPlugin(PluginBase):
    name = "my-plugin"

    def register_tools(self, registry, context: PluginContext) -> None:
        # registry.register(MyTool(...))
        pass

    def register_channels(self, channels, context: PluginContext) -> None:
        # channels["my-channel"] = MyChannel(...)
        pass
```

## Runtime behavior

- plugins are loaded from installed entry points (`g_agent.plugins`)
- load failures are logged and skipped (non-fatal)
- duplicate plugin names are skipped
- invalid channel objects from plugins are rejected

## Verification

Run gateway and confirm plugin load logs:

```bash
g-agent gateway
```

You should see:

- `Loaded plugin ...` in logs
- `Plugins loaded: ...` in CLI startup output

