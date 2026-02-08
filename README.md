<div align="center">
  <img src="backend/agent/g_agent_logo.png" alt="Galyarder Agent" width="520">
  <h1>Galyarder Agent (g-agent)</h1>
  <p><b>Private, practical, always-on personal AI assistant for Linux + Android workflows.</b></p>
  <p>
    <img src="https://img.shields.io/badge/PyPI-not%20published%20yet-6b7280" alt="PyPI not published">
    <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
    <img src="https://img.shields.io/badge/CLI-g--agent-6f42c1" alt="g-agent CLI">
    <img src="https://img.shields.io/badge/License-MIT-22c55e" alt="MIT">
  </p>
  <p>
    <img src="https://img.shields.io/badge/Channels-Telegram%20%7C%20WhatsApp%20%7C%20Discord*%20%7C%20Feishu*-10b981" alt="Channels">
    <img src="https://img.shields.io/badge/Model%20Routing-LiteLLM%20%2B%20OpenAI%20Compatible-0ea5e9" alt="Model Routing">
    <img src="https://img.shields.io/badge/Ops-systemd%20--user-f59e0b" alt="systemd user">
    <img src="https://img.shields.io/badge/Safety-restrictToWorkspace%20%2B%20tool%20policy-ef4444" alt="Safety">
  </p>
</div>

---

## Monorepo Layout

```text
.
├── backend/
│   └── agent/          # Python g-agent backend + bridge
├── landingpages/       # Next.js landing site + waitlist API
└── README.md
```

Web app docs: `landingpages/README.md`  
Backend docs: `backend/agent/README.md`

---

## Philosophy

`g-agent` is built with one clear philosophy:

- **Useful over flashy**: solve real daily tasks first.
- **Private over cloud-lock**: local workspace + local memory by default.
- **Minimal over bloated**: keep the stack lean and understandable.
- **Controllable over magical**: explicit tool policy, approvals, and allowlists.

If your assistant cannot run reliably on your own Linux machine, it is not your assistant.

---

## Architecture

<p align="center">
  <img src="backend/agent/g_agent_arch.png" alt="g-agent architecture" width="900">
</p>

---

## Core Stack

| Layer | Stack |
|---|---|
| CLI & Runtime | `Python 3.11+`, `Typer`, `Rich`, `asyncio` |
| LLM Routing | `LiteLLM` + OpenAI-compatible endpoints (vLLM/local proxy/OpenRouter/others) |
| Channels | Telegram (`python-telegram-bot`) + WhatsApp bridge (`Baileys` + Node) are primary; Discord + Feishu are available (experimental) |
| Memory | Markdown-first memory files (`MEMORY.md`, `PROFILE.md`, `PROJECTS.md`, etc.) |
| Scheduling | Built-in cron service + proactive digest/lessons jobs |
| Integrations | Google Workspace (Gmail, Calendar, Drive, Docs, Sheets, Contacts), Slack webhook, SMTP |
| Safety | `restrictToWorkspace`, `allowFrom`, browser denylist, per-tool policy, approval mode |

---

## What You Can Do Today

- Chat via CLI, Telegram, and WhatsApp (Discord/Feishu available, experimental).
- Run local-proxy models (including Gemini-compatible routes) through OpenAI-compatible APIs.
- Save and recall durable memory automatically.
- Use web/browser tools (`browser_open`, `browser_snapshot`, `browser_click`, etc.).
- Access Google Workspace (email/calendar/files/docs/sheets/contacts) via OAuth.
- Schedule proactive reminders and daily/weekly assistant jobs.

---

## Install

### From source (recommended)

```bash
git clone https://github.com/galyarderlabs/galyarder-agent.git
cd galyarder-agent/backend/agent
pip install -e .
```

### From PyPI (when published)

```bash
pip install galyarder-agent
```

> Note: package publication is pending; use source install for now.

---

## Quick Start

### 1) Initialize

```bash
g-agent onboard
```

Default data directory: `~/.g-agent`

### 2) Configure model provider

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

### 3) Chat

```bash
g-agent agent -m "Halo, siapa kamu?"
```

### 4) Check health

```bash
g-agent status
g-agent doctor --network
```

---

## CLI Commands

| Command | Purpose |
|---|---|
| `g-agent onboard` | Init config + workspace template |
| `g-agent agent -m "..."` | One-shot chat |
| `g-agent agent` | Interactive chat |
| `g-agent gateway` | Start channel gateway |
| `g-agent status` | Full runtime status |
| `g-agent doctor` | Diagnostics + fix hints |
| `g-agent feedback "..."` | Save lessons memory |
| `g-agent digest` | Generate daily digest |
| `g-agent proactive-enable` | Install default proactive jobs |
| `g-agent proactive-disable` | Remove default proactive jobs |
| `g-agent channels status` | Show channel config status |
| `g-agent channels login` | WhatsApp QR linking |
| `g-agent google configure/auth-url/exchange/verify` | Google OAuth flow |
| `g-agent cron add/list/remove/enable/run` | Scheduled jobs |

---

## Channel Setup

Supported channels and typical setup effort:

