<div align="center">
  <img src="g-agent_logo.png" alt="Galyarder Agent" width="520">
  <h1>Galyarder Agent Backend (g-agent)</h1>
  <p><b>The runtime core for a private, practical, always-on personal AI assistant.</b></p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
    <img src="https://img.shields.io/badge/CLI-g--agent-6f42c1" alt="g-agent CLI">
    <img src="https://img.shields.io/badge/License-MIT-22c55e" alt="MIT">
    <img src="https://img.shields.io/badge/Channels-Telegram%20%7C%20WhatsApp%20%7C%20CLI-10b981" alt="Channels">
  </p>
</div>

---

## Why This Backend Exists

OpenClaw and Nanobot prove the direction is real: personal agents are useful when they can act in your real workflow.

This backend keeps that direction but stays focused on ownership and operational clarity:

- keep the useful parts (`agent loop`, `tools`, `memory`, `channels`, `cron`)
- remove unnecessary complexity for personal deployment
- keep control on your machine, with your policy, your allowlists, your runtime

This is not a generic “everything platform.”  
It is a practical personal assistant runtime you can understand, audit, and evolve.

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

1) configure model + keys in `~/.g-agent/config.json`  
2) configure channel allowlists  
3) pair WhatsApp (`g-agent channels login`)  
4) run gateway (`g-agent gateway`)

---

## Philosophy

- **Useful over flashy**: solve real personal tasks first.
- **Understandable over abstract**: keep runtime behavior inspectable.
- **Private over cloud-lock**: local memory, local workspace, local policy.
- **Controlled over magical**: explicit allowlists and tool policy gates.
- **Fork-first ownership**: adapt code to your life, not generic defaults.

If the runtime is not operationally controllable, it is not truly personal.

---

## What It Supports

- **Channels**: CLI, Telegram, WhatsApp (Discord/Feishu available as experimental paths).
- **Model routing**: LiteLLM + OpenAI-compatible providers (local proxy/vLLM/OpenRouter style).
- **Memory**: markdown-first long-term memory + structured facts.
- **Scheduling**: cron jobs + proactive reminders + workflow packs.
- **Multimodal output**: text, image, voice, sticker, document.
- **Google Workspace**: Gmail, Calendar, Drive, Docs, Sheets, Contacts via OAuth.
- **Security controls**: `restrictToWorkspace`, `allowFrom`, tool policy, approval mode, quiet hours.

---

## Setup Guide

### 1) Configure model provider

Edit `~/.g-agent/config.json`:

```json
{
  "providers": {
    "vllm": {
      "apiKey": "sk-local-xxx",
      "apiBase": "http://127.0.0.1:8317/v1"
    }
  },
  "agents": {
    "defaults": {
      "model": "gemini-3-pro-preview"
    }
  },
  "tools": {
    "restrictToWorkspace": true,
    "web": {
      "search": {
        "apiKey": "BSA-xxx"
      }
    }
  }
}
```

### 2) Configure channels with allowlists

Telegram:

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "BOTFATHER_TOKEN",
      "allowFrom": ["6218572023"]
    }
  }
}
```

WhatsApp:

```json
{
  "channels": {
    "whatsapp": {
      "enabled": true,
      "bridgeUrl": "ws://localhost:3001",
      "allowFrom": ["6281234567890"]
    }
  }
}
```

Pair WhatsApp bridge:

```bash
g-agent channels login
```

Start runtime:

```bash
g-agent gateway
```

### 3) Optional experimental channels

- Discord bot path is available but still experimental.
- Feishu/Lark long-connection path is available but still experimental.

---

## Google Workspace OAuth

```bash
g-agent google configure --client-id "YOUR_CLIENT_ID" --client-secret "YOUR_CLIENT_SECRET" --calendar-id "primary"
g-agent google auth-url
# approve consent, then copy the value after ?code=
g-agent google exchange --code "PASTE_CODE"
g-agent google verify
```

Default scopes include:

- `https://www.googleapis.com/auth/gmail.modify`
- `https://www.googleapis.com/auth/calendar`
- `https://www.googleapis.com/auth/drive.readonly`
- `https://www.googleapis.com/auth/documents`
- `https://www.googleapis.com/auth/spreadsheets`
- `https://www.googleapis.com/auth/contacts.readonly`

---

## Usage

CLI examples:

```bash
g-agent agent -m "Summarize my top priorities for today."
g-agent agent -m "/pack daily_brief focus revenue --sticker --silent"
g-agent proactive-enable
g-agent status
g-agent security-audit --strict
g-agent memory-audit --json
g-agent metrics
g-agent metrics --prune --retention-hours 168 --max-events 50000
g-agent metrics --dashboard-json --export ~/.g-agent/metrics.dashboard.json
g-agent gateway --metrics-endpoint --metrics-host 127.0.0.1 --metrics-port 18791
```

Channel examples:

- “Prepare my meeting context for 14:00 from calendar + inbox.”
- “Every weekday 08:30, send my daily brief.”
- “Store this as memory: I prefer concise responses.”

---

## Memory Model

Memory lives in `~/.g-agent/workspace/memory/`:

- `MEMORY.md` (durable long-term notes)
- `FACTS.md` (structured facts: confidence/source/supersedes)
- `PROFILE.md` (identity and preferences)
- `RELATIONSHIPS.md` (people context)
- `PROJECTS.md` (active/backlog context)
- `LESSONS.md` (quality and feedback learnings)
- `YYYY-MM-DD.md` (daily notes)

