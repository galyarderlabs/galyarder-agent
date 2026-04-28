# Roadmap Implementation Plans

These files break the main `ROADMAP.md` into execution plans.

The main roadmap stays as the product thesis and reference audit. These plans
turn each phase into a buildable milestone with scope, module targets, tests,
and acceptance criteria.

## Milestones

- [Roadmap Completion TODO](TODO.md) — master task board until all phases are shipped
- [Codebase Deep-Dive Audit](00-codebase-deep-dive-audit.md)
- [v0.1: Stabilize Current Runtime](v0.1-stabilize-current-runtime.md)
- [v0.2: Session Store And Recall](v0.2-session-store-and-recall.md) — first slice shipped
- [v0.3: Commands, Logs, And Approvals](v0.3-commands-logs-approvals.md) — core shipped
- [v0.4: Core Channel Reliability](v0.4-core-channel-reliability.md) — partial, not shipped
- [v0.5: Web UI And OpenAI-Compatible API](v0.5-web-ui-openai-api.md) — not shipped
- [v0.6: Character Profiles And Visual Identity](v0.6-character-profiles-visual-identity.md) — core shipped
- [v0.7: Memory Manager And Owner Model](v0.7-memory-manager-owner-model.md) — partial
- [v0.8: Owner-Reviewed Learning Loop](v0.8-owner-reviewed-learning-loop.md) — partial
- [v0.9: Skills As Procedural Memory](v0.9-skills-procedural-memory.md) — partial
- [v0.10: Context Engine And Compression](v0.10-context-engine-compression.md) — partial
- [v0.11: Routines, Cron, And Triggers](v0.11-routines-cron-triggers.md) — partial
- [v0.12: Toolsets, MCP, And Execution Backends](v0.12-toolsets-mcp-execution.md) — partial
- [v0.13: Insights, Packaging, And Public Trust](v0.13-insights-packaging-public-trust.md) — completed slice

## Execution Rule

Build in order unless a production issue forces a hotfix. Session store,
commands, approvals, and channel reliability are the foundation. Learning,
skills, routines, and Web UI should sit on top of that foundation rather than
invent separate state.

Before implementing a milestone, read the deep-dive audit and the specific
version plan. The audit explains what already exists in G-Agent and which
Hermes/Nanobot files are useful references.
