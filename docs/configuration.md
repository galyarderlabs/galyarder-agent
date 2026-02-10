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
- `proxy_provider`: which provider to use in proxy mode (default: `vllm`)
- `fallbackModels`: ordered model list used when primary model fails

### OpenAI-compatible proxy (CLIProxyAPI, LiteLLM, etc.)

```json
{
  "agents": {
    "defaults": {
      "model": "claude-opus-4-6-thinking",
      "routing": {
        "mode": "proxy",
        "proxy_provider": "proxy",
        "fallbackModels": ["gemini-3-pro-preview", "gpt-5.3-codex"]
      }
    }
  },
  "providers": {
    "proxy": {
      "apiKey": "your-proxy-key",
      "apiBase": "http://127.0.0.1:8317/v1"
    }
  }
}
```

### vLLM inference server (backward-compatible)

```json
{
  "agents": {
    "defaults": {
      "model": "meta-llama/Llama-3-70b",
      "routing": {
        "mode": "proxy"
      }
    }
  },
  "providers": {
    "vllm": {
      "apiKey": "sk-local-xxx",
      "apiBase": "http://127.0.0.1:8000/v1"
    }
  }
}
```

### Direct provider keys

```json
{
  "agents": {
    "defaults": {
      "model": "anthropic/claude-opus-4-5",
      "routing": { "mode": "direct" }
    }
  },
  "providers": {
    "anthropic": { "apiKey": "sk-ant-xxx" }
  }
}
```
