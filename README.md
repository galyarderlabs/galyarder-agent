<div align="center">
  <img src="backend/agent/g-agent_logo.png" alt="Galyarder Agent" width="520">
  <h1>Galyarder Agent (g-agent)</h1>
  <p><b>My personal AI assistant I can actually understand, control, and evolve for my own workflow.</b></p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
    <img src="https://img.shields.io/badge/CLI-g--agent-6f42c1" alt="g-agent CLI">
    <img src="https://img.shields.io/badge/License-MIT-22c55e" alt="MIT">
    <img src="https://img.shields.io/badge/Channels-Telegram%20%7C%20WhatsApp%20%7C%20CLI-10b981" alt="Channels">
  </p>
</div>

---

## Why I Built This

OpenClaw and Nanobot are both strong projects with big vision.  
But for my personal life stack, I need an assistant I can audit, tune, and trust quickly.

`g-agent` is the answer to that tradeoff:

- I keep the powerful parts (agent loop, tools, channels, memory, scheduling).
- I remove unclear complexity where possible.
- I keep control in my own machine, own profile, own policy.

This repo is intentionally practical: built for real day-to-day execution, not feature theater.

---

## Quick Start

```bash
git clone https://github.com/galyarderlabs/galyarder-agent.git
cd galyarder-agent/backend/agent
pip install -e .
g-agent onboard
g-agent status
```

Then:

- configure model/provider in `~/.g-agent/config.json`
- pair channels (`g-agent channels login` for WhatsApp)
- run gateway (`g-agent gateway`)

Detailed setup, channel config, OAuth, and ops docs are in `backend/agent/README.md`.

Live docs (GitHub Pages): https://galyarderlabs.github.io/galyarder-agent/

---

## Philosophy

- **Useful over flashy**: real outcomes first.
- **Understandable over abstract**: a codebase you can reason about.
- **Private over cloud-lock**: local workspace, local memory, local control.
- **Controlled over chaotic**: allowlists, policy gates, approval mode, scoped profiles.
- **Fork-first ownership**: your assistant should match your life, not generic defaults.

If your assistant is not under your operational control, it is not really your assistant.

---

## What It Supports

- **Channels**: CLI, Telegram, WhatsApp (Discord/Feishu available as experimental paths).
- **Model routing**: LiteLLM + OpenAI-compatible endpoints (local proxy/vLLM/OpenRouter style).
- **Memory**: durable markdown memory (`MEMORY.md`, `PROFILE.md`, `PROJECTS.md`, `LESSONS.md`).
- **Proactive behavior**: cron jobs, perfect-day reminders, calendar lead-time nudges.
- **Workflow packs**: `daily_brief`, `meeting_prep`, `inbox_zero_batch`.
- **Multimodal output**: text + image + voice + sticker + document.
- **Google Workspace**: Gmail, Calendar, Drive, Docs, Sheets, Contacts (OAuth).
- **Safety boundaries**: `restrictToWorkspace`, `allowFrom`, tool policy presets, guest scopes.

---

## Usage

From CLI:

```bash
g-agent agent -m "Summarize my priorities for today."
g-agent agent -m "/pack daily_brief focus revenue --sticker --silent"
g-agent proactive-enable
```

From Telegram/WhatsApp:

- ask normal questions
- request scheduled reminders
- run workflow packs
- send image/voice context and get multimodal replies

Admin-style intents (examples):

- “List all scheduled jobs and their next run time.”
- “Prepare meeting context from calendar and inbox for 14:00.”
- “Send me a morning brief every weekday at 08:30.”

---

## Customizing

`g-agent` is designed for direct customization.

- tune behavior in code (`backend/agent/g_agent`)
- tune policy/runtime via `~/.g-agent/config.json`
- isolate profiles with `G_AGENT_DATA_DIR` (personal vs guest)
- extend capabilities through skills and targeted tool additions

No need to maintain config sprawl for every preference.  
If your behavior needs are unique, modify the code intentionally.

---

## Contributing

Keep the core sharp:

- accept: security fixes, reliability fixes, clarity improvements, meaningful performance wins
- avoid: bloating core with every optional channel/integration by default

