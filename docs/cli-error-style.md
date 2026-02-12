# CLI Error Style Guide

Use this format for all `g-agent` CLI failures:

1. **Cause**: short, explicit, actionable.
2. **Fix**: exact next step (`command` or `config` path).
3. **Exit code**:
   - `0` for help/info/no-op states.
   - `1` for real failures requiring user action.

## Standard Pattern

- Error line: `Cannot bind bridge port 3001 (permission denied: ...).`
- Fix line: `Fix: Check sandbox/firewall/permissions, or change channels.whatsapp.bridgeUrl to another free port.`

## Rules

- Do not emit vague messages like `failed` without context.
- Do not print raw stack traces for expected operational failures.
- Include concrete identifiers when possible:
  - provider name
  - port number
  - job ID
  - config file path
- Prefer one failure reason per branch; avoid mixed/ambiguous output.

## Code Convention

Use `g_agent/cli/commands.py` helper:

- `_cli_fail(cause, fix, exit_code=1)`

This keeps wording and formatting consistent across commands.
