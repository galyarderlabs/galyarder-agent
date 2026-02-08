# Security Policy — Galyarder Agent (`g-agent`)

This document defines practical security guidance for running `g-agent` in real life (personal or shared mode).

---

## Report a Vulnerability

If you find a security issue:

1. **Do not** open a public issue with exploit details.
2. Use GitHub Security Advisory (private) on this repository.
3. Include:
   - affected version/commit
   - reproducible steps
   - impact
   - mitigation (if known)

Target initial response: **within 48 hours**.

---

## Security Baseline (Recommended)

Use this baseline before exposing any channel:

- Set `tools.restrictToWorkspace=true`
- Set `tools.approvalMode="confirm"`
- Use non-empty `channels.*.allowFrom`
- Run as normal user (never root)
- Keep separate profiles for personal vs guest (`G_AGENT_DATA_DIR`)

Example:

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

---

## Secrets & API Keys

Secrets are stored in config files. Protect them:

```bash
chmod 700 ~/.g-agent
chmod 600 ~/.g-agent/config.json
chmod 700 ~/.g-agent/whatsapp-auth
```

Notes:

- Never commit tokens/keys into git.
- Rotate keys immediately after accidental exposure.
- Prefer separate keys for personal and guest profiles.

---

## Channel Access Control

`allowFrom` is your primary chat access gate.

- Empty allowlist = open access to everyone on that channel.
- Telegram IDs should be numeric user IDs.
- WhatsApp numbers should be normalized (E.164 style recommended).
- If running guest bot, use separate bot token / separate WA account.

---

## Tool Safety

`g-agent` includes guardrails, but operator discipline is still required.

Built-in controls include:

- workspace boundary checks (when `restrictToWorkspace=true`)
- dangerous shell pattern blocking
- browser denylist for localhost/metadata hosts
- timeouts and output truncation
- per-tool policy (`allow` / `ask` / `deny`)

Recommended policy posture:

- keep risky tools (`exec`, send/message tools) on `ask`/`confirm`
- deny tools you never need in shared mode

---

## Multi-Profile Isolation

For shared usage, keep profiles separate:

- Personal: `~/.g-agent`
- Guest: `~/.g-agent-guest`

Use:

```bash
G_AGENT_DATA_DIR=~/.g-agent-guest g-agent status
```

Each profile should have isolated:

- config and secrets
- memory/workspace
- cron jobs
- bridge/media/auth artifacts
- integrations (Google, SMTP, Slack)

---

## Google Workspace Security

If Google integration is enabled:

- use OAuth client dedicated to this app
- keep refresh token private
- keep guest profile Google integration disabled unless required
- revoke tokens from Google Account Security if compromise suspected

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

Keep both Python and Node dependencies updated regularly.

---

## Incident Response

If compromise is suspected:

1. Revoke API keys/tokens immediately.
2. Stop services:
   ```bash
   systemctl --user stop g-agent-gateway.service g-agent-wa-bridge.service
   ```
3. Inspect recent logs:
   ```bash
   journalctl --user -u g-agent-gateway.service -u g-agent-wa-bridge.service --since "2 hours ago" --no-pager
   ```
4. Rotate credentials and re-auth integrations.
5. Re-enable services after verification.

---

## Known Limitations

Current tradeoffs to keep the project lightweight:

- no built-in user rate limiting
- config secrets are plaintext on disk
- security logging is operational, not full SIEM-grade audit trail
- tool safety is guardrail-based, not sandbox virtualization

Use external controls (firewall, dedicated OS user, profile isolation) for stronger defense.

---

## Security Checklist

Before production-like use:

- [ ] `restrictToWorkspace=true`
- [ ] `approvalMode=confirm`
- [ ] `allowFrom` set for enabled channels
- [ ] running as non-root user
- [ ] config and auth directories have strict permissions
- [ ] dependencies audited and updated
- [ ] personal and guest profiles separated if sharing bot access

---

## References

- Security advisories: `https://github.com/galyarder/galyarder-agent/security/advisories`
- Releases: `https://github.com/galyarder/galyarder-agent/releases`
