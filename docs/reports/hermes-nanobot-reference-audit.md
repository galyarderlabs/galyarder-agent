# Hermes And Nanobot Reference Audit

This report maps the valuable ideas from `hermes-agent-ref/` and `nanobot-ref/` into G-Agent decisions. It is not a file-by-file inventory. It is a feature-by-feature audit with source evidence, fit, and implementation direction.

G-Agent's target is an agentic character runtime: persistent identity, relationship memory, visual presence, owner workflows, and daily-use channels. References are useful only when they support that direction.

## Decision Legend

| Decision | Meaning |
| --- | --- |
| Adopt | Bring the capability into G-Agent with similar architecture. |
| Adapt | Borrow the pattern, but reshape it for G-Agent's character-first product. |
| Later | Valuable, but not needed until the core runtime is stable. |
| Drop | Not worth carrying into G-Agent core. |

## Executive Summary

Hermes should influence G-Agent's internal learning loop. Nanobot should influence G-Agent's app surfaces and operational reliability.

The highest-value items from the reference repos are:

1. SQLite session store with FTS search.
2. Session search and summarization tool.
3. Shared slash command router with logs, status, approvals, memory, and skills commands.
4. Dangerous action approval system per session/channel.
5. Built-in memory manager with context fencing and one optional external provider.
6. Owner-reviewed learning queue.
7. Skill lifecycle as procedural memory.
8. WebSocket/Web UI and OpenAI-compatible API.
9. WhatsApp, Telegram, and Discord media/session hardening.
10. Routine engine for cron and webhook-triggered workflows.

## Current Adoption Snapshot

This snapshot is based on the current G-Agent codebase, not only on roadmap
intent.

| Status | Reference value | Current G-Agent evidence | Remaining gap |
| --- | --- | --- | --- |
| Adopted first slice | SQLite sessions, FTS recall, command controls, approval commands, profile core, skill store, routines, toolsets, MCP stdio/SSE, shared runner, local execution, observability insights, skill candidate apply/rollback. | `session/sqlite_store.py`, `agent/tools/session_search.py`, `command/`, `character/`, `skills/`, `learning/`, `routines/`, `agent/tools/toolsets.py`, `mcp/manager.py`, `agent/runner.py`, `agent/environments.py`, `observability/insights.py`. | Backfill/import polish, persisted approvals, profile switching isolation, atomic skill patching, and streamable HTTP MCP remain. |
| Partial | Channel reliability, multimodal handling, learning queue, context compression, and routine execution. | `channels/manager.py`, channel tests, `learning/`, `context/engine.py`, `context/compressor.py`, `routines/scheduler.py`. | Shared media envelope/capability flags, background reviewer, non-skill learning apply flows, automatic compression integration, webhook/API routine triggers, and multi-skill routines are still open. |
| Not shipped | First-party Web UI, WebSocket channel, OpenAI-compatible product API, formal MemoryManager, Docker execution backend, background reviewer, prompt-injection scanner, third-party notices. | No `g_agent/api/`, no `channels/websocket.py`, no `webui/`, no `g_agent/memory/manager.py`, no Docker execution backend. | These remain future implementation work, not completed roadmap claims. |

## G-Agent Baseline

Current G-Agent already has useful foundations:

