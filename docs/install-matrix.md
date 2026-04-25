# Install Matrix

Use this matrix to choose the cleanest deployment path per environment.

## Runtime matrix

| Platform | Backend runtime | WhatsApp bridge | Service mode | Notes |
| --- | --- | --- | --- | --- |
| Linux | Native Python venv | Native Node.js 20+ | systemd user units | Recommended primary path |
| macOS | Native Python venv | Native Node.js 20+ | LaunchAgent or foreground | systemd user units are Linux-only |
| Windows | WSL2 (recommended) | WSL2 Node.js | user shell / task scheduler | Keep runtime in one WSL distro |

## Quick install commands

### Linux/macOS

```bash
git clone https://github.com/galyarderlabs/galyarder-agent.git
cd galyarder-agent/backend/agent
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
g-agent onboard
g-agent status
```

### Windows (WSL2)

```bash
git clone https://github.com/galyarderlabs/galyarder-agent.git
cd galyarder-agent/backend/agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
g-agent onboard
g-agent status
```

## Script-based install/uninstall

If you prefer bootstrap scripts instead of manual setup, use `deploy/*`:

### Linux

- Install: `bash deploy/linux/install.sh`
- Uninstall: `bash deploy/linux/uninstall.sh`

### macOS

- Install: `bash deploy/macos/install.sh`
- Uninstall: `bash deploy/macos/uninstall.sh`

### Windows (PowerShell)

- Install: `powershell -ExecutionPolicy Bypass -File deploy/windows/install.ps1`
- Uninstall: `powershell -ExecutionPolicy Bypass -File deploy/windows/uninstall.ps1`

**Note:** `g-agent onboard` is safe to re-run after upgrades — it merges new config defaults without overwriting your existing settings.

## Installer flags

Use these environment variables when you need a narrower install.

Common:

| Variable | Purpose |
| --- | --- |
| `G_AGENT_INSTALL_DIR=/path/to/repo` | Override install checkout path. |
| `G_AGENT_DATA_DIR=/path/to/data` | Override runtime data directory. |

Linux:

| Variable | Purpose |
| --- | --- |
| `G_AGENT_SKIP_SERVICES=1` | Do not install systemd user services. |
| `G_AGENT_AUTO_START_SERVICES=0` | Install service files but do not start them. |
| `G_AGENT_SKIP_PACKAGES=1` | Skip package-manager dependency install. |

macOS:

| Variable | Purpose |
| --- | --- |
| `G_AGENT_SKIP_BREW=1` | Skip Homebrew dependency install. |
| `G_AGENT_SETUP_LAUNCHD=1` | Install LaunchAgent service files. |
| `G_AGENT_AUTO_START_SERVICES=0` | Install service files but do not start them. |

Windows:

| Variable | Purpose |
| --- | --- |
| `G_AGENT_SKIP_WINGET=1` | Skip winget dependency install. |
| `G_AGENT_SETUP_TASKS=1` | Install scheduled task helpers. |

## Uninstall flags

| Variable | Purpose |
| --- | --- |
| `G_AGENT_REMOVE_SERVICES=0` | Keep startup services/tasks. |
| `G_AGENT_REMOVE_REPO=1` | Remove the repo directory. |
| `G_AGENT_WIPE_DATA=1` | Remove full `~/.g-agent` runtime data. |

## Post-install checklist

1. Confirm provider/model in `~/.g-agent/config.json`
2. Set strict `allowFrom` for Telegram/WhatsApp
3. Keep `tools.restrictToWorkspace: true`
4. Run `g-agent doctor --network`
5. Start gateway and monitor logs
