# FAQ

## What is `g-agent` for?

`g-agent` is a self-hosted personal assistant runtime for execution workflows:

- chat ops (CLI, Telegram, WhatsApp)
- memory and context persistence
- scheduled reminders/jobs
- controlled tool execution under local policies

## Which channels are supported?

- CLI
- Telegram
- WhatsApp

Discord/Feishu paths may exist in code, but primary supported channels are the three above.

## Can I use local model endpoints (OpenAI-compatible proxy)?

Yes. Set `routing.proxy_provider` to `"proxy"` and configure `providers.proxy` with your endpoint's `apiBase` + `apiKey` in `~/.g-agent/config.json`. This works with CLIProxyAPI, vLLM, LiteLLM, or any OpenAI-compatible endpoint. See [Configuration](configuration.md) for examples.

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
3. [OpenClaw Delta Roadmap](roadmap/openclaw-delta.md)
