# Channels

## Supported

- CLI
- Telegram
- WhatsApp

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

## Channel troubleshooting

Use:

```bash
journalctl --user -u g-agent-gateway.service -u g-agent-wa-bridge.service -n 120 --no-pager
```
