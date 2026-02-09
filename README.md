<div align="center">
  <img src="backend/agent/g-agent_logo.png" alt="Galyarder Agent" width="520">
  <h1>Galyarder Agent (g-agent)</h1>
  <p><b>Sovereignty-first AI assistant runtime for real daily workflows.</b></p>
  <p><b>Python 3.11+ · g-agent CLI · CI · MIT</b></p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
    <img src="https://img.shields.io/badge/CLI-g--agent-6f42c1" alt="g-agent CLI">
    <img src="https://img.shields.io/github/actions/workflow/status/galyarderlabs/galyarder-agent/ci.yml?branch=main&label=CI" alt="CI">
    <img src="https://img.shields.io/badge/License-MIT-22c55e" alt="MIT">
  </p>
</div>

---

## What Is g-agent?

`g-agent` is an open-source assistant runtime you run on your own machine, with your own policies, through channels you already use (CLI, Telegram, WhatsApp).

It is built for one outcome: practical automation without losing control.

---

## Why This Project Exists

Most assistant projects drift to one of two extremes:

- feature-heavy platforms with unclear internals,
- minimal demos that look clean but break in real operations.

`g-agent` is built in the middle.

It keeps the powerful parts (agent loop, tools, memory, scheduling, integrations) while keeping the runtime understandable and auditable.

If your assistant can act but you cannot explain what it can access, who can talk to it, and where it runs, it is not really your assistant.

---

## Philosophy

- **Useful over flashy**: solve real tasks first.
- **Understandable over abstract**: keep code and behavior inspectable.
- **Private over cloud-lock**: local memory, local control, explicit policy.
- **Controlled over magical**: allowlists, approvals, scoped tools.

If your assistant cannot run reliably on your own machine, it is not your assistant.

---

## What You Can Do Today

- Chat through **CLI**, **Telegram**, or **WhatsApp**.
- Run **local/OpenAI-compatible models** through LiteLLM routing.
- Keep durable memory across sessions (`MEMORY.md`, `PROFILE.md`, `PROJECTS.md`, `LESSONS.md`).
- Schedule recurring jobs and proactive reminders.
- Run workflow packs like `daily_brief`, `meeting_prep`, and `inbox_zero_batch`.
- Send multimodal replies (text, image, voice, sticker, document).
- Connect Google Workspace (Gmail, Calendar, Drive, Docs, Sheets, Contacts).

---

## Requirements

- Linux, macOS, or Windows
- Python `3.11+`
- Node.js `20+` (for WhatsApp bridge)
- Optional: `ffmpeg` + `espeak-ng` (voice output quality)

---

## Quick Start

### Option A: Installer script (recommended)

| OS | Command |
|---|---|
| Arch / Arch-based | `curl -fsSL https://raw.githubusercontent.com/galyarderlabs/galyarder-agent/main/deploy/arch/install.sh \| bash` |
| Debian / Ubuntu | `curl -fsSL https://raw.githubusercontent.com/galyarderlabs/galyarder-agent/main/deploy/debian/install.sh \| bash` |
| macOS | `curl -fsSL https://raw.githubusercontent.com/galyarderlabs/galyarder-agent/main/deploy/macos/install.sh \| bash` |
| Windows (PowerShell) | `irm https://raw.githubusercontent.com/galyarderlabs/galyarder-agent/main/deploy/windows/install.ps1 \| iex` |

### Option B: From source

```bash
git clone https://github.com/galyarderlabs/galyarder-agent.git
cd galyarder-agent/backend/agent
pip install -e .
```

### First run

```bash
g-agent onboard
g-agent status
g-agent gateway
```

Then set provider/model in `~/.g-agent/config.json`.

---

## Uninstall

| OS | Command |
|---|---|
| Arch / Arch-based | `curl -fsSL https://raw.githubusercontent.com/galyarderlabs/galyarder-agent/main/deploy/arch/uninstall.sh \| bash` |
| Debian / Ubuntu | `curl -fsSL https://raw.githubusercontent.com/galyarderlabs/galyarder-agent/main/deploy/debian/uninstall.sh \| bash` |
| macOS | `curl -fsSL https://raw.githubusercontent.com/galyarderlabs/galyarder-agent/main/deploy/macos/uninstall.sh \| bash` |
| Windows (PowerShell) | `irm https://raw.githubusercontent.com/galyarderlabs/galyarder-agent/main/deploy/windows/uninstall.ps1 \| iex` |

