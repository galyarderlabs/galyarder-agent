# Configuration

Primary config path:

```text
~/.g-agent/config.json
```

## Core sections

- `agents.defaults`: model, temperature, tool iterations, workspace path, routing policy
- `channels`: Telegram/WhatsApp/Discord channel toggles and allowlists
- `providers`: API base and key for model routing
- `tools`: shell timeout, workspace restriction, web search settings
- `google`: OAuth credentials for Gmail/Calendar/Docs/Sheets/Drive

## Safety defaults

- Enable `tools.restrictToWorkspace: true`
- Keep `allowFrom` lists strict per channel
- Use approval mode for risky tool execution
- Prefer separate profiles with `G_AGENT_DATA_DIR` (personal/guest)

## Quick sanity check

```bash
g-agent status
g-agent doctor --network
```

## Model routing policy

`agents.defaults.routing` supports:

- `mode`: `auto` | `proxy` | `direct`
- `fallbackModels`: ordered model list used when primary model fails

Recommended with OpenAI-compatible local proxy:

```json
{
  "agents": {
    "defaults": {
      "model": "gemini-3-pro-preview",
      "routing": {
        "mode": "proxy",
        "fallbackModels": ["gemini-3-flash-preview"]
      }
    }
  },
  "providers": {
    "vllm": {
      "apiKey": "sk-local-xxx",
      "apiBase": "http://127.0.0.1:8317/v1"
    }
  }
}
```
