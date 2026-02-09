# Operations

## Core commands

```bash
g-agent status
g-agent doctor --network
g-agent gateway
g-agent agent -m "Daily brief"
```

## Logs

```bash
journalctl --user -u g-agent-gateway.service -u g-agent-wa-bridge.service -f
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
- OAuth credentials and tokens stored in your profile path