| Channel | Setup |
|---|---|
| Telegram | Easy (bot token + user ID allowlist) |
| WhatsApp | Medium (Node bridge + QR pairing) |
| Discord* | Medium (bot token + intents + invite URL) |
| Feishu* | Medium (app credentials + event subscription) |

`*` Experimental in current release.

### Telegram

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

### WhatsApp

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

> For WhatsApp bridge, use Node.js 18+.

Pair WhatsApp:

```bash
g-agent channels login
```

Then in another terminal:

```bash
g-agent gateway
```

### Discord (experimental)

1. Create app + bot in Discord Developer Portal.
2. Enable **Message Content Intent** in bot settings.
3. Get your Discord user ID (Developer Mode → Copy User ID).
4. Invite bot with permissions like `Send Messages` and `Read Message History`.

```json
{
  "channels": {
    "discord": {
      "enabled": true,
      "token": "DISCORD_BOT_TOKEN",
      "allowFrom": ["YOUR_DISCORD_USER_ID"]
    }
  }
}
```

Run:

```bash
g-agent gateway
```

### Feishu / Lark (experimental)

1. Create app on Feishu Open Platform and enable **Bot** capability.
2. Add permission to send/receive IM messages.
3. Add event subscription for message receive using **Long Connection** mode.
4. Copy `appId` and `appSecret` to config.

```json
{
  "channels": {
    "feishu": {
      "enabled": true,
      "appId": "cli_xxx",
      "appSecret": "xxx",
      "encryptKey": "",
      "verificationToken": "",
      "allowFrom": []
    }
  }
}
```

Run:

```bash
g-agent gateway
```

> Feishu long-connection mode does not require public webhook hosting.

---

## Google Workspace (OAuth)

```bash
g-agent google configure --client-id "YOUR_CLIENT_ID" --client-secret "YOUR_CLIENT_SECRET" --calendar-id "primary"
g-agent google auth-url
# open URL, approve consent, copy value after ?code=
g-agent google exchange --code "PASTE_CODE"
g-agent google verify
```

Default scopes include:
- `gmail.modify`
- `calendar`
- `drive.readonly`
- `documents`
- `spreadsheets`
- `contacts.readonly`

---

## Memory Model

Memory lives inside `workspace/memory`:

- `MEMORY.md`: durable long-term notes
- `PROFILE.md`: user identity/preferences
- `RELATIONSHIPS.md`: people context
- `PROJECTS.md`: active and backlog project context
- `LESSONS.md`: behavior improvements and feedback
- `YYYY-MM-DD.md`: daily memory note

The agent can use `remember` and `recall` tools to write/read useful context across sessions.

---

## Security Model

Primary controls:

- `tools.restrictToWorkspace`: keep file/shell actions inside workspace.
- `channels.*.allowFrom`: whitelist chat users/numbers.
- `tools.policy`: per-tool `allow` / `ask` / `deny`.
- `tools.approvalMode`: `confirm` for risky tool calls.
- Browser denylist for localhost/metadata endpoints.

Recommended baseline for personal usage:

```json
{
  "tools": {
    "restrictToWorkspace": true,
    "approvalMode": "confirm"
  }
}
```

---

## 24/7 Service Mode (systemd --user)

```bash
systemctl --user enable --now g-agent-wa-bridge.service
systemctl --user enable --now g-agent-gateway.service
```

Check:

```bash
systemctl --user status g-agent-wa-bridge.service
systemctl --user status g-agent-gateway.service
```

Optional lingering:

```bash
sudo loginctl enable-linger "$USER"
```

---

## Docker Quick Run

From repo root:

```bash
docker build -t g-agent ./backend/agent
docker run -v ~/.g-agent:/root/.g-agent --rm g-agent g-agent onboard
docker run -v ~/.g-agent:/root/.g-agent --rm g-agent g-agent status
docker run -v ~/.g-agent:/root/.g-agent -p 18790:18790 g-agent g-agent gateway
```

---

## Guest Profile Isolation (Clone Assistant Mode)

`g-agent` supports isolated profiles using `G_AGENT_DATA_DIR`.

Example guest profile:

```bash
mkdir -p ~/.g-agent-guest
G_AGENT_DATA_DIR=~/.g-agent-guest g-agent onboard
G_AGENT_DATA_DIR=~/.g-agent-guest g-agent status
```

Each profile has isolated:
- config
- workspace/memory
- cron jobs
- media/bridge data
- OAuth/session artifacts

Use separate Telegram bot token and separate WhatsApp account for guest profile.

---

## Troubleshooting

### Telegram timeout

- verify internet/proxy
- check token:

```bash
curl -sS "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"
```

### WhatsApp bridge reconnect loops

- rebuild bridge:

```bash
g-agent channels login --rebuild
```

- then restart services:

```bash
systemctl --user restart g-agent-wa-bridge.service g-agent-gateway.service
```

---

## Acknowledgements

This project stands on the shoulders of open-source work:

- [`HKUDS/nanobot`](https://github.com/HKUDS/nanobot) — lightweight personal assistant foundation and practical CLI/channel ideas.
- [`openclaw/openclaw`](https://github.com/openclaw/openclaw) — broader agent architecture inspiration for memory, tooling, and personal assistant direction.

Huge respect to both communities and contributors.

---

## License

MIT — see `LICENSE`.
