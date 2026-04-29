# G-Agent Roadmap

G-Agent should become an agentic character runtime: a personal digital identity that can live across chat apps, understand media, operate tools, remember context, and become more useful through repeated interaction.

This roadmap is based on the current G-Agent repo plus two local reference checkouts:

- `nanobot-ref/`: useful for gateway, Web UI, API, channel, MCP, and test-organization patterns.
- `hermes-agent-ref/`: useful for long-term learning, memory, skills, session search, approvals, context compression, routines, and multi-environment runtime patterns.

Neither reference should be merged wholesale. G-Agent's advantage should be a character-first product: identity, relationship memory, visual presence, owner workflows, and channels such as WhatsApp, Telegram, Discord, Web UI, and OpenAI-compatible clients.

## North Star

G-Agent is not a generic automation gateway. It is a framework for building agentic characters that can:

- live across WhatsApp, Telegram, Discord, local Web UI, and API clients
- keep a durable identity, voice, visual profile, boundaries, and relationship model
- remember owner preferences, people, projects, routines, and past decisions
- generate and send visual outputs such as selfie, mirror, avatar, outfit, and scene images
- operate tools safely inside a workspace plus explicit trusted path roots
- learn from usage by proposing memory updates, routines, and skills
- run scheduled or triggered workflows without needing the owner to babysit every turn
- expose enough logs, approvals, and controls that the owner can trust it daily

The important product bet is character depth. If the goal were only "many channels plus tools", Nanobot or Hermes would be enough. G-Agent should own the layer where a digital identity becomes a persistent character that grows with the user.

## Reference Audit

### Nanobot Contributes Infrastructure

Nanobot's strongest ideas are runtime surfaces and operational hardening:

- Web UI and WebSocket chat control room
- OpenAI-compatible API surface
- command router for shared slash commands
- channel tests and improved Telegram, Discord, WhatsApp reliability
- MCP wrapper hardening
- reusable agent runner
- subagent status/cancellation patterns
- memory compaction/dream-loop inspiration
- organized tests by agent, channel, provider, tool, cron, and config area

Use Nanobot as an implementation reference for "how does the app talk to users and tools?"

### Hermes Contributes Learning Runtime

Hermes is the stronger reference for "how does the agent grow over time?"

Concrete valuable pieces found in `hermes-agent-ref/`:

- `hermes_state.py`: SQLite session store with WAL, FTS5 message search, session metadata, cost/token counters, parent session chains, and lock retry.
- `tools/session_search_tool.py`: searches old conversations, groups by session, truncates around matches, and summarizes relevant transcripts with a cheaper model.
- `agent/memory_manager.py`: one memory integration point, builtin memory plus at most one external provider, prefetched recall blocks, lifecycle hooks, and context fencing.
- `plugins/memory/honcho/README.md`: cross-session user modeling with user/AI peer cards, session summaries, dialectic reasoning, and configurable recall/write cadence.
- `plugins/memory/holographic/README.md`: local SQLite fact store with FTS5 search, trust scoring, entity resolution, contradiction handling, and explicit fact feedback.
- `tools/skill_manager_tool.py`: skills as procedural memory, local `SKILL.md` creation/patch/delete, supporting files, validation, path safety, atomic writes, and optional guard scans.
- `tools/skills_tool.py`, `agent/skill_commands.py`, `agent/skill_preprocessing.py`: progressive skill loading, slash-command skill invocation, setup metadata, templates, references, and controlled preprocessing.
- `agent/prompt_builder.py`: memory guidance, session-search guidance, skill guidance, and prompt-injection checks for context files.
- `run_agent.py`: background memory and skill review after responses, nudge intervals, quiet review agent, and summaries of successful learning actions.
- `agent/context_engine.py`, `agent/context_compressor.py`: pluggable context engine, structured summaries, protected head/tail context, tool-output pruning, and redaction.
- `tools/approval.py`: dangerous-command detection, per-session approvals, permanent allowlist, gateway `/approve` and `/deny`, and context-local session identity.
- `gateway/platforms/api_server.py`: OpenAI-compatible `/v1/chat/completions`, `/v1/responses`, `/v1/models`, async runs, SSE events, health endpoints, request limits, and multimodal normalization.
- `hermes-already-has-routines.md`: cron routines, GitHub/webhook/API triggers, script pre-processing, multi-skill workflows, and delivery to chat platforms.
- `toolsets.py`: capability-based tool grouping so the runtime can expose smaller, safer tool bundles.
- `agent/insights.py`: session, cost, model, tool, skill, and platform usage insights.
- `tools/environments/`: local, Docker, SSH, Daytona, Singularity, and Modal execution backend patterns.
- `acp_adapter/`: later reference for editor/agent-client integrations.