The runtime uses memory tools (`remember`, `recall`) to persist useful context across sessions.

---

## Workflow Packs and Proactive Jobs

Built-in packs include:

- `daily_brief`
- `meeting_prep`
- `inbox_zero_batch`

Proactive mode:

```bash
g-agent proactive-enable
g-agent proactive-disable
g-agent cron list
```

---

## Security Model

Primary controls:

- `tools.restrictToWorkspace`
- `channels.*.allowFrom`
- `tools.policy` (`allow` / `ask` / `deny`)
- `tools.approvalMode` (recommended `confirm`)
- browser denylist and runtime timeout guardrails

Recommended personal baseline:

```json
{
  "tools": {
    "restrictToWorkspace": true,
    "approvalMode": "confirm"
  }
}
```

Policy presets:

```bash
g-agent policy apply personal_full --replace-scope
g-agent policy apply guest_limited --channel telegram --sender 123456 --replace-scope
g-agent policy apply guest_readonly --channel whatsapp --sender 6281234567890 --replace-scope
```

---

## Guest Clone Mode

Use separate profiles with `G_AGENT_DATA_DIR`:

```bash
mkdir -p ~/.g-agent-guest
G_AGENT_DATA_DIR=~/.g-agent-guest g-agent onboard
G_AGENT_DATA_DIR=~/.g-agent-guest g-agent status
```

Each profile isolates:

- config
- workspace + memory
- cron schedules
- media/bridge state
- OAuth artifacts

For clean separation: use a separate Telegram bot token and separate WhatsApp account for guest mode.

---

## Service Mode (24/7)

```bash
systemctl --user enable --now g-agent-wa-bridge.service
systemctl --user enable --now g-agent-gateway.service
```

Check status:

```bash
systemctl --user status g-agent-wa-bridge.service
systemctl --user status g-agent-gateway.service
journalctl --user -u g-agent-gateway.service -u g-agent-wa-bridge.service -n 120 --no-pager
```

Optional:

```bash
sudo loginctl enable-linger "$USER"
```

---

## Installers and Uninstallers

Install scripts:

- `../../deploy/arch/install.sh`
- `../../deploy/debian/install.sh`
- `../../deploy/macos/install.sh`
- `../../deploy/windows/install.ps1`

Uninstall scripts:

- `../../deploy/arch/uninstall.sh`
- `../../deploy/debian/uninstall.sh`
- `../../deploy/macos/uninstall.sh`
- `../../deploy/windows/uninstall.ps1`

Run from remote one-liners (documented in root README), or execute scripts directly from your fork.

---

## Operations Checklist

### Lock access

- keep all enabled channels with non-empty `allowFrom`
- keep `restrictToWorkspace: true`
- keep `approvalMode: "confirm"` (or stricter)
- isolate guest/public assistants in a separate data profile

### Monitor

```bash
g-agent doctor --network
g-agent status
g-agent security-audit --strict
g-agent metrics
```

### Backup

```bash
mkdir -p ~/.g-agent-backups
tar -czf ~/.g-agent-backups/g-agent-$(date +%F).tar.gz \
  ~/.g-agent/config.json \
  ~/.g-agent/workspace/memory \
  ~/.g-agent/cron
```

### Rotate keys safely

```bash
NEW_TG_TOKEN='YOUR_NEW_TOKEN'
tmp=$(mktemp) && jq --arg v "$NEW_TG_TOKEN" '.channels.telegram.token = $v' ~/.g-agent/config.json > "$tmp" && mv "$tmp" ~/.g-agent/config.json
systemctl --user restart g-agent-gateway.service
```

```bash
NEW_BRAVE_KEY='YOUR_NEW_BRAVE_KEY'
tmp=$(mktemp) && jq --arg v "$NEW_BRAVE_KEY" '.tools.web.search.apiKey = $v' ~/.g-agent/config.json > "$tmp" && mv "$tmp" ~/.g-agent/config.json
systemctl --user restart g-agent-gateway.service
```

---

## Troubleshooting

Telegram timeout:

```bash
curl -sS "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"
```

WhatsApp bridge reconnect loops:

```bash
g-agent channels login --rebuild
systemctl --user restart g-agent-wa-bridge.service g-agent-gateway.service
```

---

## Development and Releases

Core commands:

- `g-agent status`
- `g-agent doctor --network`
- `g-agent policy list`
- `g-agent cron list`
- `g-agent channels status`

Release automation is handled in repository root by `../../.github/workflows/release.yml`.  
Update `../../CHANGELOG.md`, push `main`, then push a version tag (`vX.Y.Z` style).

---

## OpenClaw Delta Roadmap

The focused delta roadmap is tracked at:

- `../../docs/roadmap/openclaw-delta.md`

The goal is to keep the runtime lean while adding high-value capabilities deliberately.

---

## Acknowledgements

This runtime is built with respect for upstream inspiration:

- [`HKUDS/nanobot`](https://github.com/HKUDS/nanobot)
- [`openclaw/openclaw`](https://github.com/openclaw/openclaw)

This project keeps that spirit while prioritizing personal ownership and operational discipline.

---

## License

MIT — see `../../LICENSE`.

Changelog — see `../../CHANGELOG.md`.

---

> “Digital sovereignty is not isolation — it is ascendancy with ownership: your memory, your tools, your systems, your future.”
