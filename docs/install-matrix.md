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

### Arch Linux

- Install: `bash deploy/arch/install.sh`
- Uninstall: `bash deploy/arch/uninstall.sh`

### Debian/Ubuntu

- Install: `bash deploy/debian/install.sh`
- Uninstall: `bash deploy/debian/uninstall.sh`

### macOS

- Install: `bash deploy/macos/install.sh`
- Uninstall: `bash deploy/macos/uninstall.sh`

### Windows (PowerShell)

- Install: `powershell -ExecutionPolicy Bypass -File deploy/windows/install.ps1`
- Uninstall: `powershell -ExecutionPolicy Bypass -File deploy/windows/uninstall.ps1`

**Note:** `g-agent onboard` is safe to re-run after upgrades — it merges new config defaults without overwriting your existing settings.

## Post-install checklist

1. Confirm provider/model in `~/.g-agent/config.json`
2. Set strict `allowFrom` for Telegram/WhatsApp
3. Keep `tools.restrictToWorkspace: true`
4. Run `g-agent doctor --network`
5. Start gateway and monitor logs
