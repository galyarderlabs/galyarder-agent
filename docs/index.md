# Galyarder Agent Docs

Galyarder Agent (`g-agent`) is a practical, self-hosted personal assistant runtime.

![Galyarder Agent](assets/logo-wordmark.svg)

<div class="gagent-hero">
  <p><b>Private by default.</b> Operate from your own machine, with your own policies.</p>
  <p><b>Practical by design.</b> Focus on channels, memory, automation, and auditability.</p>
</div>

## What you get

- Multi-channel assistant: CLI, Telegram, WhatsApp
- LLM routing through configurable OpenAI-compatible proxies (CLIProxyAPI, vLLM, LiteLLM, etc.)
- Persistent memory in local Markdown files
- Proactive scheduling, cron-based reminders, workflow packs
- Policy controls for workspace access, approvals, and guest limits

## Who this is for

This project is for builders who want:

- strong local control
- auditable behavior
- production utility over hype

## Start here

1. [Getting Started](getting-started.md)
2. [Install Matrix](install-matrix.md)
3. [Configuration](configuration.md)
4. [Operations](operations.md)
5. [Troubleshooting](troubleshooting.md)
6. [Security](security.md)

## Codebase map

- Backend runtime: `backend/agent`
- Docs source: `docs/`
- Project roadmap: `docs/roadmap/runtime-roadmap.md`

## Open-source navigation

- Common operator questions: [FAQ](faq.md)
- Contribution expectations: [Contributing](contributing.md)

## Architecture

![g-agent architecture](https://raw.githubusercontent.com/galyarderlabs/galyarder-agent/main/backend/agent/g-agent_arch.png)

<p class="gagent-note"><i>Execution path: channel input → agent loop → tools/memory/scheduler → outbound dispatch.</i></p>