---

## Usage Examples

From CLI:

```bash
g-agent agent -m "Summarize my priorities for today."
g-agent agent -m "/pack daily_brief focus revenue --sticker --silent"
g-agent proactive-enable
```

From Telegram/WhatsApp:

- Ask questions.
- Request reminders.
- Trigger workflow packs.
- Send images/voice and get multimodal responses.

---

## Core Commands

| Command | Purpose |
|---|---|
| `g-agent onboard` | Initialize config and workspace |
| `g-agent status` | Runtime and integration status |
| `g-agent gateway` | Run Telegram/WhatsApp gateway |
| `g-agent agent -m "..."` | One-shot chat from CLI |
| `g-agent channels login` | Pair WhatsApp via QR |
| `g-agent doctor --network` | Connectivity diagnostics |
| `g-agent proactive-enable` | Enable default proactive jobs |
| `g-agent cron list` | List scheduled jobs |

---

## Architecture

<p align="center">
  <img src="backend/agent/g-agent_arch.png" alt="g-agent architecture" width="900">
</p>

Execution flow:

`Channel Input -> Message Bus -> Agent Loop -> Tools + Memory + Scheduler -> Outbound Dispatcher`

Runtime model:

- Python process for agent runtime
- Node.js bridge for WhatsApp transport
- local filesystem for state and memory

---

## Security Model (Plain Language)

- `tools.restrictToWorkspace` keeps file/shell access inside allowed workspace.
- `channels.*.allowFrom` controls who can send messages to the assistant.
- approval mode can require confirmation for risky actions.
- policy presets (`personal_full`, `guest_limited`, `guest_readonly`) control tool risk.
- separate profiles via `G_AGENT_DATA_DIR` isolate personal and guest environments.

For details, read `SECURITY.md` and `backend/agent/SECURITY.md`.

---

## FAQ

### Why not just use OpenClaw?

Use OpenClaw if you want a broader platform surface and larger built-in ecosystem.  
Use `g-agent` if you want a leaner runtime with faster auditability and simpler day-to-day ops.

### How is this different from Nanobot?

Nanobot provides a lightweight and practical base.  
`g-agent` builds on similar principles but adds stronger opinionated flow for sovereignty, policy presets, workflow packs, cross-platform installers, and richer operational docs.

### Is this trying to replace OpenClaw or Nanobot?

No. This project is a focused fork-direction for operators who prefer tight control, simple operations, and practical personal-assistant behavior.

### Can I use this as my always-on personal assistant?

Yes. The typical production flow is user services + allowlists + restricted workspace + approval mode.

### Is it safe enough for personal data?

It is built with practical controls (`allowFrom`, `restrictToWorkspace`, approvals, profile isolation).  
You still need to review your configuration and keep tokens scoped/rotated.

---

## Documentation

- Docs site: https://galyarderlabs.github.io/galyarder-agent/
- Getting started: `docs/getting-started.md`
- Configuration: `docs/configuration.md`
- Channels: `docs/channels.md`
- Install matrix: `docs/install-matrix.md`
- Operations: `docs/operations.md`
- Troubleshooting: `docs/troubleshooting.md`
- FAQ: `docs/faq.md`
- Backend docs: `backend/agent/README.md`
- Roadmap: `docs/roadmap/openclaw-delta.md`
- Changelog: `CHANGELOG.md`

---

## Contributing

We welcome focused contributions:

- security hardening,
- reliability improvements,
- performance improvements,
- documentation clarity.

Please read `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md` before opening a PR.

---

## Acknowledgements

With respect to projects that inspired this direction:

- [`HKUDS/nanobot`](https://github.com/HKUDS/nanobot)
- [`openclaw/openclaw`](https://github.com/openclaw/openclaw)

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=galyarderlabs/galyarder-agent&type=Date)](https://star-history.com/#galyarderlabs/galyarder-agent&Date)

---

> “Digital sovereignty is not isolation — it is ownership with execution.”