Use Hermes as an implementation reference for "how does the character accumulate wisdom and repeatable behavior?"

## Product Principles

- Character-first, not channel-first.
- Local/private by default, remote-capable later.
- Owner-reviewed learning before autonomous mutation.
- One built-in memory provider plus one optional external memory provider, not memory-backend chaos.
- WhatsApp, Telegram, Discord, Web UI, API first.
- Explicit trusted path roots for owner media and projects.
- Skills are procedural memory; normal memory is declarative facts and preferences.
- Background review happens after the user gets a response, so learning never blocks the main task.
- Every automatic change to memory, skills, or character profile should be inspectable, reversible, and explainable.
- Integrations should be toolsets or plugins, not permanent core bloat.

## What Not To Borrow

Do not turn G-Agent into a generic everything agent.

- Do not bring unsupported external chat adapters into core.
- Do not bring Hermes research/RL/batch trajectory machinery into core.
- Do not bring every Hermes memory plugin into core.
- Do not bring every execution backend into the first public runtime.
- Do not make the Web UI a plain message box; it should control character, memory, channels, tools, approvals, and routines.
- Do not allow self-modifying code, skills, or profile changes without owner review and rollback.
- Do not hide unsafe shell/tool behavior behind natural language.
- Do not copy upstream docs verbatim; rewrite ideas into G-Agent's product language.

Optional plugin or later-stage items:

- Slack expansion
- Matrix
- Microsoft Teams
- ACP/editor integration
- Modal/Daytona/Singularity backends
- external memory providers beyond one selected provider
- public skill hub

## Target Architecture

The target runtime should be organized around these durable pieces:

- **Character Profile**: identity, tone, boundaries, visual profile, channel behavior, and owner relationship model.
- **Session Store**: SQLite-backed conversations with FTS5 search, channel/source metadata, parent session chains, token/cost fields, and media references.
- **Memory Manager**: built-in local memory plus one optional external provider, recall prefetch, context fencing, lifecycle hooks, and write cadence.
- **Learning Queue**: proposed memory, profile, routine, and skill changes awaiting owner review.
- **Skill Store**: local `SKILL.md` workflows with references, templates, scripts, assets, validation, patching, and rollback.
- **Context Engine**: prompt assembly, session search, compression, protected recent context, tool-output pruning, and redaction.
- **Tool Registry + Toolsets**: capability bundles for safe, channel-aware, profile-aware tool exposure.
- **Approval System**: dangerous action detection, per-session pending approvals, chat commands, CLI/Web UI review, and permanent allowlist.
- **Channel Gateway**: WhatsApp, Telegram, Discord, WebSocket/Web UI, OpenAI-compatible API, and later webhooks.
- **Routine Engine**: cron jobs, webhook/API triggers, script pre-processing, multi-step workflows, and delivery to selected platforms.
- **Execution Backend**: local default, optional Docker sandbox, optional SSH/VPS target, later advanced backends only if needed.

Data flow:

1. Channel receives message or routine trigger.
2. Session store records inbound event and media references.
3. Context engine pulls character profile, relevant memories, session search, and active routine/skill context.
4. Agent loop runs with bounded tools and toolsets.
5. Approval system pauses risky actions until owner approves.
6. Outbound result is sent to the originating channel or requested destination.
7. Background review agent proposes memory/profile/skill/routine updates.
8. Learning queue stores diffs for owner review.
9. Accepted changes update memory, skills, routines, or character profile for future turns.