| Area | Current source | Current state | Gap |
| --- | --- | --- | --- |
| Memory | `backend/agent/g_agent/agent/memory.py` | Markdown memory files, profile, relationships, projects, FACTS index, recall and consolidation helpers. | Needs formal `MemoryManager`, context fencing, provider boundary, and owner-reviewed write lifecycle. |
| Skills | `backend/agent/g_agent/agent/skills.py`, `backend/agent/g_agent/skills/`, `backend/agent/g_agent/agent/tools/skills.py`, `backend/agent/g_agent/command/builtin.py` | Built-in/workspace `SKILL.md` loader plus skill store/validator/manager/draft tooling, `skill_manage`, and owner-reviewed `/learn apply`/`rollback` for skill candidates. | Needs atomic patching, full lifecycle command polish, and background skill proposal review. |
| Sessions | `backend/agent/g_agent/session/manager.py`, `backend/agent/g_agent/session/sqlite_store.py` | JSONL sessions remain readable, with a SQLite dual-write store, WAL, FTS5 search, media refs, and tool-call metadata. | Needs explicit JSONL backfill/import and richer context windows around search hits. |
| Commands | `backend/agent/g_agent/channels/slash_commands.py`, `backend/agent/g_agent/command/` | Native slash commands now include shared parsing for direct CLI/chat, `/history`, `/sessions`, `/logs`, `/approve`, and `/deny`. | Needs first-class persisted approval state, narrow allowlists, skills commands, learning review, and broader handler extraction. |
| Channels | `backend/agent/g_agent/channels/` | WhatsApp, Telegram, Discord, Slack, email, manager; supervisor/retry and multimodal tests exist. | Needs shared capability flags, normalized media envelope, long-message splitting contract, normalized delivery errors, and broader diagnostics. |
| Cron/proactive | `backend/agent/g_agent/cron/`, `backend/agent/g_agent/proactive/`, `backend/agent/g_agent/routines/` | Cron service plus routine model/store/runner/scheduler and `/routines` command surface. | Needs script preprocessing, multi-skill routines, webhook/API triggers, and tighter destination/tool policy. |

## Audit Matrix

### Session Store And Conversation Recall

| Capability | Source | Evidence files | Decision | Fit for G-Agent | Implementation notes |
| --- | --- | --- | --- | --- | --- |
| SQLite session database | Hermes | `hermes-agent-ref/hermes_state.py` | Adopted first slice | This is the substrate for long-term character continuity. JSONL is readable but weak for search, concurrency, and analytics. | `SessionSQLiteStore` now provides sessions/messages tables, WAL, FTS5, source/channel metadata, token/tool counters, and media refs. Keep JSONL compatibility; add explicit historical backfill later. |
| Full-text session search | Hermes | `hermes-agent-ref/hermes_state.py`, `hermes-agent-ref/tools/session_search_tool.py` | Adopted first slice | The character must recall old conversations, decisions, commands, and owner preferences. | `session_search` and `/history` now search SQLite-backed sessions while `/search` remains web search. Rich summaries/context windows remain follow-up work. |
| Session title/lineage | Hermes | `hermes-agent-ref/hermes_state.py`, `hermes-agent-ref/agent/title_generator.py` | Adapt | Useful for Web UI and owner review. Parent chains matter after compression. | Add automatic titles later, but start with channel/source/date and optional title. |
| Cost/token/session insights | Hermes | `hermes-agent-ref/hermes_state.py`, `hermes-agent-ref/agent/insights.py` | Adopted first slice | Useful for owner trust and debugging. | `observability/insights.py`, `/insights`, and `tests/test_insights.py` cover session/model/platform/tool overview, provider buckets, skill usage, malformed metrics lines, and recent failed calls. |
| JSONL-only session persistence | Current G-Agent | `backend/agent/g_agent/session/manager.py` | Replace gradually | Good for simplicity, insufficient for G-Agent's memory ambitions. | Keep export/import compatibility while moving primary store to SQLite. |

### Memory And User Modeling

