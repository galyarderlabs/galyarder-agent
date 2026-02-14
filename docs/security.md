# Security

## Security model

Galyarder Agent is secured by layered controls:

- identity gates (`allowFrom`)
- tool boundaries (`restrictToWorkspace`, policy presets)
- approval flow for risky actions
- profile separation (`G_AGENT_DATA_DIR`) for personal vs guest assistants

## Minimum hardening baseline

1. Use strict channel allowlists
2. Keep workspace restriction enabled
3. Separate guest profile from personal profile
4. Scope API/OAuth permissions to least privilege
5. Monitor runtime logs and rotate secrets on suspicion
6. Set `channels.whatsapp.bridgeToken` when running WhatsApp bridge in production

## Vulnerability reporting

Use private GitHub advisories:

- https://github.com/galyarderlabs/galyarder-agent/security/advisories

Also review:

- Root policy: `SECURITY.md`
- Runtime details: `backend/agent/SECURITY.md`
