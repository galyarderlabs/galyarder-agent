# Embedding in Python

Use `g-agent` directly in your Python app with the embeddable `Agent` API.

## Basic usage

```python
from g_agent.agent import Agent

agent = Agent()
result = agent.ask_sync("Summarize my top priorities today")
print(result)
```

## Async usage

```python
from g_agent.agent import Agent

agent = Agent()
result = await agent.ask("Draft a short project update")
```

## Custom provider and plugins

```python
from g_agent.agent import Agent

agent = Agent(
    provider=my_provider,
    plugins=[my_plugin],
)
```

## Notes

- `ask_sync()` is for synchronous contexts only.
- If you already run an event loop, use `await agent.ask(...)`.
- By default, the API loads config from `~/.g-agent/config.json`.
