# Channels

## Supported

- CLI
- Telegram
- WhatsApp
- Email
- Slack (Socket Mode)

Discord/Feishu paths exist in runtime code and can be hardened as needed.

## Telegram

1. Create bot token with BotFather
2. Add your numeric Telegram user ID to `channels.telegram.allowFrom`
3. Restart gateway and verify in logs

## WhatsApp

1. Run `g-agent channels login`
2. Scan QR in the bridge output
3. Ensure your WA sender ID is in `channels.whatsapp.allowFrom`
4. Keep bridge + gateway active (systemd user services recommended)

## Email

Bidirectional email channel using IMAP polling and SMTP replies.

### Requirements

- IMAP-enabled mailbox (Gmail, Outlook, self-hosted)
- App password or OAuth credentials for SMTP relay
- Explicit consent: set `consent_granted: true` in config

### Configuration

```json
{
  "channels": {
    "email": {
      "enabled": true,
      "consent_granted": true,
      "imap_host": "imap.gmail.com",
      "smtp_host": "smtp.gmail.com",
      "imap_username": "you@gmail.com",
      "imap_password": "your-app-password",
      "smtp_username": "you@gmail.com",
      "smtp_password": "your-app-password",
      "from_address": "you@gmail.com",
      "allow_from": ["trusted@example.com"],
      "poll_interval_seconds": 30
    }
  }
}
```

### Security notes

- The channel **will not start** unless `consent_granted` is explicitly `true`.
- Use `allow_from` to restrict which senders the agent responds to.
- Replies are threaded with subject prefix `G-Agent reply:`.

## Slack (Socket Mode)

Real-time bidirectional Slack channel using Socket Mode (no public URL required).

### Slack requirements

- Slack app with Socket Mode enabled
- Bot token (`xoxb-...`) with `chat:write`, `app_mentions:read` scopes
- App-level token (`xapp-...`) with `connections:write` scope

### Slack configuration

```json
{
  "channels": {
    "slack_channel": {
      "enabled": true,
      "bot_token": "xoxb-your-bot-token",
      "app_token": "xapp-your-app-token",
      "group_policy": "mention",
      "dm": {
        "enabled": true,
        "policy": "open"
      }
    }
  }
}
```

### Policies

| Setting | Options | Description |
| --- | --- | --- |
| `group_policy` | `mention` / `open` | Respond to @mentions only, or all messages in channels |
| `dm.policy` | `open` / `allowlist` / `disabled` | Control DM access |
| `dm.allow_from` | list of Slack user IDs | Restrict DMs when policy is `allowlist` |

## Channel troubleshooting

Use:

```bash
journalctl --user -u g-agent-gateway.service -u g-agent-wa-bridge.service -n 120 --no-pager
```
