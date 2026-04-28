# Security

## Security model

Galyarder Agent is secured by layered controls: channel allowlists, workspace-aware tool guards, approval policy, and separate runtime data directories for different trust levels.

### 1. Execution Sandbox & Trusted Roots
By default, terminal commands run through `ExecTool` in a spawn-per-call local environment.

- **Restrict to workspace:** When `tools.restrictToWorkspace` is `true`, built-in filesystem tools and `ExecTool` enforce best-effort path checks against the workspace plus configured `tools.allowedPaths`. This is a guardrail for local operation, not a substitute for an OS sandbox.
- **Dangerous commands:** The shell guard blocks common destructive patterns such as `rm -rf`, `mkfs`, disk writes, power commands, and fork bombs before execution.
- **Optional isolation:** Use a dedicated OS user, container, VM, or restricted service account for untrusted users or high-risk workflows.

### 2. Channel Allowlists
- Configure `allowFrom` for every enabled network channel.
- Telegram, WhatsApp, Discord, email, and Slack channel handlers reject senders that are not on their configured allowlist.
- Keep allowlists narrow for public bot accounts and shared workspaces.

### 3. Tool Approval Policy
`tools.policy` enables granular allow, ask, or deny decisions for individual tools, optionally scoped by channel and sender ID.

- **Approval mode:** Set `tools.approvalMode` to `confirm` to require explicit `/approve` before risky tools such as `exec`, `send_email`, and `gmail_send`.
- **Policy presets:** Use `g-agent policy apply guest_readonly` to deny terminal and write-capable tools for guest scopes.

### 4. Secrets & Service Environment
- Never hardcode API keys in the SQLite database or JSONL session transcripts.
- Keep runtime secrets in `.env`, environment variables, or the local `config.json`; do not commit them.
- **WhatsApp Bridge Authentication:** Set `channels.whatsapp.bridgeToken` when running the WhatsApp bridge in production. If left empty, any process on `localhost` can connect to the bridge and impersonate the agent.
- **Service Isolation:** When running via `systemd` or `launchd`, ensure the service user has no `sudo` privileges.

### 5. Memory & Profile Separation
- The agent's identity and memory are tied to its active profile and data directory.
- To prevent guests from polluting the owner's personal memory or accessing the owner's Google Workspace context, configure a separate `G_AGENT_DATA_DIR` or use a dedicated guest profile with restricted toolsets.
- Review runtime activity with `/insights` and search past context with `/history` or the `session_search` tool.

## Minimum hardening baseline

1. Use strict channel allowlists (`allowFrom`)
2. Keep workspace restriction enabled (`restrictToWorkspace: true`)
3. Separate guest profile from personal profile
4. Scope API/OAuth permissions to least privilege
5. Monitor runtime logs and rotate secrets on suspicion
6. Set `channels.whatsapp.bridgeToken` for the WhatsApp bridge in production

## Dependency floor

The backend pins a security floor for `python-dotenv` at `>=1.2.2`. `litellm`
currently declares a narrower transitive pin, so `backend/agent/pyproject.toml`
uses `tool.uv.override-dependencies` to keep `uv lock` and `uv run` on the
patched dependency line instead of resolving back to `1.0.1`.

After dependency changes, verify the resolved environment:

```bash
cd backend/agent
uv lock
uv run python -c 'from importlib.metadata import version; print(version("python-dotenv"))'
```

## Vulnerability reporting

Use private GitHub advisories:

- https://github.com/galyarderlabs/galyarder-agent/security/advisories

Also review:

- Root policy: `SECURITY.md`
- Runtime details: `backend/agent/SECURITY.md`