| Capability | Source | Evidence files | Decision | Fit for G-Agent | Implementation notes |
| --- | --- | --- | --- | --- | --- |
| Memory manager as single integration point | Hermes | `hermes-agent-ref/agent/memory_manager.py` | Adopt, not shipped | Prevents scattered memory logic and provider conflicts. | Current code still uses `MemoryStore` directly from tools/context. Add manager around it; built-in provider always enabled; allow one optional external provider. |
| Context fencing for recalled memory | Hermes | `hermes-agent-ref/agent/memory_manager.py` | Adopt | Critical so recalled facts are not treated as new user instructions. | Use fenced `<memory-context>` or G-Agent equivalent. Strip leaked fences from provider outputs. |
| Built-in local fact memory | Current G-Agent + Hermes holographic | `backend/agent/g_agent/agent/memory.py`, `hermes-agent-ref/plugins/memory/holographic/README.md` | Adapted first slice | Best first default: local/private, no external service dependency. | Markdown-facing files and FACTS indexing exist. Formal provider interface, confidence/source/contradiction metadata, and manager-level lifecycle remain. |
| Honcho-style user/AI peer model | Hermes | `hermes-agent-ref/plugins/memory/honcho/README.md` | Later | Very aligned with agentic character depth, but external and complex. | Defer until local memory works. Borrow concepts: owner model, AI self model, relationship card, session summaries. |
| Multiple external memory plugins | Hermes | `hermes-agent-ref/plugins/memory/` | Drop from core | Too much provider sprawl for early G-Agent. | Support plugin interface later, but core should ship one local provider plus one optional external. |
| Markdown memory files | Current G-Agent | `backend/agent/g_agent/agent/memory.py` | Keep | Owner-readable memory is valuable for trust. | Make markdown a human view/export, not the only query engine. |

### Learning Loop

| Capability | Source | Evidence files | Decision | Fit for G-Agent | Implementation notes |
| --- | --- | --- | --- | --- | --- |
| Background memory/skill review | Hermes | `hermes-agent-ref/run_agent.py` | Adapt | This is the heart of "the character grows with use." | Run review after response delivery. Do not block user response. Generate candidates for review, not automatic writes at first. |
| Nudge intervals | Hermes | `hermes-agent-ref/run_agent.py` | Adapt | Prevents constant self-reflection spam. | Configurable intervals for memory review, skill review, and routine review. |
| Learning queue | G-Agent target | `ROADMAP.md`, `backend/agent/g_agent/learning/` | Adopted partial | Owner needs review/edit/rollback before character changes. | `LearningCandidate` and `LearningQueue` persist lifecycle fields. `/learn` supports list/info/approve/reject/edit and skill apply/rollback. Background reviewer and non-skill apply flows remain. |
| Auto-apply memory/skills | Hermes pattern | `hermes-agent-ref/run_agent.py`, `hermes-agent-ref/tools/skill_manager_tool.py` | Later | Too risky until review UX and tests exist. | Start manual approval only; maybe low-risk facts auto-apply later. |
| Research/RL learning | Hermes | `hermes-agent-ref/environments/`, `hermes-agent-ref/batch_runner.py`, `hermes-agent-ref/agent/trajectory.py` | Drop from core | Not aligned with first G-Agent product. | Keep as distant research inspiration only. |

### Skills As Procedural Memory

| Capability | Source | Evidence files | Decision | Fit for G-Agent | Implementation notes |
| --- | --- | --- | --- | --- | --- |
| Progressive skill loading | Current G-Agent + Hermes + Nanobot | `backend/agent/g_agent/agent/skills.py`, `hermes-agent-ref/tools/skills_tool.py`, `nanobot-ref/nanobot/agent/skills.py` | Adopt | Keeps prompts small while letting the character use specialized procedures. | Keep summary-first loading; add `skill_view`/`skills_list` tools if missing. |
| Skill create/patch/delete lifecycle | Hermes | `hermes-agent-ref/tools/skill_manager_tool.py` | Adapted partial | Required for procedural memory and self-improvement. | `skills/store.py`, `skills/validator.py`, `skills/manager.py`, drafts, `skill_manage`, and owner-reviewed skill candidate activation/rollback exist. Atomic patching and background skill proposal review remain. |
| Supporting files in skills | Hermes | `hermes-agent-ref/tools/skill_manager_tool.py` | Adopted first slice | Useful for templates, scripts, assets, and references. | Current skill package handling supports local skill directories and validation. More explicit policy for `references/`, `templates/`, `scripts/`, `assets/` and traversal tests should remain in the lifecycle work. |
| Skill command invocation | Hermes | `hermes-agent-ref/agent/skill_commands.py`, `hermes-agent-ref/agent/skill_preprocessing.py` | Later | Good UX, but lifecycle should land first. | Add `/skills`, `/skill <name>`, and optional template substitution after review system exists. |
| Skill hub/public marketplace | Hermes/Nanobot | `hermes-agent-ref/hermes_cli/skills_hub.py`, `nanobot-ref/nanobot/skills/` | Later | Useful eventually, risky before local skills mature. | Keep local/private skill development first. |
| Community skill packs | Nanobot | `nanobot-ref/nanobot/skills/` | Drop from core | Some examples are fine, but not product-defining. | Do not import wholesale. |

