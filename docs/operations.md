# Operations

## Core commands

```bash
g-agent status
g-agent doctor --network
g-agent gateway
g-agent agent -m "Daily brief"
```

For incident handling patterns, see [Troubleshooting](troubleshooting.md).

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

## Release checklist

Before tagging a release (`vX.Y.Z`):

1. Update version metadata in:
   - `backend/agent/pyproject.toml`
   - `backend/agent/g_agent/__init__.py`
   - `backend/agent/uv.lock`
2. Update release docs:
   - `CHANGELOG.md`
   - `docs/release-notes/vX.Y.Z.md` (must exist and be non-empty)
3. Run backend checks:

```bash
cd backend/agent
python -m compileall -q g_agent
ruff check g_agent tests --select F
pytest -q
```

4. Open PR, merge to `main`, then push tag:

```bash
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

Notes:

- CI enforces that version-bump PRs include non-empty `docs/release-notes/vX.Y.Z.md`.
- Release workflow publishes GitHub release notes from that file.

## Backup

Back up:

- `~/.g-agent/config.json`
- `~/.g-agent/workspace/`
- OAuth credentials and tokens stored in your profile path