## Phase 0: Stabilize Current Runtime

Goal: make the current owner setup boring and debuggable.

- Keep workspace restriction enabled by default.
- Keep `tools.allowedPaths` as the official way to trust owner media/project folders.
- Keep OpenAI-compatible image providers simple, document `gpt-image-2` proxy configuration, and add focused tests for proxy response formats.
- Fix Google Workspace discovery so services can find `gws` and `gcloud` from the service environment.
- Add easy log inspection from CLI and chat: recent gateway logs, channel logs, failed tool calls, and provider errors.
- Add owner-local troubleshooting docs for PATH, systemd user services, sandbox behavior, and trusted media folders.

## Phase 1: Session Store And Recall

Goal: give G-Agent a real memory substrate before adding self-improvement.

- Replace scattered/per-channel transcript assumptions with a SQLite session store.
- Store sessions, messages, source channel, chat id, user id, model, token/cost counters, tool calls, media refs, and titles.
- Enable WAL and write-lock retry for concurrent gateway/channel use.
- Add FTS5 search across messages.
- Add `session_search` tool:
  - search old conversations
  - group by session
  - truncate around matches
  - summarize with auxiliary model
  - preserve commands, paths, URLs, decisions, and unresolved items
- Add slash command aliases such as `/search`, `/history`, and `/sessions`.
- Add tests for persistence, FTS search, concurrent writes, and channel/source filtering.

Reference: `hermes-agent-ref/hermes_state.py`, `hermes-agent-ref/tools/session_search_tool.py`.

## Phase 2: Commands, Logs, And Approvals

Goal: make the owner able to control the agent from chat, CLI, and later Web UI.

- Normalize slash commands across WhatsApp, Telegram, Discord, CLI, and Web UI.
- Minimum commands:
  - `/status`
  - `/logs`
  - `/new`
  - `/stop`
  - `/restart`
  - `/whoami`
  - `/sessions`
  - `/search`
  - `/approve`
  - `/deny`
  - `/tools`
  - `/memory`
  - `/skills`
- Add dangerous action detection for shell and filesystem tools.
- Track pending approvals per session/chat.
- Let owners approve once, deny, or add a narrow persistent allowlist.
- Surface blocked-command reason clearly in chat and logs.
- Avoid broad auto-approval until the policy is tested.

Reference: `hermes-agent-ref/tools/approval.py`, `hermes-agent-ref/agent/skill_commands.py`.

## Phase 3: Core Channel Reliability

Goal: make the daily channels solid before adding more channels.

- WhatsApp:
  - reliable media send/receive
  - QR/login status command
  - owner-only admin commands
  - bridge restart handling
  - better outbound routing
  - clear local-file and sandbox errors
- Telegram:
  - media parity with WhatsApp
  - group/DM policy
  - topic/thread session mapping if useful
  - rate/flood handling
  - Markdown-safe responses
- Discord:
  - DM and mention policy
  - attachment and image replies
  - reconnect behavior
  - persistent thread/session mapping
- Shared:
  - channel capability flags
  - message splitting
  - media envelopes
  - delivery receipts/errors
  - tests for each channel's command and media path

Reference: Nanobot channel updates and Hermes gateway release notes.

## Phase 4: Web UI And OpenAI-Compatible API

Goal: add a first-party control room and make other clients able to talk to G-Agent.

- Add WebSocket channel with:
  - local-first bind
  - token auth
  - streaming deltas
  - session list
  - media upload envelope
  - structured lifecycle events
- Add REST endpoints:
  - health/status
  - sessions
  - session history
  - upload media
  - pending approvals
  - learning queue
  - character profiles
- Add OpenAI-compatible API:
  - `GET /v1/models`
  - `POST /v1/chat/completions`
  - `POST /v1/responses` later
  - streaming/SSE
  - image input normalization
  - request size limits