### Commands, Approvals, And Owner Control

| Capability | Source | Evidence files | Decision | Fit for G-Agent | Implementation notes |
| --- | --- | --- | --- | --- | --- |
| Native slash command router | Current G-Agent + Nanobot + Hermes | `backend/agent/g_agent/channels/slash_commands.py`, `nanobot-ref/nanobot/command/router.py`, `hermes-agent-ref/hermes_cli/commands.py` | Adopted first slice | Owner needs deterministic controls without LLM ambiguity. | `g_agent/command` now provides shared command context/router and quoted-argument parsing. Continue moving legacy handlers out of `channels/slash_commands.py`. |
| Dangerous command approval | Hermes | `hermes-agent-ref/tools/approval.py` | Adopted first slice | Directly addresses user concern about exec approvals and unsafe local actions. | `/approve` now passes through to live replay and `/deny` clears pending session approvals. Add persisted approval state and narrow allowlists next. |
| Logs/status commands | Current G-Agent + Hermes | `backend/agent/g_agent/channels/slash_commands.py`, `hermes-agent-ref/hermes_cli/logs.py`, `hermes-agent-ref/gateway/status.py` | Adopted first slice | Debugging via chat is essential for owner runtime. | `/logs` now reads bounded task checkpoints with obvious secret redaction. Richer status remains follow-up. |
| Permission policy UI | Hermes | `hermes-agent-ref/tools/approval.py` | Adapt | Useful but must be simpler than Hermes initially. | Chat first, Web UI later. |
| Natural-language operational commands only | Existing behavior risk | N/A | Drop | Too ambiguous for safety-critical actions. | Keep deterministic slash commands. |

### Web UI, WebSocket, And API

| Capability | Source | Evidence files | Decision | Fit for G-Agent | Implementation notes |
| --- | --- | --- | --- | --- | --- |
| WebSocket channel | Nanobot | `nanobot-ref/nanobot/channels/websocket.py`, `nanobot-ref/docs/websocket.md` | Adopt, not shipped | Foundation for first-party Web UI and real-time control. | No `channels/websocket.py` exists yet. Add token auth, session mapping, media envelopes, streaming deltas, lifecycle events. |
| Web UI | Nanobot | `nanobot-ref/webui/`, `nanobot-ref/images/nanobot_webui.png` | Adapt, not shipped | Needed, but G-Agent UI should control character/memory/skills/routines, not just chat. | No first-party `webui/` exists yet. Build after backend state and commands are stable. |
| OpenAI-compatible chat completions | Nanobot + Hermes | `nanobot-ref/nanobot/api/server.py`, `nanobot-ref/docs/openai-api.md`, `hermes-agent-ref/gateway/platforms/api_server.py` | Adopt, not shipped | Lets Open WebUI, LobeChat, LibreChat, and local tools use G-Agent. | `GatewayConfig` exists, but no first-party `g_agent/api/` product server exists yet. Start with `/v1/models` and `/v1/chat/completions`; add `/v1/responses` later. |
| Stateful responses API | Hermes | `hermes-agent-ref/gateway/platforms/api_server.py` | Later | Good compatibility, but more complex than initial chat completions. | Defer until session store and chat completions are stable. |
| API multimodal normalization | Nanobot + Hermes | `nanobot-ref/nanobot/api/server.py`, `hermes-agent-ref/gateway/platforms/api_server.py` | Adopt | Important for image input and visual workflows. | Support base64 data URLs, uploads, size limits, and explicit remote URL policy. |

