# Troubleshooting

Use this matrix for common runtime and ops failures.

## Troubleshooting matrix

| Symptom | Likely cause | Verify | Fix |
| --- | --- | --- | --- |
| Telegram bot connected but no response | sender ID not in `allowFrom` | `g-agent status` and gateway logs | add numeric Telegram ID to `channels.telegram.allowFrom` |
| WhatsApp access denied | WA sender ID mismatch | gateway warning shows rejected sender | add exact sender ID to `channels.whatsapp.allowFrom` |
| WhatsApp bridge reconnect loop | stale session or unstable bridge runtime | `journalctl --user -u g-agent-wa-bridge.service` | re-login via `g-agent channels login`, restart bridge |
| LLM auth error | wrong provider key/base/model route | `g-agent status`, provider section in config | correct `providers.*` fields and restart gateway |
| Google tool unavailable | OAuth missing/expired | `g-agent status` Google OAuth parts | refresh OAuth token flow in CLI |
| Cron jobs not firing | jobs disabled/misconfigured timezone | startup logs + cron service lines | verify proactive config and schedule definitions |

## Core diagnostics

```bash
g-agent status
g-agent doctor --network
journalctl --user -u g-agent-gateway.service -u g-agent-wa-bridge.service -n 200 --no-pager
```

## Safe recovery sequence

```bash
systemctl --user daemon-reload
systemctl --user restart g-agent-wa-bridge.service g-agent-gateway.service
g-agent status
```

## Escalation checklist

When filing an issue, include:

- commit hash
- config section involved (redact secrets)
- exact command used
- relevant log excerpt (timestamp + error line)
