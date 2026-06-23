<div align="center">
  <img src="docs/assets/header.webp" alt="Galyarder Agent header" width="900">

  ---
  <p><b>Build your agentic company and autonomous workforce. Give your operations persistent memory, presence, and execution systems across WhatsApp, Telegram, Discord, Email, and CLI.</b></p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
    <img src="https://img.shields.io/badge/CLI-g--agent-6f42c1" alt="g-agent CLI">
    <img src="https://img.shields.io/github/actions/workflow/status/galyarderlabs/galyarder-agent/ci.yml?branch=main&label=CI" alt="CI">
    <img src="https://img.shields.io/badge/License-MIT-22c55e" alt="MIT">
  </p>
  <p>
    <img src="https://img.shields.io/badge/Presence-WhatsApp%20%7C%20Telegram%20%7C%20Discord%20%7C%20Email-10b981" alt="Presence channels">
    <img src="https://img.shields.io/badge/Identity-Memory%20%2B%20Ledger%20%2B%20Tools-8b5cf6" alt="Identity">
    <img src="https://img.shields.io/badge/Model%20Routing-Direct%20%7C%20Proxy%20%7C%20Local%20%7C%20Fallback-0ea5e9" alt="Model Routing">
    <img src="https://img.shields.io/badge/Runtime-Local--first%20%2B%20Self--hosted-f59e0b" alt="Local-first self-hosted runtime">
    <img src="https://img.shields.io/badge/Safety-restrictToWorkspace%20%2B%20tool%20policy-ef4444" alt="Safety">
  </p>
</div>

---

## What Is g-agent?

`g-agent` is an open-source runtime for building your agentic company and autonomous workforce.

It lets you deploy agentic systems and digital entities that carry persistent memory, domain expertise, custom tools, and execution models. These agents can act as your autonomous departments—managing financial operations, customer interactions, document processing, workflows, and communication channels under your direction.

The same agent can correspond through WhatsApp, Telegram, Discord, Email, or CLI; process within the local workspace you allow; work with Gmail/Calendar through `gws`; and automate repeatable business workflows without giving up local control.

---

## Why This Project Exists

Most AI products are still framed as disposable chat boxes, generic productivity wrappers, or isolated automation tools.

That is too small.

A single builder, developer, creator, or small team should have the execution power of an entire corporation. Yet, custom workflows, persistent memory, action ledgers, and multi-channel orchestration remain complex to set up and run privately.

`g-agent` exists to make autonomous business execution programmable, private, and persistent.

The goal is the agentic company: a self-hosted workforce that executes your goals, manages your state, coordinates workflows, and interacts across the channels you choose, while keeping you in full sovereignty.

---

## Philosophy

- **Execution first**: persistent memory, custom tools, and communication channels should form a unified, reliable workflow.
- **Persistence over sessions**: your company state, ledgers, and records should endure across chats and restarts.
- **Presence over text boxes**: agents should operate directly where your business communicates—WhatsApp, Telegram, Discord, Email, and CLI.
- **Sovereignty over cloud-lock**: local memory, local configuration, and explicit policy controls.
- **Control over automation magic**: explicit permission gates, approvals, allowlists, and auditable action logs.
- **Proof over spectacle**: every agent action must connect to actual code execution, file changes, database commits, or network requests.

If your autonomous workforce cannot run reliably on your local machine, it is not truly yours.

---

## What You Can Build

- **Autonomous Departments**: specialized agent entities representing Finance, Devops, Content/Growth, or Customer Support, working in parallel.
- **Personal Operator**: an always-on system managing your email inbox, calendar, files, scheduled crons, and custom workflow pipelines.
- **Agentic Company Core**: a unified local command layer coordinating tools like Google Workspace (gws), Slack, and Discord.
- **Digital Mirror**: a persistent reflection of your professional goals, coding standards, and decision protocols that operates autonomously when you are offline.

---

## What It Does Today

- Persistent company identity and goals through local workspace files and SQLite.
- WhatsApp, Telegram, Discord, Email, and CLI channel interfaces.
- Google Workspace integration through the local `gws` CLI.
- Secure local tools for file editing, shell executions, task schedules, and custom workflow tools.
- Multi-model routing through direct providers, local inference, or OpenAI-compatible proxies.
- Durable agent memory across sessions (`MEMORY.md`, `PROFILE.md`, `PROJECTS.md`, `LESSONS.md`).
- Scheduled jobs, cron triggers, event listeners, and user-level systemd daemons.

For the full setup guide, use the docs site: https://galyarderlabs.github.io/galyarder-agent/

---

## Quick Start

```bash
git clone https://github.com/galyarderlabs/galyarder-agent.git
cd galyarder-agent/backend/agent
pip install -e .
g-agent onboard
g-agent status
g-agent gateway
```

Requirements: Python `3.11+`, Node.js `20+` for the WhatsApp bridge, and a configured model provider.

For installers, channel setup, proxy routing, Google Workspace, and service mode, read the docs:

- [Getting Started](docs/getting-started.md)
- [Install Matrix](docs/install-matrix.md)
- [Configuration](docs/configuration.md)
- [Channels](docs/channels.md)
- [Operations](docs/operations.md)
- [Troubleshooting](docs/troubleshooting.md)

Docs site: https://galyarderlabs.github.io/galyarder-agent/

---

## Architecture

<p align="center">
  <img src="docs/assets/architecture.webp" alt="g-agent architecture" width="900">
</p>

Core flow:

`Channel Input -> Identity + Memory Context -> Agent Loop -> Tools + Scheduler -> Response -> Learning Loop`

Runtime pieces:

- Python backend runtime in `backend/agent`
- Node.js WhatsApp bridge in `backend/agent/bridge`
- local config, memory, sessions, cron, and media under `~/.g-agent`
- MkDocs documentation in `docs/`

---

## Safety Model

`g-agent` is designed for personal, local-first operation with explicit boundaries.

- `channels.*.allowFrom` controls who can talk to the character/agent.
- `tools.restrictToWorkspace` keeps file/shell access inside the configured workspace.
- `tools.allowedPaths` can add trusted media or project folders without disabling the sandbox.
- approval mode can require confirmation for risky tool execution.
- separate `G_AGENT_DATA_DIR` profiles isolate personal and guest environments.

Read [Security](docs/security.md) and [Configuration](docs/configuration.md) before exposing a channel to anyone else.

---

## Roadmap

The next product direction is agentic company depth:

- SQLite session store and searchable recall: first slice shipped.
- Shared command controls for history, sessions, logs, approve, and deny: core shipped.
- Character profiles, skill management, routines, toolsets, MCP stdio/SSE/streamable HTTP, subagents, Memory Manager, background reviewer, product API, and insights: first slices exist.
- Owner-reviewed learning queue: model/list-inspect plus skill edit/apply/rollback exists; non-skill apply flows remain.
- Web UI, WebSocket channel, `/v1/responses`, and Docker backend: not shipped yet.

See [ROADMAP.md](ROADMAP.md).

---

## Reference Research

The project is currently using Nanobot and Hermes Agent as references, not upstreams to merge wholesale.

- `nanobot-ref/` informs Web UI, WebSocket/API, channel reliability, MCP, runner, and test patterns.
- `hermes-agent-ref/` informs session search, memory manager, learning loop, skills, approvals, context compression, and routines.

See [Hermes And Nanobot Reference Audit](docs/reports/hermes-nanobot-reference-audit.md).

---

## Contributing

Focused contributions are welcome:

- safety and approval hardening
- channel reliability
- memory and session search
- tools and workflow integration
- docs clarity

Please read [Contributing](docs/contributing.md) before opening a PR.
