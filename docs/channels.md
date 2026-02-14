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

### Configuration

```json
{
  "channels": {
    "whatsapp": {
      "enabled": true,
      "bridgeUrl": "ws://localhost:3001",
      "allowFrom": ["628xxxxxxxxxx"],
      "bridgeToken": "your-shared-secret"
    }
  }
}
```

### Bridge authentication

Set `bridgeToken` to add a shared-secret auth gate on the WebSocket bridge. The Python client sends an auth message immediately after connecting; the Node.js bridge verifies it within 5 seconds or closes the connection.

- If `bridgeToken` is empty (default), the bridge accepts all connections (backward compatible).
- The token is also passed as `BRIDGE_TOKEN` env var when launching the bridge via `g-agent channels login`.

### Voice notes

- Incoming voice/audio transcription uses Groq Whisper (`providers.groq.apiKey` or `GROQ_API_KEY`).
- Generated `media_type: "voice"` replies require `espeak-ng`/`espeak` + `ffmpeg` for OGG/Opus voice-note format.
- If `ffmpeg` is unavailable, g-agent auto-falls back to regular `audio` output.

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
