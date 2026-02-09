<div align="center">
  <img src="backend/agent/g-agent_logo.png" alt="Galyarder Agent" width="520">
  <h1>Galyarder Agent (g-agent)</h1>
  <p><b>Open-source, sovereignty-first AI agent runtime for private operations across CLI, Telegram, and WhatsApp.</b></p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
    <img src="https://img.shields.io/badge/CLI-g--agent-6f42c1" alt="g-agent CLI">
    <img src="https://img.shields.io/badge/License-MIT-22c55e" alt="MIT">
    <img src="https://img.shields.io/badge/Channels-Telegram%20%7C%20WhatsApp%20%7C%20CLI-10b981" alt="Channels">
  </p>
</div>

---

## Mission

`g-agent` is built for one goal: **digital sovereignty in daily AI operations**.

That means:

- you control where the agent runs,
- you control which models and tools it can use,
- you control who can reach it,
- and you can audit every operational decision in code and logs.

This repository is a public, production-oriented foundation that favors clarity, safety boundaries, and predictable behavior over feature sprawl.

---

## Why This Project Exists

Many agent projects optimize for breadth. `g-agent` optimizes for **operational ownership**:

- **Local-first control**: data, memory, and runtime state live in your environment.
- **Inspectable architecture**: practical code paths that can be reviewed and customized quickly.
- **Policy-driven safety**: allowlists, workspace boundaries, approval gates, and profile presets.
- **Reliable automation**: scheduling, proactive reminders, workflow packs, and service-mode operation.

`g-agent` takes inspiration from strong open-source predecessors and focuses on shipping a hardening-friendly runtime you can trust in real workflows.

---

## Core Capabilities

- **Channels**: CLI, Telegram, WhatsApp (Discord/Feishu paths available as experimental).
- **Model routing**: LiteLLM + OpenAI-compatible endpoints (local proxy/vLLM/OpenRouter-style).
- **Memory system**: persistent markdown memory (`MEMORY.md`, `PROFILE.md`, `PROJECTS.md`, `LESSONS.md`).
- **Proactive behavior**: cron scheduling, recurring reminders, perfect-day routines, calendar nudges.
- **Workflow packs**: `daily_brief`, `meeting_prep`, `inbox_zero_batch`.
- **Multimodal output**: text, image, voice, sticker, and document responses.
- **Google Workspace**: Gmail, Calendar, Drive, Docs, Sheets, Contacts via OAuth.
- **Safety controls**: `restrictToWorkspace`, `allowFrom`, approval mode, and policy presets (`personal_full`, `guest_limited`, `guest_readonly`).

---

## Architecture

<p align="center">
  <img src="backend/agent/g-agent_arch.png" alt="g-agent architecture" width="900">
</p>

High-level execution flow:

`Channel Input -> Message Bus -> Agent Loop -> Tools + Memory + Scheduler/Proactive -> Outbound Dispatcher`

Runtime components:

- Python process for the core agent loop and tool execution.
- Node.js bridge process for WhatsApp transport.
- Local filesystem for state, memory, and operational artifacts.

---

## Quick Start

### 1) Clone

```bash
git clone https://github.com/galyarderlabs/galyarder-agent.git
cd galyarder-agent
```

### 2) Install (by platform)

- **Arch Linux**
  ```bash
  bash deploy/arch/install.sh
  ```
- **Debian/Ubuntu**
  ```bash
  bash deploy/debian/install.sh
  ```
- **macOS**
  ```bash
  bash deploy/macos/install.sh
  ```
- **Windows (PowerShell)**
  ```powershell
  powershell -ExecutionPolicy Bypass -File deploy/windows/install.ps1
  ```

### 3) Onboard and verify

```bash
g-agent onboard
g-agent status
```

Then configure your provider/model in `~/.g-agent/config.json`, pair channels (`g-agent channels login` for WhatsApp), and run:

```bash
g-agent gateway
```

---

## Service Mode (Always On)

For persistent runtime on Linux/macOS with user services:

```bash
systemctl --user status g-agent-gateway.service
systemctl --user status g-agent-wa-bridge.service
journalctl --user -u g-agent-gateway.service -u g-agent-wa-bridge.service -n 120 --no-pager
```

Ops helpers:

- `deploy/ops/healthcheck.sh`
- `deploy/ops/backup.sh`

---

## Security Model

`g-agent` is designed around constrained execution, not blind trust:

- **Workspace boundaries**: `tools.restrictToWorkspace` limits filesystem and shell scope.
- **Identity gates**: per-channel `allowFrom` controls who can interact with the runtime.
- **Policy presets**: enforce different risk profiles for personal vs guest assistants.
- **Approval mode**: explicit confirmation for risky actions.
- **Profile isolation**: separate data directories for personal and guest contexts.

See `SECURITY.md` and `backend/agent/SECURITY.md` for implementation details.

---

## Documentation

- Docs site: https://galyarderlabs.github.io/galyarder-agent/
- Getting started: `docs/getting-started.md`
- Installation matrix: `docs/install-matrix.md`
- Configuration: `docs/configuration.md`
- Channels: `docs/channels.md`
- Operations: `docs/operations.md`
- Troubleshooting: `docs/troubleshooting.md`
- Security: `docs/security.md`
- FAQ: `docs/faq.md`
- Backend developer docs: `backend/agent/README.md`
- Roadmap: `docs/roadmap/openclaw-delta.md`
- Changelog: `CHANGELOG.md`

---

## Contributing

We welcome focused, high-signal contributions:

- security hardening,
- reliability and observability improvements,
- performance wins with measurable impact,
- documentation clarity and operator UX.

Please read:

- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`

---

## Acknowledgements

This project is inspired by open-source agent work from:

- [`HKUDS/nanobot`](https://github.com/HKUDS/nanobot)
- [`openclaw/openclaw`](https://github.com/openclaw/openclaw)

`g-agent` extends those ideas with a sovereignty-first operational focus for modern personal and small-team deployments.

---

> “Digital sovereignty is not a feature toggle. It is an architecture decision.”
