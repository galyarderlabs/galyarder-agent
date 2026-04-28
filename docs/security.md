# Security

## Security model

Galyarder Agent is secured by layered controls:

- identity gates (`allowFrom`)
- tool boundaries (`restrictToWorkspace`, policy presets)
- approval flow for risky actions
- profile separation (`G_AGENT_DATA_DIR`) for personal vs guest characters

## Minimum hardening baseline

1. Use strict channel allowlists
2. Keep workspace restriction enabled
3. Separate guest profile from personal profile
4. Scope API/OAuth permissions to least privilege
5. Monitor runtime logs and rotate secrets on suspicion
6. Set `channels.whatsapp.bridgeToken` when running WhatsApp bridge in production; if left empty, any localhost client can connect to the bridge.

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