- Build Web UI around G-Agent's actual product:
  - session sidebar
  - chat thread
  - image lightbox
  - connection/channel status
  - character/profile switcher
  - memory and skill review
  - approvals
  - routine scheduler
  - provider and visual settings

References: `nanobot-ref/webui`, `nanobot-ref/nanobot/channels/websocket.py`, `nanobot-ref/nanobot/api/server.py`, `hermes-agent-ref/gateway/platforms/api_server.py`.

## Phase 5: Character Profiles And Visual Identity

Goal: make the "agentic character" layer explicit and first-class.

- Add character profile files:
  - name
  - role
  - voice/tone
  - boundaries
  - relationship model
  - channel behavior
  - visual identity config
  - proactive behavior policy
- Add profile switching for multiple characters.
- Add visual provider config per profile:
  - OpenAI-compatible proxy image generation
  - local/reference image roots
  - prompt templates for selfie, mirror, avatar, outfit, and scene
  - identity anchor fields
  - fallback behavior when image provider fails
- Keep examples generic; do not bake a private character into docs or defaults.
- Add owner-visible profile diffs when learning proposes identity changes.

## Phase 6: Memory Manager And Owner Model

Goal: create durable character memory without prompt bloat.

- Add built-in local memory provider:
  - owner facts
  - preferences
  - people/relationships
  - projects
  - routines
  - environment/tool quirks
  - character reflections
- Add context fencing so recalled memory is never treated as new user input.
- Add pre-turn recall and post-turn sync lifecycle hooks.
- Add write cadence settings:
  - immediate/manual
  - async after turn
  - session-end
  - every N turns
- Allow at most one external memory provider at a time.
- Evaluate Honcho-style user modeling as optional later:
  - user representation
  - AI self-representation
  - relationship card
  - session summary
  - dialectic reasoning
- Evaluate local fact-store ideas before external dependency:
  - FTS search
  - trust score
  - contradiction detection
  - explicit feedback/update/remove actions

References: `hermes-agent-ref/agent/memory_manager.py`, `hermes-agent-ref/plugins/memory/honcho/README.md`, `hermes-agent-ref/plugins/memory/holographic/README.md`.

## Phase 7: Owner-Reviewed Learning Loop

Goal: let the character improve without silently drifting.

- Add background review after response delivery.
- Review agent should inspect:
  - recent conversation
  - tool-heavy work
  - repeated errors
  - new owner preferences
  - new project facts
  - reusable workflow patterns
  - character/profile drift
- Produce learning candidates:
  - `memory_candidate`
  - `profile_candidate`
  - `skill_candidate`
  - `routine_candidate`
  - `relationship_update`
  - `tool_quirk`
- Store candidates in a learning queue with:
  - diff
  - reason
  - source session/message ids
  - risk level
  - accept/reject/edit state
  - rollback metadata
- Expose review through CLI/chat first, Web UI later.
- Default mode should be owner-reviewed, not auto-apply.
- Add auto-apply only for low-risk facts after enough trust and tests.

Reference: `hermes-agent-ref/run_agent.py` background memory/skill review and nudge intervals.

## Phase 8: Skills As Procedural Memory

Goal: make repeated successful workflows become reusable skills.

- Define G-Agent skill layout:
  - `SKILL.md`
  - `references/`
  - `templates/`
  - `scripts/`
  - `assets/`
- Support skill actions:
  - list
  - view
  - create draft
  - patch
  - validate
  - activate
  - disable
  - rollback
- Add validation:
  - required YAML frontmatter
  - size limits
  - path traversal prevention
  - allowed supporting-file directories
  - prompt-injection scan
  - optional security scan for scripts
- Separate declarative memory from procedural skills:
  - memory remembers "what is true"
  - skills remember "how to do this workflow"
- Let background review propose skills after repeated or tool-heavy work.
- Require owner review before activation.
- Add skill command invocation once the base lifecycle is stable.

