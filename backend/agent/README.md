<div align="center">
  <img src="header.webp" alt="Galyarder Agent header" width="900">
  <h1>Galyarder Agent Backend (g-agent)</h1>
  <p><b>The runtime core for agentic digital characters across WhatsApp, Telegram, Discord, Slack, Email, and CLI.</b></p>
  <p>
    <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
    <img src="https://img.shields.io/badge/CLI-g--agent-6f42c1" alt="g-agent CLI">
    <img src="https://img.shields.io/badge/License-MIT-22c55e" alt="MIT">
    <img src="https://img.shields.io/badge/Channels-WhatsApp%20%7C%20Telegram%20%7C%20Discord%20%7C%20Slack%20%7C%20Email-10b981" alt="Channels">
  </p>
</div>

---

## Why This Backend Exists

The product direction is not just “an assistant that can call tools.” It is a
digital character that can keep identity, remember context, appear in chat,
generate selfies or mirror photos, and act inside real workflows with explicit
permission.

This backend keeps that direction operational:

- character identity and persona files
- local memory and session continuity
- channel presence across WhatsApp, Telegram, Discord, Slack, Email, and CLI
- visual identity through the `selfie` tool
- scoped tools for workspace, shell, Google Workspace, schedules, media, and workflow packs

This is the runtime layer for building yourself as an agent, an agentic
girlfriend, a companion, an operator, or a fictional persona that is still
understandable, auditable, and locally owned.

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

- **Character first**: memory, persona, visual identity, and tool use should point at one coherent presence.
- **Useful over flashy**: the character still needs to solve real personal tasks.
- **Understandable over abstract**: keep runtime behavior inspectable.
- **Private over cloud-lock**: local memory, local workspace, local policy.
- **Controlled over magical**: explicit allowlists and tool policy gates.
- **Fork-first ownership**: adapt code to your life, not generic defaults.

If the runtime is not operationally controllable, it is not truly personal.

---

## What It Supports

- **Digital characters**: persistent persona, memory, visual identity, and channel presence.
- **Channels**: WhatsApp, Telegram, Discord, Slack, Email, CLI, and experimental Feishu paths.
- **Model routing**: LiteLLM + OpenAI-compatible providers (local proxy/vLLM/OpenRouter style).
- **Memory**: markdown-first long-term memory + structured facts.
- **Scheduling**: cron jobs + proactive reminders + workflow packs.
- **Multimodal output**: text, image, voice, sticker, document.
- **Google Workspace**: Gmail, Calendar, Drive, Docs, Sheets, Contacts through the local `gws` CLI.
- **Security controls**: `restrictToWorkspace`, `allowFrom`, tool policy, approval mode, quiet hours.

---

## Setup Guide

### 1) Configure model provider

Edit `~/.g-agent/config.json`:

**CLIProxyAPI / generic OpenAI-compatible proxy:**

```json
{
  "providers": {
    "proxy": {
      "api_key": "your-cliproxy-key",
      "api_base": "http://localhost:8317/v1"
    }
  },
  "agents": {
    "defaults": {
      "model": "gemini-3-pro-preview",
      "routing": {
        "mode": "proxy",
        "proxy_provider": "proxy",
        "fallback_models": ["gemini-3-flash-preview"]
      }
    }
  }
}
```

**vLLM / legacy proxy setup (backward-compatible):**

```json
{
  "providers": {
    "vllm": {
      "api_key": "sk-local-xxx",
      "api_base": "http://127.0.0.1:8000/v1"
    }
  },
  "agents": {
    "defaults": {
      "model": "meta-llama/Llama-3-70b",
      "routing": {
        "mode": "proxy"
      }
    }
  }
}
```

**Direct provider keys:**

```json
{
  "providers": {
    "anthropic": { "api_key": "sk-ant-xxx" },
    "gemini": { "api_key": "gsk-xxx" }
  },
  "agents": {
    "defaults": {
      "model": "claude-opus-4-6-thinking",
      "routing": { "mode": "direct" }
    }
  }
}
```

Routing modes:

- `proxy`: use the provider configured in `routing.proxy_provider` (default: `vllm`). Set `proxy_provider: "proxy"` for CLIProxyAPI.
- `direct`: resolve by provider keys (OpenAI/Anthropic/Gemini/etc) without proxy fallback.
- `auto`: explicit provider prefixes win (`gemini/...`, `openai/...`); otherwise prefer the configured proxy provider when its `api_base` is set.

### 2) Configure channels with allowlists

Telegram:

```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "BOTFATHER_TOKEN",
      "allowFrom": ["123456789"]
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

### 3) Additional channels

- Discord, Slack, and Email channel paths are available in the runtime.
- Feishu/Lark long-connection path is available as an experimental option.

---

## Google Workspace via `gws`

```bash
npm i -g @googleworkspace/cli
gws auth login --services gmail,calendar,drive,docs,sheets,people
gws auth status
```

`g-agent` executes Gmail, Calendar, Drive, Docs, Sheets, and Contacts through
the local `gws` binary. If your service environment cannot find `gws`, set an
absolute path in `~/.g-agent/config.json`:

```json
{
  "integrations": {
    "google": {
      "gwsPath": "/home/you/.local/bin/gws",
      "calendarId": "primary"
    }
  }
}
```

Leave `credentialsFile` empty for normal desktop usage so `gws` can use its
own encrypted keyring/token cache. Only set it for exported/headless
credentials.

Common scopes used by the tools:

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
g-agent security-fix
g-agent security-fix --apply
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
- `tools.allowedPaths`
- `channels.*.allowFrom`
- `tools.policy` (`allow` / `ask` / `deny`)
- `tools.approvalMode` (recommended `confirm`)
- browser denylist and runtime timeout guardrails

Recommended personal baseline:

```json
{
  "tools": {
    "restrictToWorkspace": true,
    "allowedPaths": ["/home/you/Documents/AgentMedia"],
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
g-agent security-fix
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

Protected `main` releases go through a pull request. Before publishing:

1. Update the package version and `../../docs/release-notes/vX.Y.Z.md`.
2. Regenerate CLI docs after CLI changes with `python scripts/generate_cli_docs.py`.
3. Merge the release PR after CI passes.
4. Tag the merged `main` commit and publish the GitHub Release from the release notes.

---

## Runtime Roadmap

The focused roadmap is tracked at:

- `../../docs/roadmap/runtime-roadmap.md`

The goal is to keep the runtime lean while adding high-value capabilities deliberately.

---

## License

MIT — see `../../LICENSE`.

Changelog — see `../../CHANGELOG.md`.

---

> “Digital sovereignty is not isolation — it is ascendancy with ownership: your memory, your tools, your systems, your future.”
