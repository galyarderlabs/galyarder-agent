# Getting Started

## Requirements

- Python 3.11+
- Node.js 20+ (WhatsApp bridge)
- Linux/macOS/Windows

For platform-specific paths, see [Install Matrix](install-matrix.md).

## Install

```bash
git clone https://github.com/galyarderlabs/galyarder-agent.git
cd galyarder-agent/backend/agent
pip install -e .
```

## First run

```bash
g-agent onboard
g-agent status
```

`onboard` is safe to re-run — it merges new defaults into your existing config without overwriting customizations like API keys.

## Start runtime

```bash
g-agent gateway
```

## Channel login

```bash
g-agent channels login
```

Use WhatsApp after QR login and allowlist setup. Telegram only needs bot-token
configuration plus the sender allowlist.

## Systemd (recommended for 24/7 on Linux)

The Linux installer can create the user units for you. If you install manually,
use the commands in [Operations](operations.md) after creating matching
`g-agent-gateway.service` and `g-agent-wa-bridge.service` user units.

For day-to-day operations and diagnostics, see [Operations](operations.md).

For in-app Python usage, see [Embedding](embedding.md).