References: `hermes-agent-ref/tools/skill_manager_tool.py`, `hermes-agent-ref/tools/skills_tool.py`, `hermes-agent-ref/agent/skill_commands.py`, `hermes-agent-ref/agent/skill_preprocessing.py`.

## Phase 9: Context Engine And Compression

Goal: keep long-running character sessions useful without stuffing everything into every prompt.

- Add pluggable context engine interface.
- Build prompt sections in a stable order:
  - platform/system policy
  - character profile
  - current channel/session state
  - relevant memory
  - relevant session search
  - active skills/routines
  - recent messages
- Add compression:
  - structured running summary
  - protected recent tail
  - protected identity/profile head
  - tool-output pruning
  - sensitive redaction
  - fallback model for compression failures
- Make summaries reference-only, not new instructions.
- Add tests for prompt injection from context files, memory blocks, and retrieved transcripts.

References: `hermes-agent-ref/agent/context_engine.py`, `hermes-agent-ref/agent/context_compressor.py`, `hermes-agent-ref/agent/prompt_builder.py`.

## Phase 10: Routines, Cron, And Triggers

Goal: let the character act on recurring workflows and external events.

- Add routine model:
  - name
  - trigger type
  - schedule/webhook/API event
  - target character
  - destination channel
  - allowed tools
  - approval policy
  - delivery policy
- Support cron schedules for:
  - reminders
  - reports
  - daily/weekly check-ins
  - monitoring
  - content generation
- Support script pre-processing:
  - script runs first
  - stdout becomes context
  - result routes into the agent
- Support multi-skill workflows later.
- Add webhook/API triggers after command/session/store foundation is stable.
- Keep proactive behavior opt-in and bounded by quiet hours and consent gates.

Reference: `hermes-agent-ref/hermes-already-has-routines.md`.

## Phase 11: Toolsets, MCP, And Execution Backends

Goal: make tools safer and more modular without bloating the core.

- Group tools by capability:
  - safe
  - file
  - terminal
  - web/search
  - vision
  - image generation
  - messaging
  - memory
  - skills
  - routines
  - MCP
  - code execution
  - subagents
- Upgrade MCP:
  - stdio, SSE, and streamable HTTP configs
  - schema normalization
  - per-tool timeouts
  - transient retry
  - OAuth only when needed
  - path traversal checks
- Refactor subagents:
  - shared runner
  - bounded tool access
  - cancellation
  - status events
  - completion summaries routed back to origin channel
- Add execution backend strategy:
  - local default
  - Docker sandbox for risky tasks
  - SSH/VPS for always-on deployment
  - advanced backends later only when demanded

References: `hermes-agent-ref/toolsets.py`, `hermes-agent-ref/tools/environments/`, `nanobot-ref/nanobot/agent/tools/mcp.py`, `nanobot-ref/nanobot/agent/runner.py`.

## Phase 12: Insights, Packaging, And Public Trust

Goal: make the project installable, inspectable, and safe enough for users outside the founder setup.

- Add insights:
  - session count
  - channel activity
  - tool usage
  - skill usage
  - model/provider usage
  - token/cost estimates
  - failed tool/provider calls
- Clean install matrix:
  - Linux
  - macOS
  - Windows/WSL
- Separate owner profile vs guest/default profile.
- Add release checklist for backend, bridge, Web UI, docs, service files, and config migration.
- Add security docs for:
  - workspace sandbox
  - trusted path roots
  - channel allowlists
  - tool approval policy
  - secrets and service environment
  - memory/profile review
- Keep docs focused on product surfaces; workflow reports belong under department/report docs, not main user docs.

Reference: `hermes-agent-ref/agent/insights.py`.

## First 30 Days

The highest-leverage implementation order:

