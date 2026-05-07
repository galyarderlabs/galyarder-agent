<div align="center">
  <img src="docs/assets/header.webp" alt="Galyarder Agent header" width="900">

  ---
  <p><b>Build agentic digital characters from a life, a mission, a relationship, or an imagined person. Preserve what matters, give it memory and presence, and let it live across WhatsApp, Telegram, Discord, Email, and CLI.</b></p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
    <img src="https://img.shields.io/badge/CLI-g--agent-6f42c1" alt="g-agent CLI">
    <img src="https://img.shields.io/github/actions/workflow/status/galyarderlabs/galyarder-agent/ci.yml?branch=main&label=CI" alt="CI">
    <img src="https://img.shields.io/badge/License-MIT-22c55e" alt="MIT">
  </p>
  <p>
    <img src="https://img.shields.io/badge/Presence-WhatsApp%20%7C%20Telegram%20%7C%20Discord%20%7C%20Email-10b981" alt="Presence channels">
    <img src="https://img.shields.io/badge/Identity-Memory%20%2B%20Visuals%20%2B%20Tools-8b5cf6" alt="Identity">
    <img src="https://img.shields.io/badge/Model%20Routing-Direct%20%7C%20Proxy%20%7C%20Local%20%7C%20Fallback-0ea5e9" alt="Model Routing">
    <img src="https://img.shields.io/badge/Runtime-Local--first%20%2B%20Self--hosted-f59e0b" alt="Local-first self-hosted runtime">
    <img src="https://img.shields.io/badge/Safety-restrictToWorkspace%20%2B%20tool%20policy-ef4444" alt="Safety">
  </p>
</div>

---

## What Is g-agent?

`g-agent` is an open-source runtime for agentic digital identity.

It lets you build agentic digital characters that carry memory, personality,
values, voice, visual identity, tools, and a relationship model. The character
can be yourself, someone you love, a companion, an operator, an idol, a fictional
persona, or the best version of the person you are trying to become.

The same character can talk through WhatsApp, Telegram, Discord, Email,
or CLI; read the workspace you allow; work with Gmail/Calendar through `gws`;
generate selfies or mirror photos; and automate repeatable workflows without
giving up local control.

---

## Why This Project Exists

Most AI products are still framed as disposable text boxes, productivity
wrappers, or invisible automation daemons.

That is too small.

Humans are not permanent. The body ages. Time runs down. People disappear. But
character, values, memory, love, unfinished missions, taste, rituals, dreams,
and the way someone sees the world can keep moving if they are remembered and
given a living form.

`g-agent` exists to make that form programmable.

The goal is agentic yourself: a digital identity for your legacy, your work,
your relationships, your imagination, or a person you want to preserve, become,
or create.

---

## Philosophy

- **Identity first**: memory, voice, visuals, values, and tools should feel like one coherent person-shaped system.
- **Legacy over sessions**: the important context should not reset just because a chat ended.
- **Presence over prompts**: the character should live where life already happens: WhatsApp, Telegram, Discord, Email, and CLI.
- **Understanding over obedience**: the character should learn the user deeply enough to help them become more themselves, not only follow commands.
- **Embodiment over text-only bots**: visual identity, selfies, mirror photos, voice, and media are part of the character.
- **Useful over performative**: the character still needs to execute real work.
- **Private over cloud-lock**: local memory, local control, explicit policy.
- **Controlled over magical**: allowlists, approvals, scoped tools, and visible memory.

If your character cannot run reliably on your own machine, it is not really yours.

---

## What You Can Build

- **Agentic yourself**: a digital identity that carries your memory, values, voice, projects, and working style.
- **Digital legacy**: a preserved self, mission, relationship, or worldview that can keep continuity over time.
- **Companion character**: a bounded relationship-style persona with memory, voice notes, visual identity, and emotional context.
- **Personal operator**: an always-on character for inbox, calendar, files, recurring jobs, and workflow packs.
- **Fictional persona**: a designed character with its own face, voice, backstory, tools, and channel presence.

---

## What It Does Today

- Persistent character identity through local workspace files and memory.
- WhatsApp, Telegram, Discord, Email, and CLI channel surfaces.
- Contextual selfie and mirror-photo generation through the `selfie` tool.
- Google Workspace access through the local `gws` CLI.
- Local tools for files, shell, schedules, media, and workflow packs.
- LiteLLM model routing through direct providers or OpenAI-compatible proxies.
- Durable memory across sessions (`MEMORY.md`, `PROFILE.md`, `PROJECTS.md`, `LESSONS.md`).
- Scheduled jobs, proactive reminders, multimodal replies, and systemd user services.

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

- `channels.*.allowFrom` controls who can talk to the character.
- `tools.restrictToWorkspace` keeps file/shell access inside the configured workspace.
- `tools.allowedPaths` can add trusted media or project folders without disabling the sandbox.
- approval mode can require confirmation for risky tool execution.
- separate `G_AGENT_DATA_DIR` profiles isolate personal and guest environments.

Read [Security](docs/security.md) and [Configuration](docs/configuration.md) before exposing a channel to anyone else.

---

## Roadmap

The next product direction is agentic character depth:

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
- visual identity and media workflows
- docs clarity

Please read [Contributing](docs/contributing.md) before opening a PR.