### Channels And Gateway

| Capability | Source | Evidence files | Decision | Fit for G-Agent | Implementation notes |
| --- | --- | --- | --- | --- | --- |
| WhatsApp reliability patterns | Nanobot + Hermes | `nanobot-ref/bridge/src/whatsapp.ts`, `nanobot-ref/nanobot/channels/whatsapp.py`, `hermes-agent-ref/gateway/platforms/whatsapp.py` | Adopted partial | WhatsApp is one of G-Agent's primary surfaces. | Bridge auth, login, reconnect, and multimodal basics have coverage. Shared media envelope, clearer delivery errors, and richer diagnostics remain. |
| Telegram channel hardening | Nanobot + Hermes | `nanobot-ref/nanobot/channels/telegram.py`, `hermes-agent-ref/gateway/platforms/telegram.py` | Adopted partial | Primary channel. | Reconnect and basic outbound tests exist. Markdown safety, richer media policy, group/topic mapping, and rate handling remain. |
| Discord channel hardening | Nanobot + Hermes | `nanobot-ref/nanobot/channels/discord.py`, `hermes-agent-ref/gateway/platforms/discord.py` | Adopted partial | Primary channel. | Channel exists with tests around ported channel config and multimodal basics. Attachments, DM/mention policy, persistent mapping, and reconnect polish remain. |
| Gateway platform abstraction | Hermes | `hermes-agent-ref/gateway/platforms/base.py`, `hermes-agent-ref/gateway/run.py`, `hermes-agent-ref/gateway/session.py` | Adapt | Useful if G-Agent channel manager gets too coupled. | Borrow patterns selectively; avoid full gateway rewrite too early. |
| Regional enterprise chat adapters | Nanobot + Hermes | Regional chat adapter implementations in both reference repos | Drop from core | Not aligned with G-Agent's current use case. | Keep out of core. Maybe plugin examples later. |
| Slack/Matrix/Microsoft Teams | Nanobot + Hermes | `nanobot-ref/nanobot/channels/slack.py`, `nanobot-ref/nanobot/channels/matrix.py`, `nanobot-ref/nanobot/channels/msteams.py`, `hermes-agent-ref/gateway/platforms/slack.py`, `hermes-agent-ref/gateway/platforms/matrix.py` | Slack adopted basic slice; Matrix/Teams later | Useful for broader users, not first focus. | `channels/slack.py` and Slack config tests exist. Matrix and Microsoft Teams remain optional future channel packs. |

### MCP, Tools, And Toolsets

