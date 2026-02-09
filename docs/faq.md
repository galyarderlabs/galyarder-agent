# FAQ

## Why docs-first instead of a landing site?

This repo is now optimized for open-source operators and contributors.  
Docs-first keeps maintenance lower and onboarding clearer.

## Is Vercel required?

No. Documentation is served through GitHub Pages.

## Can I still run this privately for personal use?

Yes. The runtime remains local-first with profile and policy controls.

## Does this support Telegram and WhatsApp together?

Yes. Configure both channels and strict per-channel `allowFrom` lists.

## Can I isolate guest users from personal data?

Yes. Use separate profiles (`G_AGENT_DATA_DIR`) and limited policy presets.

## Why keep local pre-push guard if branch protection exists?

It catches failures before remote push and shortens debug loops.

## Where should I start contributing?

Read:

1. [Contributing](contributing.md)
2. [Security](security.md)
3. [OpenClaw Delta Roadmap](roadmap/openclaw-delta.md)
