# Security Policy — Galyarder Agent (`g-agent`)

This document defines the practical security model for running `g-agent` as a personal assistant, plus the minimum controls required before shared access.

---

## Security Philosophy

`g-agent` uses a **policy-first** security posture:

- explicit access control (`allowFrom`)
- explicit tool boundaries (`restrictToWorkspace`, tool policy)
- explicit operator approvals (`approvalMode`)
- explicit profile separation (personal vs guest data dirs)

This keeps the runtime understandable and controllable, while staying lightweight.

---

## Threat Model (Practical)

Primary risks:

1. unauthorized message sender reaches your channels
2. sensitive token/key leakage from config or logs
3. over-permissive tool execution (filesystem/shell/network)
4. shared profile leaks personal memory/context to guest users
5. compromised integration tokens (Telegram, WhatsApp, Google, Brave, etc.)

`g-agent` mitigates these with allowlists, workspace restriction, per-tool policy, and operator confirmation.  
You still need correct host-level hygiene (file permissions, key rotation, profile separation).

---

## Report a Vulnerability

If you find a security issue:

1. do **not** publish exploit details in public issues
2. open a private advisory via GitHub Security tab
3. include:
   - affected version/commit
   - reproduction steps
   - impact
   - suggested mitigation (if known)

Target initial response: within `48` hours.

---

## Minimum Baseline (Required)

Before exposing Telegram/WhatsApp:

- set `tools.restrictToWorkspace = true`
- set `tools.approvalMode = "confirm"` (or stricter)
- ensure non-empty `channels.*.allowFrom` for every enabled channel
- run as normal user (never root)
- separate personal and guest profiles (`G_AGENT_DATA_DIR`)

Baseline example:

```json
{
  "tools": {
    "restrictToWorkspace": true,
    "approvalMode": "confirm"
  },
  "channels": {
    "telegram": {
      "allowFrom": ["6218572023"]
    },
    "whatsapp": {
      "allowFrom": ["6281234567890"]
    }
  }
}
```

Quick baseline verification:

```bash
g-agent security-audit --strict
```

---

## Secrets and Key Management

`g-agent` stores operational secrets in profile config. Lock file permissions:

```bash
chmod 700 ~/.g-agent
chmod 600 ~/.g-agent/config.json
chmod 700 ~/.g-agent/whatsapp-auth
```

Rules:

- never commit secrets to git
- rotate immediately after accidental exposure
- use separate credentials for personal and guest profiles
- keep OAuth tokens scoped to minimum required permissions

---

## Channel Access Control

`allowFrom` is the first security wall.

- empty allowlist means open channel access
- Telegram values should be numeric user IDs
- WhatsApp values should be normalized numbers (E.164 recommended)
- guest mode should use separate bot identity (Telegram token + WA account)

Validate sender IDs from logs before allowing new users.

---

## Tool Safety and Policy

Core controls:

- workspace boundary checks (with `restrictToWorkspace=true`)
- dangerous shell pattern blocking
- per-tool policy (`allow` / `ask` / `deny`)
- approval mode for sensitive actions
- browser denylist for localhost/metadata-style targets
- execution timeouts and output truncation

Recommended posture:

- keep write/exec/send-like tools on `ask` in mixed-access setups
- deny tools you do not need
- prefer separate profile + stricter policy for guest assistants

Policy shortcuts:

```bash
g-agent policy apply personal_full --replace-scope
g-agent policy apply guest_limited --channel telegram --sender 123456 --replace-scope
g-agent policy apply guest_readonly --channel whatsapp --sender 6281234567890 --replace-scope
```

---

## Profile Isolation (Personal vs Guest)

Use separate data dirs:

```bash
mkdir -p ~/.g-agent-guest
G_AGENT_DATA_DIR=~/.g-agent-guest g-agent onboard
G_AGENT_DATA_DIR=~/.g-agent-guest g-agent status
```

Each profile isolates:

- config + secrets
- memory/workspace
- cron jobs
- bridge/media/auth artifacts
- integration tokens

Do not share one profile between personal and public/guest traffic.

---

## Google Workspace Security

If Google integration is enabled:

- use dedicated OAuth client for this assistant
- keep refresh token private
- keep guest profile Google integration disabled by default
- revoke tokens immediately from Google Account Security on suspicion
- review scopes periodically and remove unused access

---

## Runtime Hardening

For 24/7 operation:

```bash
systemctl --user enable --now g-agent-wa-bridge.service
systemctl --user enable --now g-agent-gateway.service
```

Recommended extras:

- enable linger only for trusted local user (`sudo loginctl enable-linger "$USER"`)
- keep host OS patched
- restrict shell account access on host
- avoid running unrelated services under same user profile

---

## Dependency Hygiene

Python:

```bash
pip install pip-audit
pip-audit
```

Node bridge:

```bash
cd bridge
npm audit
```

Keep runtime dependencies updated on a regular schedule.

---

## Incident Response

If compromise is suspected:

1. revoke exposed API keys/tokens immediately
2. stop runtime services:
   ```bash
   systemctl --user stop g-agent-gateway.service g-agent-wa-bridge.service
   ```
3. inspect recent logs:
   ```bash
   journalctl --user -u g-agent-gateway.service -u g-agent-wa-bridge.service --since "2 hours ago" --no-pager
   ```
4. rotate credentials and re-auth integrations
5. verify policy and allowlists
6. restart services only after validation

---

## Current Limitations

Known tradeoffs to keep the project lean:

- no built-in global rate limiter
- secrets are plaintext in local profile config
- operational logging, not full SIEM-grade audit trail
- guardrail model, not full sandbox virtualization by default

If you need stricter isolation, deploy with additional host/container controls.

---

## Security Checklist

Before production-like usage:

- [ ] `restrictToWorkspace=true`
- [ ] `approvalMode=confirm` (or stricter)
- [ ] non-empty allowlists on all enabled channels
- [ ] non-root runtime user
- [ ] strict file permissions on config/auth directories
- [ ] audited dependencies (Python + Node bridge)
- [ ] personal and guest profiles fully separated

---

## References

- Advisories: `https://github.com/galyarderlabs/galyarder-agent/security/advisories`
- Releases: `https://github.com/galyarderlabs/galyarder-agent/releases`
- Main docs: `../../README.md`
- Backend docs: `README.md`
