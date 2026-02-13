# Communication & Support — Galyarder Agent (`g-agent`)

Use this guide for support, bug reports, and security communication.

---

## General Support

For normal questions, setup help, and usage guidance:

- Open a GitHub issue in this repository.
- Include your environment summary and what you already tried.

Helpful diagnostics to attach:

```bash
g-agent --version
g-agent status
g-agent doctor --network
```

If you run via systemd:

```bash
journalctl --user -u g-agent-gateway.service -u g-agent-wa-bridge.service -n 200 --no-pager
```

---

## Bug Report Template (Recommended)

When reporting bugs, include:

1. **Goal**: what you expected to happen
2. **Actual**: what happened instead
3. **Steps**: minimal reproducible steps
4. **Config context**: relevant channel/provider fields (mask secrets)
5. **Logs**: relevant snippets from `journalctl` or CLI output

Mask sensitive values before sharing:

- bot tokens
- API keys
- OAuth refresh tokens
- private identifiers you do not want public

---

## Security Reports (Private)

For vulnerabilities, follow private disclosure:

- Use GitHub Security Advisory (private), not public issues.
- See `SECURITY.md` for response expectations and details.

## Maintainer Notes

When asking for help on multi-profile setups, specify profile explicitly:

- personal: `~/.g-agent`
- guest: `~/.g-agent-guest`

And run commands with the correct profile:

```bash
G_AGENT_DATA_DIR=~/.g-agent-guest g-agent status
```
