# FAQ

## What is `g-agent` for?

`g-agent` is a self-hosted personal assistant runtime for execution workflows:

- chat ops (CLI, Telegram, WhatsApp, Email, Slack)
- memory and context persistence
- scheduled reminders/jobs
- controlled tool execution under local policies

## Which channels are supported?

- CLI
- Telegram
- WhatsApp
- Email (IMAP/SMTP with consent gate)
- Slack (Socket Mode)

Discord/Feishu paths may exist in code, but primary supported channels are the five above.

## Can I use local model endpoints (OpenAI-compatible proxy)?

Yes. Set `routing.proxy_provider` to `"proxy"` and configure `providers.proxy` with your endpoint's `apiBase` + `apiKey` in `~/.g-agent/config.json`. This works with CLIProxyAPI, vLLM, LiteLLM, or any OpenAI-compatible endpoint. See [Configuration](configuration.md) for examples.

**Note:** The provider registry does not interfere with proxy mode. Custom model names pass through without modification.

## Which LLM providers are supported out of the box?

Anthropic, OpenAI, Gemini, DeepSeek, Groq, Zhipu, Moonshot, DashScope, OpenRouter, AiHubMix, and Ollama. Provider-specific logic (env vars, model prefixes, parameter overrides) is handled automatically by the declarative provider registry.

## What is the provider registry?

A declarative system that replaces hardcoded if-elif chains for provider configuration. It auto-detects providers from model names, sets environment variables, applies correct LiteLLM prefixes, and handles model-specific parameter overrides. See [Configuration → Provider registry](configuration.md#provider-registry).

## Does memory persist across sessions?

Yes. Memory is persisted under your profile workspace (for example `~/.g-agent/workspace/memory/`).

## Can `g-agent` send proactive reminders/tasks?

Yes. It supports cron/scheduled workflows and proactive message jobs.

## Can I still run this privately for personal use?

Yes. The runtime remains local-first with profile and policy controls.

## How do I keep it secure by default?

Minimum baseline:

- keep `tools.restrictToWorkspace: true`
- keep strict `allowFrom` lists per channel
- use separate data profiles for personal vs guest workloads
- scope integration credentials to least privilege
- for Email: ensure `consent_granted` is only `true` when you explicitly approve mailbox access

## Can I isolate guest users from personal data?

Yes. Use separate profiles (`G_AGENT_DATA_DIR`) and limited policy presets.

## How do I debug runtime issues quickly?

Use:

- `g-agent status`
- `g-agent doctor --network`
- `journalctl --user -u g-agent-gateway.service -u g-agent-wa-bridge.service -n 120 --no-pager`

## Where should I start contributing?

Read:

1. [Contributing](contributing.md)
2. [Security](security.md)
3. [Runtime Roadmap](roadmap/runtime-roadmap.md)