| Capability | Source | Evidence files | Decision | Fit for G-Agent | Implementation notes |
| --- | --- | --- | --- | --- | --- |
| MCP schema normalization and retry | Nanobot | `nanobot-ref/nanobot/agent/tools/mcp.py`, `nanobot-ref/tests/agent/test_mcp_connection.py`, `nanobot-ref/tests/agent/test_mcp_transient_retry.py` | Adopted first slice | G-Agent already wants app/tool integrations; MCP must be boring and safe. | `mcp/manager.py` supports stdio/SSE connection, schema normalization, timeout, transient retry, and clearer errors. Streamable HTTP MCP remains. |
| Toolsets/capability groups | Hermes | `hermes-agent-ref/toolsets.py` | Adopted first slice | Prevents every character/session from getting every tool. | `agent/tools/toolsets.py` defines safe/file/terminal/web/search/vision/image/messaging/memory/skills/routines/MCP/subagent groupings and dynamic MCP groups. Per-profile policy remains. |
| File/shell tool UX | Nanobot + Hermes | `nanobot-ref/nanobot/agent/tools/filesystem.py`, `nanobot-ref/nanobot/agent/tools/shell.py`, `hermes-agent-ref/tools/terminal_tool.py` | Adapted first slice | Useful, but must respect G-Agent sandbox and allowed paths. | File/shell tools, local environment, roots, and approval hooks exist. More path UX, file-state reporting, and durable approval persistence remain. |
| Notebook/scratch tools | Nanobot | `nanobot-ref/nanobot/agent/tools/notebook.py` | Later | Nice for complex tasks, not first priority. | Consider after session store/skills. |
| Tool hints and progress events | Nanobot | `nanobot-ref/nanobot/utils/tool_hints.py`, `nanobot-ref/nanobot/utils/progress_events.py` | Adapt | Useful for chat UX and Web UI. | Add progress/lifecycle events to WebSocket/API first. |

### Agent Runner, Subagents, And Execution

| Capability | Source | Evidence files | Decision | Fit for G-Agent | Implementation notes |
| --- | --- | --- | --- | --- | --- |
| Shared agent runner | Nanobot | `nanobot-ref/nanobot/agent/runner.py` | Adopted first slice | Separates tool loop from product/session/channel concerns. | `agent/runner.py` exists and is used by subagent execution. API/channel unification can build on it later. |
| Subagent lifecycle | Nanobot + Hermes | `nanobot-ref/nanobot/agent/subagent.py`, `nanobot-ref/nanobot/agent/tools/spawn.py`, `hermes-agent-ref/tools/delegate_tool.py`, `hermes-agent-ref/tests/tools/test_delegate.py` | Adapted first slice | Useful for background work and research, but owner needs status and summaries. | Subagent spawn/run/cancel paths exist. Richer status events, artifacts, and completion summaries remain. |
| Local execution default | Current G-Agent | `backend/agent/g_agent/` | Keep, implemented | Best for user's setup and privacy. | `agent/environments.py` includes local execution. Improve durable approvals and path policy next. |
| Docker/SSH/remote backends | Hermes | `hermes-agent-ref/tools/environments/` | Later | Useful for always-on or risky work, not first core. | Start with local; add Docker sandbox next; SSH/VPS later. |
| Modal/Daytona/Singularity | Hermes | `hermes-agent-ref/tools/environments/` | Later/drop from core | Interesting but too heavy for early G-Agent. | Keep as optional backend only if demand appears. |

### Context Compression And Prompt Assembly

| Capability | Source | Evidence files | Decision | Fit for G-Agent | Implementation notes |
| --- | --- | --- | --- | --- | --- |
| Pluggable context engine | Hermes | `hermes-agent-ref/agent/context_engine.py` | Adopted first slice | Character context will become complex: profile, memory, sessions, skills, routines. | `context/engine.py` exists with a default engine. Deeper integration and policy coverage remain. |
| Structured compression | Hermes + Nanobot | `hermes-agent-ref/agent/context_compressor.py`, `nanobot-ref/nanobot/agent/autocompact.py` | Adapted first slice | Needed for long-lived characters. | `context/compressor.py` exists. Automatic trigger, `/compact` replacement, and strict instruction-vs-reference handling remain. |
| Dream/consolidation loop | Nanobot | `nanobot-ref/nanobot/templates/agent/dream_phase1.md`, `nanobot-ref/nanobot/templates/agent/dream_phase2.md`, `nanobot-ref/nanobot/agent/autocompact.py` | Adapt | Very aligned with character development. | Merge with owner-reviewed learning queue instead of autonomous hidden mutation. |
| Prompt injection checks for context files | Hermes | `hermes-agent-ref/agent/prompt_builder.py` | Adopt | AGENTS/SOUL/profile/memory files are untrusted inputs in practice. | Add scans for hidden chars and injection patterns. |

