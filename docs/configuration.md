# Configuration

Primary config path:

```text
~/.g-agent/config.json
```

## Core sections

- `agents.defaults`: model, temperature, tool iterations, workspace path
- `channels`: Telegram/WhatsApp/Discord channel toggles and allowlists
- `providers`: API base and key for model routing
- `tools`: shell timeout, workspace restriction, web search settings
- `google`: OAuth credentials for Gmail/Calendar/Docs/Sheets/Drive

## Safety defaults

- Enable `tools.restrictToWorkspace: true`
- Keep `allowFrom` lists strict per channel
- Use approval mode for risky tool execution
- Prefer separate profiles with `G_AGENT_DATA_DIR` (personal/guest)

## Quick sanity check

```bash
g-agent status
g-agent doctor --network
```
