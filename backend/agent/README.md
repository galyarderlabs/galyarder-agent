<div align="center">
  <img src="header.webp" alt="Galyarder Agent backend header" width="900">
  <h1>Galyarder Agent Backend</h1>
  <p><b>Runtime core for agentic digital identity: memory, tools, channels, visual presence, and owner-controlled execution.</b></p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
    <img src="https://img.shields.io/badge/CLI-g--agent-6f42c1" alt="g-agent CLI">
    <img src="https://img.shields.io/badge/License-MIT-22c55e" alt="MIT">
  </p>
</div>

---

## Purpose

This package contains the Python runtime behind `g-agent`.

The product direction is agentic digital identity, not a disposable chat box.
The backend is the layer that makes that identity operational:

- character profile and workspace files
- local memory and session continuity
- WhatsApp, Telegram, Discord, Email, CLI, and plugin channel surfaces
- visual identity through the `selfie` tool
- Google Workspace access through the local `gws` CLI
- scoped filesystem, shell, schedule, media, and workflow-pack tools
- local-first safety controls: `allowFrom`, `restrictToWorkspace`, policy presets, and approvals

For product narrative and public setup docs, start at the root README and MkDocs site.

---

## Quick Start

```bash
cd backend/agent
pip install -e .
g-agent onboard
g-agent status
g-agent gateway
```

Full setup:

- root README: `../../README.md`
- docs site: https://galyarderlabs.github.io/galyarder-agent/
- configuration: `../../docs/configuration.md`
- channels: `../../docs/channels.md`
- operations: `../../docs/operations.md`

---

## Runtime Layout

```text
g_agent/
  agent/          core loop, memory, tools, skills, subagents
  bus/            inbound/outbound message queue
  channels/       Telegram, WhatsApp, Discord, Email, Slack, CLI-facing surfaces
  cli/            g-agent command line
  config/         Pydantic config schema and presets
  cron/           scheduled jobs
  observability/  metrics and health
  plugins/        extension plugin loader
  providers/      model routing through LiteLLM/providers
  security/       audit and fix helpers
  session/        session persistence
  utils/          shared helpers
```

Most development work happens inside `g_agent/` and `tests/`.

---

## Development Checks

Run from `backend/agent/`:

```bash
python -m compileall -q g_agent
ruff check g_agent tests --select F
pytest -q
```

Regenerate CLI docs after CLI changes:

```bash
python scripts/generate_cli_docs.py
```

Docs build from repo root:

```bash
mkdocs build --strict
```

---

## Runtime Data

Default runtime data lives under `~/.g-agent/`:

- `config.json`: provider, channel, tool, visual, Google Workspace, and routing config
- `workspace/`: character files, memory, skills, and working context
- `sessions/`: conversation state
- `media/`: inbound/outbound media
- `cron/`: scheduled jobs

Use `G_AGENT_DATA_DIR=/path/to/profile` to isolate another character, guest profile, or test runtime.

---

## Safety Baseline

Before enabling any shared channel:

- keep `channels.*.allowFrom` strict
- keep `tools.restrictToWorkspace: true`
- add only trusted folders to `tools.allowedPaths`
- keep risky tools on approval mode
- use separate `G_AGENT_DATA_DIR` profiles for personal and guest characters
- keep credentials out of git

See `SECURITY.md` and `../../docs/security.md`.

---

## Release Notes

Public release notes live in `../../docs/release-notes/`.

The active product roadmap lives in `../../ROADMAP.md`.
