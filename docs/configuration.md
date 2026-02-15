# Configuration

Primary config path:

```text
~/.g-agent/config.json
```

## Core sections

- `agents.defaults`: model, temperature, tool iterations, workspace path, routing policy
- `channels`: Telegram, WhatsApp, Email, Slack channel toggles and allowlists
- `providers`: API base, key, and extra headers for model routing
- `tools`: shell timeout, workspace restriction, web search settings
- `visual`: selfie generation — image provider, physical description, prompt templates
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
      "model": "claude-opus-4-6-thinking",
      "routing": { "mode": "direct" }
    }
  },
  "providers": {
    "anthropic": { "apiKey": "sk-ant-xxx" }
  }
}
```

## Provider registry

Provider-specific logic (environment variables, model prefixes, parameter overrides) is
driven by a declarative registry in `providers/registry.py`. The registry auto-detects
providers from model names or explicit configuration — no manual if-elif setup required.

### Supported providers

| Provider | Keywords | Env Key | Notes |
| --- | --- | --- | --- |
| Anthropic | `claude` | `ANTHROPIC_API_KEY` | Direct |
| OpenAI | `gpt`, `o1`, `o3`, `o4` | `OPENAI_API_KEY` | Direct |
| Gemini | `gemini` | `GEMINI_API_KEY` | Prefixed `gemini/` |
| DeepSeek | `deepseek` | `DEEPSEEK_API_KEY` | Direct |
| Groq | `groq` | `GROQ_API_KEY` | Direct |
| Zhipu | `glm`, `zhipu` | `ZHIPUAI_API_KEY` | Prefixed `zai/` |
| Moonshot | `moonshot`, `kimi` | `MOONSHOT_API_KEY` | Prefixed `moonshot/` |
| DashScope | `dashscope`, `qwen` | `DASHSCOPE_API_KEY` | Direct |
| OpenRouter | `openrouter` | `OPENROUTER_API_KEY` | Gateway, prefixed `openrouter/` |
| AiHubMix | `aihubmix` | `AIHUBMIX_API_KEY` | Gateway |
| Ollama | `ollama` | `OLLAMA_API_KEY` | Local |

### Extra headers

Some providers (e.g., AiHubMix) require custom HTTP headers. Configure via `extra_headers`:

```json
{
  "providers": {
    "aihubmix": {
      "apiKey": "your-key",
      "apiBase": "https://api.aihubmix.com/v1",
      "extra_headers": {
        "APP-Code": "your-app-code"
      }
    }
  }
}
```

### Gateway auto-detection

Gateways (OpenRouter, AiHubMix) are auto-detected by:

1. **`provider_name`** from config key (e.g., `"openrouter"`)
2. **API key prefix** (e.g., `sk-or-` → OpenRouter)
3. **API base URL** keyword (e.g., `aihubmix` in URL → AiHubMix)

## Channel configuration

See [Channels](channels.md) for full setup guides for:

- **Email**: IMAP/SMTP with consent-gated access and sender allowlists
- **Slack**: Socket Mode with group policies and DM controls
- **Telegram**: Bot token with numeric user ID allowlists
- **WhatsApp**: QR-paired bridge with sender ID allowlists and optional `bridgeToken` auth

## Runtime plugins

`g-agent` can load extension plugins from Python entry points (`g_agent.plugins`).

Policy fields under `tools.plugins`:

- `enabled`: disable/enable plugin loading globally
- `allow`: optional plugin name allowlist
- `deny`: optional plugin name denylist (overrides allow)

See [Plugins](plugins.md) for plugin SDK, policy examples, and verification steps.

## Visual identity (selfie generation)

The `visual` section enables AI-generated selfie photos with consistent appearance.

### Setup

1. Provide a reference photo or write a physical description manually
2. Configure an image generation provider
3. Enable the feature

### Provider options

| Provider | Config `provider` | Cost | Notes |
| --- | --- | --- | --- |
| HuggingFace | `huggingface` | Free | Rate limited ~1000/5min |
| Cloudflare Workers AI | `cloudflare` | Free | ~2000 img/day, requires `accountId` |
| Nebius | `nebius` | $0.001/img | OpenAI-compatible |
| OpenAI-compatible | `openai-compatible` | Varies | Local vLLM, ComfyUI, etc. |

### Example: Cloudflare (free)

```json
{
  "visual": {
    "enabled": true,
    "referenceImage": "~/Photos/myphoto.jpg",
    "imageGen": {
      "provider": "cloudflare",
      "apiKey": "your-cf-api-token",
      "accountId": "your-cloudflare-account-id",
      "model": "@cf/black-forest-labs/flux-1-schnell"
    }
  }
}
```

### Example: HuggingFace (free)

```json
{
  "visual": {
    "enabled": true,
    "physicalDescription": "25-year-old man with short black hair, brown eyes",
    "imageGen": {
      "provider": "huggingface",
      "apiKey": "hf_xxxxx",
      "model": "black-forest-labs/FLUX.1-schnell"
    }
  }
}
```

### Fields

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `enabled` | bool | `false` | Enable selfie generation |
| `referenceImage` | string | `""` | Path to reference photo for vision extraction |
| `physicalDescription` | string | `""` | Physical traits (auto-extracted or manual) |
| `imageGen.provider` | string | `""` | Provider name |
| `imageGen.apiKey` | string | `""` | Provider API key |
| `imageGen.apiBase` | string | `""` | Custom endpoint URL |
| `imageGen.model` | string | `""` | Model identifier |
| `imageGen.accountId` | string | `""` | Cloudflare account ID |
| `imageGen.timeout` | int | `30` | Request timeout (seconds) |
| `defaultFormat` | string | `"jpeg"` | Output image format |
| `promptTemplates` | object | (builtin) | `mirror` and `direct` prompt templates |
| `mirrorKeywords` | list | (builtin) | Keywords triggering mirror selfie mode |
| `directKeywords` | list | (builtin) | Keywords triggering direct selfie mode |

### How it works

1. **One-time setup:** Vision LLM extracts physical traits from reference photo → saved to `physicalDescription`
2. **Every selfie:** Physical description is injected into prompt template → sent to text-to-image provider
3. **Delivery:** Generated image saved locally → sent via existing media pipeline (Telegram/WhatsApp/etc.)

If `physicalDescription` is already set (manually or from previous extraction), the reference image is not needed again.
