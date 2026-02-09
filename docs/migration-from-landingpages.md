# Migration Guide (Landingpages → Docs-first)

This repository moved from a marketing landing app to a docs-first open-source layout.

## What changed

- Removed `landingpages/` Next.js + waitlist stack
- Replaced with static docs in `docs/` powered by MkDocs
- Added GitHub Pages deploy workflow
- Re-targeted CI/release/security checks from landing app to docs checks

## Why this change

- Lower maintenance surface
- Better fit for open-source users
- Faster onboarding through docs instead of marketing funnel
- No Vercel dependency for public project documentation

## Current structure

- `backend/agent` → runtime + CLI + integrations
- `docs` → documentation source
- `.github/workflows/docs-pages.yml` → docs deploy pipeline

## Operational impact

- GitHub Pages now serves documentation
- Required status check is `Docs Checks` (not `Landingpages Checks`)
- Dependabot monitors docs Python dependencies via `docs/requirements.txt`

## If you were using old landingpages paths

- Landing waitlist endpoints are no longer available
- Replace landing links with docs links:
  - docs site: `https://galyarderlabs.github.io/galyarder-agent/`
  - repo docs source: `docs/`
