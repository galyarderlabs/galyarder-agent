# CLI Commands

_This page is auto-generated from `g_agent.cli.commands`._

Regenerate with:

```bash
python backend/agent/scripts/generate_cli_docs.py
```

## Global usage

```bash
g-agent [OPTIONS] COMMAND [ARGS]...
```

### Global options

- `--version`, `-v`: Show version.
- `--install-completion`: Install completion for the current shell.
- `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
- `--help`: Show help and exit.

## Top-level commands

| Command | Description |
| --- | --- |
| `help` | Show help for g-agent commands (alias for --help). |
| `version` | Show g-agent version. |
| `login` | Link device via QR code (alias for `channels login`). |
| `onboard` | Initialize g-agent configuration and workspace. |
| `gateway` | Start the g-agent gateway. |
| `agent` | Interact with the agent directly. |
| `digest` | Generate a daily personal digest via the agent. |
| `proactive-enable` | Install proactive cron jobs (daily digest + weekly lessons). |
| `proactive-disable` | Remove default proactive cron jobs. |
| `feedback` | Log a lesson for self-improvement memory. |
| `memory-audit` | Audit memory drift and cross-scope fact conflicts. |
| `security-audit` | Run baseline security audit for current profile. |
| `security-fix` | Plan or apply automatic security baseline remediations. |
| `metrics` | Show runtime observability metrics snapshot. |
| `status` | Show g-agent status. |
| `doctor` | Run diagnostics for model, channels, memory, and tool configuration. |
| `channels` | Manage channels. |
| `plugins` | Inspect runtime plugins. |
| `google` | Manage Google Workspace integration. |
| `cron` | Manage scheduled tasks. |
| `policy` | Manage tool policy presets. |

## `channels` subcommands

```bash
g-agent channels [COMMAND] --help
```

- `status`: Show channel status.
- `login`: Link device via QR code.

## `plugins` subcommands

```bash
g-agent plugins [COMMAND] --help
```

- `list`: List discovered plugins and effective policy status.
- `doctor`: Run diagnostics for plugin discovery and policy configuration.

## `google` subcommands

```bash
g-agent google [COMMAND] --help
```

- `status`: Show Google Workspace integration status.
- `configure`: Save Google OAuth client credentials into config.
- `auth-url`: Generate Google OAuth consent URL.
- `exchange`: Exchange OAuth code and save Google tokens into config.
- `verify`: Verify Google auth by calling Gmail profile endpoint.
- `clear`: Clear saved Google Workspace tokens from config.

## `cron` subcommands

```bash
g-agent cron [COMMAND] --help
```

- `list`: List scheduled jobs.
- `add`: Add a scheduled job.
- `remove`: Remove a scheduled job.
- `enable`: Enable or disable a job.
- `run`: Manually run a job.

## `policy` subcommands

```bash
g-agent policy [COMMAND] --help
```

- `list`: List available policy presets.
- `apply`: Apply a policy preset globally or to a channel/sender scope.
- `status`: Show current policy map grouped by scope.

## Quick examples

```bash
g-agent --help
g-agent help
g-agent version
g-agent channels --help
g-agent channels login
g-agent plugins --help
g-agent plugins list
g-agent google --help
g-agent cron --help
g-agent policy --help
```
