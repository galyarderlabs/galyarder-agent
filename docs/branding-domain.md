# Branding & Domain

This docs site ships with brand assets and optional custom-domain support.

## Branding assets

- Logo mark: `docs/assets/logo-mark.svg`
- Wordmark: `docs/assets/logo-wordmark.svg`
- Theme override: `docs/styles/extra.css`

## Optional custom domain (CNAME)

The deploy workflow supports custom domain injection without hardcoding.

Set repository variable:

- `G_AGENT_PAGES_CNAME` = your domain (example: `docs.galyarderlabs.app`)

The workflow writes `site/CNAME` during deploy when this variable is present.

## DNS requirements

For `docs.yourdomain.com`:

1. Create `CNAME` record:
   - host: `docs`
   - target: `galyarderlabs.github.io`
2. Wait DNS propagation.
3. Re-run `Docs Pages` workflow once.

## Verify

```bash
gh run list --workflow "Docs Pages" --limit 3
gh api repos/galyarderlabs/galyarder-agent/pages
```