Preferred pattern for optional expansion: add skills/workflows/docs that let users transform their own fork cleanly.

---

## Request for Skills (RFS)

High-value additions we want contributors to package cleanly:

- `/add-telegram-hardening` (advanced Telegram control + moderation boundaries)
- `/add-slack` (Slack channel path with scoped policy profile)
- `/add-discord` (Discord production-ready flow, not just experimental)
- `/setup-windows` (WSL2-focused deployment path)
- `/add-clear` (context compaction command with safe memory carry-over)
- `/add-google-admin-pack` (meeting + follow-up + weekly review orchestration)

---

## Requirements

- Linux, macOS, or Windows
- Python `3.11+`
- Node.js `20+` (required for WhatsApp bridge)
- Optional:
  - Docker (containerized run mode)
  - `ffmpeg` + `espeak-ng` (enhanced voice output)

---

## Architecture

<p align="center">
  <img src="backend/agent/g-agent_arch.png" alt="g-agent architecture" width="900">
</p>

Execution model (high level):

`Channel Input (CLI/Telegram/WhatsApp) -> Message Bus -> Agent Loop -> Tools + Memory + Cron/Proactive -> Outbound Dispatcher`

Runtime notes:

- Python process for agent runtime
- Node bridge process for WhatsApp transport
- local filesystem as operational state

---

## Security Model

Security is policy + scope driven:

- `tools.restrictToWorkspace` limits file/shell operations to allowed workspace
- `channels.*.allowFrom` gates who can talk to the agent
- tool policy presets (`personal_full`, `guest_limited`, `guest_readonly`)
- approval mode for risky actions
- separate data profiles for personal and guest assistants

For a stricter setup, run the stack under isolated runtime boundaries (for example dedicated user profile or containerized deployment) with minimal mounted paths.

---

## Main Branch Safety

For this public repo, use **GitHub branch protection** as the primary guard for `main`.

Recommended required checks:

- `Docs Checks`
- `Backend Agent Checks`
- `Analyze (python)`
- `Analyze (javascript-typescript)`

Optional local guard for maintainers:

```bash
bash deploy/install-local-guard.sh
G_AGENT_PRE_PUSH_MODE=changed git push origin main
```

---

## FAQ

### Why not just use OpenClaw directly?

Use OpenClaw if you want its full platform surface.  
Use `g-agent` if you want a leaner personal stack you can customize quickly with less cognitive overhead.

### Is this only for Telegram/WhatsApp?

Those are primary channels today. CLI is first-class.  
Discord/Feishu paths exist and can be hardened further.

### Is this secure enough for personal use?

It is designed with operational controls (`allowFrom`, tool policy, workspace restriction, profile separation).  
Still, you should review your own config and keep secrets/token scope tight.

### Can I run this 24/7?

Yes. Typical setup uses user services and health checks.  
See `backend/agent/README.md` for systemd flow and operational commands.

### How do I debug issues fast?

Use:

- `g-agent status`
- `g-agent doctor --network`
- `journalctl --user -u g-agent-gateway.service -u g-agent-wa-bridge.service -n 120 --no-pager`

---

## Docs

- Docs site: https://galyarderlabs.github.io/galyarder-agent/
- Docs source: `docs/`
- Backend docs: `backend/agent/README.md`
- Roadmap: `docs/roadmap/openclaw-delta.md`
- Changelog: `CHANGELOG.md`
- Security notes: `SECURITY.md` and `backend/agent/SECURITY.md`
- Contributing guide: `CONTRIBUTING.md`
- Code of Conduct: `CODE_OF_CONDUCT.md`

---

## Acknowledgements

Respect to projects that inspired this direction:

- [`HKUDS/nanobot`](https://github.com/HKUDS/nanobot)
- [`openclaw/openclaw`](https://github.com/openclaw/openclaw)

This project keeps that spirit while prioritizing personal ownership, practical reliability, and operational clarity.

---

## License

MIT — see `LICENSE`.

---

> “Digital sovereignty is not isolation — it is ascendancy with ownership: your memory, your tools, your systems, your future.”
