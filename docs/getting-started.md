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

## Start runtime

```bash
g-agent gateway
```

## Channel login

```bash
g-agent channels login
```

Use Telegram/WhatsApp after login and allowlist setup.

## Systemd (recommended for 24/7)

Use service templates in `backend/agent/deploy/systemd/` and run as user units.

For day-to-day operations and diagnostics, see [Operations](operations.md).

For in-app Python usage, see [Embedding](embedding.md).