1. Add SQLite session store with FTS5 search and channel/source metadata.
2. Add `session_search` and `/search` so the agent can recall prior work.
3. Normalize slash commands and implement `/status`, `/logs`, `/new`, `/sessions`, `/approve`, and `/deny`.
4. Add dangerous action approval state per session.
5. Finish current visual/image-provider docs for OpenAI-compatible `gpt-image-2` proxy usage.
6. Harden WhatsApp media, sandbox path errors, and local file delivery.
7. Add minimal built-in memory provider with context fencing.
8. Add learning queue schema but keep all changes owner-reviewed.
9. Add draft skill lifecycle: list, view, create draft, patch, validate, activate, rollback.
10. Start WebSocket/API foundation after session store and command router are stable.

This order matters: session store and commands make the agent inspectable; approvals make it safer; memory and skills then have a real substrate; Web UI becomes a control room instead of a thin chat page.

## Open Decisions

- Should local memory start as simple SQLite facts, markdown files, or both?
- Should Honcho-style external user modeling be optional in v1 or deferred?
- Which visual identity anchor is the default: LoRA trigger, reference image folder, or generated profile description?
- How strict should auto-apply be for low-risk memory candidates?
- Should routines ship before Web UI review screens, or only after owner review is ergonomic?
- Should Docker sandbox be part of the first public release or documented as advanced setup?

## Current Product Thesis

Build the runtime in this order:

1. reliable channels
2. searchable session memory
3. owner-visible controls
4. character profile and visual identity
5. reviewed learning loop
6. procedural skills
7. routines and triggers
8. Web UI/API polish
9. optional advanced integrations

That path keeps G-Agent distinct: not the biggest channel bot, not the most research-heavy agent, but the most personal agentic character runtime.

## Detailed Implementation Plans

The phase-by-phase execution plans live in `docs/roadmap/`. These files expand
the roadmap into versioned build plans without replacing the product thesis in
this document.

- `docs/roadmap/v0.1-stabilize-current-runtime.md`
- [x] `docs/roadmap/v0.2-session-store-and-recall.md` — SQLite/FTS/session-search first slice shipped; historical JSONL backfill and richer search context remain follow-up work.
- [x] `docs/roadmap/v0.3-commands-logs-approvals.md` — core command router, logs/history/sessions, approve/deny replay shipped; persisted approval state remains follow-up work.
- [ ] `docs/roadmap/v0.4-core-channel-reliability.md` — channel supervisor/retry/media basics exist; capability flags, media envelopes, splitting, and delivery diagnostics remain.
- [ ] `docs/roadmap/v0.5-web-ui-openai-api.md` — not shipped; no first-party product API server, WebSocket channel, or Web UI exists.
- [x] `docs/roadmap/v0.6-character-profiles-visual-identity.md` — core profile model/store/context shipped; full switching isolation, per-profile visual merge, and reviewable profile diffs remain.
- [x] `docs/roadmap/v0.7-memory-manager-owner-model.md` — first MemoryManager/provider/fencing slice shipped; write cadence and manager-routed memory tools remain.
- [x] `docs/roadmap/v0.8-owner-reviewed-learning-loop.md` — queue/model/chat command, skill candidate edit/apply/rollback, and opt-in background reviewer first slice shipped; non-skill apply flows remain.
- [x] `docs/roadmap/v0.9-skills-procedural-memory.md` — skill store/validator/manager/tool plus `/skills`, draft patching, owner-reviewed skill apply/rollback, and background skill proposals shipped; broader file lifecycle remains.
- [x] `docs/roadmap/v0.10-context-engine-compression.md` — first slice and `/compact` compressor replacement shipped; automated compression triggering in `AgentLoop` remains.
- [x] `docs/roadmap/v0.11-routines-cron-triggers.md` — first slice and script preprocessing shipped; multi-skill workflows and webhook/API triggers remain.
- [x] `docs/roadmap/v0.12-toolsets-mcp-execution.md` — local backend/toolset/MCP slice shipped; streamable HTTP MCP and Docker execution backend remain.
- [x] `docs/roadmap/v0.13-insights-packaging-public-trust.md` — completed slice; insights, guest enforcement, profile setup, release checklist, install matrix, and security docs are covered.
