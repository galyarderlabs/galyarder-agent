<div align="center">
  <img src="backend/agent/g-agent_logo.png" alt="Galyarder Agent" width="520">
  <h1>Galyarder Agent (g-agent)</h1>
  <p><b>Sovereignty-first AI assistant runtime for real daily workflows.</b></p>
  <p>
    <img src="https://img.shields.io/badge/PyPI-not%20published%20yet-6b7280" alt="PyPI not published">
    <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
    <img src="https://img.shields.io/badge/CLI-g--agent-6f42c1" alt="g-agent CLI">
    <img src="https://img.shields.io/github/actions/workflow/status/galyarderlabs/galyarder-agent/ci.yml?branch=main&label=CI" alt="CI">
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

### Installer flags (optional)

- Common:
  - `G_AGENT_INSTALL_DIR=/path/to/repo` (default: `~/galyarder-agent`)
  - `G_AGENT_DATA_DIR=/path/to/data` (default: `~/.g-agent`)
- Arch:
  - `G_AGENT_SKIP_PACMAN=1`
  - `G_AGENT_SKIP_SERVICES=1`
  - `G_AGENT_AUTO_START_SERVICES=0`
- Debian/Ubuntu:
  - `G_AGENT_SKIP_APT=1`
  - `G_AGENT_SKIP_SERVICES=1`
  - `G_AGENT_AUTO_START_SERVICES=0`
- macOS:
  - `G_AGENT_SKIP_BREW=1`
  - `G_AGENT_SETUP_LAUNCHD=1`
  - `G_AGENT_AUTO_START_SERVICES=0`
- Windows:
  - `G_AGENT_SKIP_WINGET=1`
  - `G_AGENT_SETUP_TASKS=1`

---

## Uninstall

| OS | Command |
|---|---|
| Arch / Arch-based | `curl -fsSL https://raw.githubusercontent.com/galyarderlabs/galyarder-agent/main/deploy/arch/uninstall.sh \| bash` |
| Debian / Ubuntu | `curl -fsSL https://raw.githubusercontent.com/galyarderlabs/galyarder-agent/main/deploy/debian/uninstall.sh \| bash` |
| macOS | `curl -fsSL https://raw.githubusercontent.com/galyarderlabs/galyarder-agent/main/deploy/macos/uninstall.sh \| bash` |
| Windows (PowerShell) | `irm https://raw.githubusercontent.com/galyarderlabs/galyarder-agent/main/deploy/windows/uninstall.ps1 \| iex` |

Optional flags:

- `G_AGENT_REMOVE_SERVICES=0` keep startup services/tasks
- `G_AGENT_REMOVE_REPO=1` remove repo directory
- `G_AGENT_WIPE_DATA=1` remove full `~/.g-agent` data

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
| `g-agent channels status` | Show channel config status |
| `g-agent google configure/auth-url/exchange/verify` | Google OAuth flow |
| `g-agent doctor --network` | Connectivity diagnostics |
| `g-agent proactive-enable` | Enable default proactive jobs |
| `g-agent cron add/list/remove/enable/run` | Manage scheduled jobs |

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

Pair WhatsApp:

```bash
g-agent channels login
g-agent gateway
```

### Discord / Feishu (experimental)

- See `docs/channels.md` for full step-by-step setup.
- Keep `allowFrom` strict for any public-facing deployment.

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

Memory lives in `workspace/memory`:

- `MEMORY.md`: long-term notes
- `PROFILE.md`: identity/preferences
- `RELATIONSHIPS.md`: people context
- `PROJECTS.md`: active project context
- `LESSONS.md`: behavior improvements
- `YYYY-MM-DD.md`: daily memory notes

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

```bash
docker build -t g-agent ./backend/agent
docker run -v ~/.g-agent:/root/.g-agent --rm g-agent g-agent onboard
docker run -v ~/.g-agent:/root/.g-agent --rm g-agent g-agent status
docker run -v ~/.g-agent:/root/.g-agent -p 18790:18790 g-agent g-agent gateway
```

---

## Guest Profile Isolation

```bash
mkdir -p ~/.g-agent-guest
G_AGENT_DATA_DIR=~/.g-agent-guest g-agent onboard
G_AGENT_DATA_DIR=~/.g-agent-guest g-agent status
```

Each profile has isolated config, memory, cron jobs, bridge data, and OAuth/session artifacts.

---

## Troubleshooting

### Telegram timeout

```bash
curl -sS "https://api.telegram.org/bot<YOUR_TOKEN>/getMe"
```

### WhatsApp bridge reconnect loops

```bash
g-agent channels login --rebuild
systemctl --user restart g-agent-wa-bridge.service g-agent-gateway.service
```

---

## Production Checklist

### 1) Lock access

- Keep `channels.*.allowFrom` non-empty on enabled channels.
- Keep `tools.restrictToWorkspace: true`.
- Keep `tools.approvalMode: "confirm"` or stricter.
- Use separate `G_AGENT_DATA_DIR` for guest/public assistants.

### 2) Monitor health

```bash
g-agent doctor --network
systemctl --user status g-agent-gateway.service g-agent-wa-bridge.service
journalctl --user -u g-agent-gateway.service -u g-agent-wa-bridge.service -n 120 --no-pager
```

### 3) Backup critical state

```bash
mkdir -p ~/.g-agent-backups
tar -czf ~/.g-agent-backups/g-agent-$(date +%F).tar.gz \
  ~/.g-agent/config.json \
  ~/.g-agent/workspace/memory \
  ~/.g-agent/cron
```

### 4) Rotate keys safely

```bash
NEW_TG_TOKEN='YOUR_NEW_TOKEN'
tmp=$(mktemp) && jq --arg v "$NEW_TG_TOKEN" '.channels.telegram.token = $v' ~/.g-agent/config.json > "$tmp" && mv "$tmp" ~/.g-agent/config.json
systemctl --user restart g-agent-gateway.service
```

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

## OpenClaw Delta Roadmap

Roadmap and implementation status:

- `docs/roadmap/openclaw-delta.md`

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

## License

MIT — see `LICENSE`.

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=galyarderlabs/galyarder-agent&type=Date)](https://star-history.com/#galyarderlabs/galyarder-agent&Date)

---

> “Digital sovereignty is not isolation — it is ascendancy with ownership: your memory, your tools, your systems, your future.”
