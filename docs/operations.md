# Operations

## Core commands

```bash
g-agent status
g-agent doctor --network
g-agent gateway
g-agent agent -m "Daily brief"
g-agent new                     # clear cli:default session (archived)
g-agent new --all --yes         # clear all sessions
g-agent new --channel whatsapp  # clear WhatsApp sessions only
```

For incident handling patterns, see [Troubleshooting](troubleshooting.md).

## Logs

```bash
journalctl --user -u g-agent-gateway.service -u g-agent-wa-bridge.service -f
```

## Service mode

For an always-on local character, run the gateway and WhatsApp bridge as user
services.

```bash
systemctl --user enable --now g-agent-wa-bridge.service
systemctl --user enable --now g-agent-gateway.service
```

Check service health:

```bash
systemctl --user status g-agent-wa-bridge.service
systemctl --user status g-agent-gateway.service
```

Optional lingering keeps user services alive after logout:

```bash
sudo loginctl enable-linger "$USER"
```

## Proactive jobs

- Enable reminders/jobs via runtime config
- Validate loaded jobs in startup logs
- Keep schedule logic explicit and auditable

## Upgrades

Use pinned environments when possible and re-run checks:

```bash
cd backend/agent
python -m compileall -q g_agent
ruff check g_agent tests --select F
pytest -q
```

## Backup

Back up:

- `~/.g-agent/config.json`
- `~/.g-agent/workspace/`
- Google Workspace `gws` auth state, usually `~/.config/gws/`

Example:

```bash
mkdir -p ~/.g-agent-backups
tar -czf ~/.g-agent-backups/g-agent-$(date +%F).tar.gz \
  ~/.g-agent/config.json \
  ~/.g-agent/workspace \
  ~/.g-agent/cron \
  ~/.config/gws
```

## Profile isolation

Use separate data directories for personal characters, guest characters, or
test runtimes.

```bash
mkdir -p ~/.g-agent-guest
G_AGENT_DATA_DIR=~/.g-agent-guest g-agent onboard
G_AGENT_DATA_DIR=~/.g-agent-guest g-agent status
```

Each profile has isolated config, memory, sessions, cron jobs, bridge data, and
OAuth/session artifacts.

## Rotate channel keys

Edit `~/.g-agent/config.json`, then restart services.

```bash
NEW_TG_TOKEN='YOUR_NEW_TOKEN'
tmp=$(mktemp)
jq --arg v "$NEW_TG_TOKEN" '.channels.telegram.token = $v' ~/.g-agent/config.json > "$tmp"
mv "$tmp" ~/.g-agent/config.json
systemctl --user restart g-agent-gateway.service
```