### Routines, Cron, And Triggers

| Capability | Source | Evidence files | Decision | Fit for G-Agent | Implementation notes |
| --- | --- | --- | --- | --- | --- |
| Cron jobs | Current G-Agent + Nanobot + Hermes | `backend/agent/g_agent/cron/`, `backend/agent/g_agent/routines/`, `nanobot-ref/nanobot/agent/tools/cron.py`, `hermes-agent-ref/cron/scheduler.py` | Adopted first slice | Character should run reminders, reports, and check-ins. | Cron service plus routine model/store/runner/scheduler exist. Destination policy, allowed-tool policy, script preprocessing, webhook/API triggers, and multi-skill workflows remain. |
| Script pre-processing before agent | Hermes | `hermes-agent-ref/hermes-already-has-routines.md` | Adapt | Very useful for workflows: gather data first, then let character interpret. | Add routine step that runs approved script and injects stdout as context. |
| Webhook/API triggers | Hermes | `hermes-agent-ref/hermes-already-has-routines.md`, `hermes-agent-ref/gateway/platforms/webhook.py` | Later | Useful after API/session store exist. | Add after routine model and auth. |
| Multi-skill workflows | Hermes | `hermes-agent-ref/hermes-already-has-routines.md` | Later | Powerful but requires stable skills. | Defer until skill lifecycle works. |

### Image Generation And Visual Identity

| Capability | Source | Evidence files | Decision | Fit for G-Agent | Implementation notes |
| --- | --- | --- | --- | --- | --- |
| Image provider registry | Hermes | `hermes-agent-ref/agent/image_gen_provider.py`, `hermes-agent-ref/agent/image_gen_registry.py` | Adapt | G-Agent already has visual/selfie direction and proxy image need. | Keep provider config simple. Prioritize OpenAI-compatible proxy and local reference image roots. |
| Selfie/mirror character workflows | Current G-Agent product direction | `backend/agent/g_agent/agent/tools/selfie.py`, `ROADMAP.md` | Adopted first slice | This is a differentiator. | `SelfieTool` exists with channel delivery and tests. Profile-level visual config, reviewable visual changes, and better error logs remain. |
| Provider sprawl | Hermes/Nanobot | provider directories | Drop from core | Too much maintenance. | One clean OpenAI-compatible image path plus optional extras. |

### Docs, Packaging, And Tests

| Capability | Source | Evidence files | Decision | Fit for G-Agent | Implementation notes |
| --- | --- | --- | --- | --- | --- |
| Organized test matrix | Nanobot | `nanobot-ref/tests/agent/`, `nanobot-ref/tests/channels/`, `nanobot-ref/tests/tools/`, `nanobot-ref/tests/providers/` | Adapted partial | G-Agent needs confidence before learning loop changes memory/skills. | Tests are still flat under `backend/agent/tests/`, but coverage now spans sessions, commands, MCP, toolsets, channels, routines, skills, context, security, and insights. Reorganization can wait. |
| MkDocs user docs | Current G-Agent + Nanobot docs | `docs/`, `nanobot-ref/docs/` | Adapt | G-Agent docs should explain product surfaces, not upstream internals. | Add docs for allowed paths, image proxy, commands, memory, skills, routines, Web UI/API as they land. |
| Install matrix | Current G-Agent | `docs/install-matrix.md`, `deploy/` | Keep | Important for public trust. | Keep the public surface simple: Linux, macOS, Windows. |
| Third-party notices | Nanobot | `nanobot-ref/THIRD_PARTY_NOTICES.md` | Later | Only needed when borrowing assets/code/deps. | If code is copied, add notices. Prefer reimplementation from concepts. |

## Recommended Implementation Order

### Milestone 1: Inspectable Runtime

1. Completed first slice: SQLite session store behind current session manager.
2. Completed first slice: FTS search via `session_search` and `/history` while
   keeping `/search` as web search.
3. Completed first slice: `/logs` and `/sessions`; richer `/status` remains.
4. Completed first slice: `/approve` pass-through and `/deny`; persisted
   approval state and narrow allowlists remain.
5. Fix image proxy docs/config and remove dead Nebius assumptions.

Why first: the owner needs to see what happened, approve risky work, and retrieve old context before any self-improvement loop can be trusted.

### Milestone 2: Character Memory

1. Still open: wrap current `MemoryStore` in a formal Memory Manager.
2. Still open: add context-fenced recall blocks.
3. Partially done: local fact memory exists; manager-level fact lifecycle is still open.
4. Partially done: learning candidate storage exists; memory apply/reject/edit flow is still open.
5. Still open: `/memory review` command and rollback-safe non-skill owner workflow.

Why second: this turns memory from static files into a safe learning substrate.

### Milestone 3: Skills And Learning Queue

1. Completed first slice: learning candidate/queue model exists.
2. Still open: background review that proposes memory/profile/skill/routine candidates.
3. Partially done: skill store/validator/manager/drafts and `skill_manage` exist.
4. Partially done: `/learn` supports approve/reject/edit plus skill apply/rollback.
5. Still open: atomic skill patching, `/skills` polish, and background skill proposal review.

Why third: this is the Hermes-style growth loop, but constrained for G-Agent safety.

### Milestone 4: Channels And Web Surface

1. Partially done: WhatsApp media/login/reconnect/security tests exist; shared media envelope and diagnostics remain.
2. Partially done: Telegram/Discord channels and tests exist; richer media/session mapping remains.
3. Not shipped: WebSocket channel and events.
4. Not shipped: minimal OpenAI-compatible `/v1/models` and `/v1/chat/completions` product API.
5. Not shipped: first-party Web UI around sessions, approvals, memory, skills, and character profiles.

Why fourth: once the backend has real state and controls, Web UI becomes useful instead of decorative.

### Milestone 5: Routines And Advanced Runtime

1. Completed first slice: routine model/store/runner/scheduler and cron integration exist.
2. Still open: script preprocessing.
3. Still open: webhook/API triggers.
4. Completed first slice: toolsets and MCP stdio/SSE hardening exist; streamable HTTP MCP remains.
5. Still open: Docker sandbox, then SSH/VPS backend if needed.

Why fifth: routines are powerful only after approvals, memory, sessions, and tools are reliable.

## Drop List For Core

These should not be part of the G-Agent core roadmap now:

- Regional enterprise chat adapters that are not part of the core product surface.
- Hermes RL environments and batch trajectory generation.
- Every Hermes memory provider.
- Public skill hub before local skill lifecycle is stable.
- Modal, Daytona, Singularity as first-class early backends.
- Generic chat-only Web UI.
- Provider sprawl beyond clean OpenAI-compatible routing.
- Hidden autonomous skill/profile mutation.

## Open Questions

1. What exact historical JSONL backfill/import contract should ship for old sessions?
2. Should the formal Memory Manager stay markdown-first with indexes, or become provider-first with markdown export?
3. Should non-skill learning candidates apply through current stores now, or wait for MemoryManager/profile/routine manager polish?
4. Should Web UI wait for learning review, or start earlier with sessions/logs/approvals only?
5. Should Docker sandbox be part of the first public release or documented as an advanced deployment?
6. Should Honcho-style external memory be considered a plugin in v1, or deferred until local memory feels excellent?

## Bottom Line

The valuable core from Hermes is the growth loop: session recall, memory manager, learning review, procedural skills, approvals, and context compression.

The valuable core from Nanobot is the operating surface: WebSocket/Web UI, OpenAI API, channel reliability, MCP hardening, shared runner, and test organization.

G-Agent should combine those into a narrower product: an agentic character runtime that grows with the owner across real chat channels, visual identity, memory, skills, and routines.
