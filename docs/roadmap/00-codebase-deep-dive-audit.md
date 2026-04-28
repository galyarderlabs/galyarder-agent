# Codebase Deep-Dive Audit For Roadmap Execution

This audit grounds the roadmap plans in the current repository. It is written for
agents that need to implement roadmap milestones without rediscovering the whole
codebase from scratch.

## Current Runtime Shape

Most production code lives under `backend/agent/g_agent/`.

Current important modules:

- `agent/loop.py`: core runtime loop. Receives `InboundMessage`, builds prompt
  through `ContextBuilder`, runs LLM/tool loop, applies tool policy, writes
  JSONL session history through `SessionManager`, writes task checkpoints, and
  emits outbound messages.
- `agent/context.py`: prompt builder. Loads bootstrap files, markdown memory,
  skill summaries, runtime metadata, media, and conversation history.
- `agent/memory.py`: markdown-backed memory store. Maintains `MEMORY.md`,
  `PROFILE.md`, `RELATIONSHIPS.md`, `PROJECTS.md`, `FACTS.md`, `LESSONS.md`,
  `SUMMARIES.md`, and daily notes. Has lightweight retrieval, fact indexing,
  semantic matching, and profile alias compatibility.
- `session/manager.py` and `session/sqlite_store.py`: current session store.
  JSONL files remain readable under the active data directory while
  `SessionManager.save()` dual-writes to SQLite. The SQLite store has WAL,
  FTS5, tool-call rows, media refs, and channel/session filtering. Explicit
  historical JSONL backfill and richer search context windows are still
  follow-up work.
- `channels/slash_commands.py` and `command/`: deterministic command
  dispatcher. Already has `/start`, `/new`, `/reset`, `/compact`, `/context`,
  `/status`, `/whoami`, `/memory`, `/model`, `/tools`, `/cron`, `/packs`,
  `/search`, `/history`, `/sessions`, `/logs`, `/approve`, `/deny`, `/help`,
  and `/commands`. `/search` currently means web search; `/history` is
  cross-session search.
- `channels/base.py`: base channel abstraction with allowlist checks and
  `InboundMessage` publishing.
- `channels/manager.py`: starts enabled channels, supervises restarts, routes
  outbound messages, and supports plugin channel registration.
- `channels/whatsapp.py`, `channels/telegram.py`, `channels/discord.py`,
  `channels/email.py`, `channels/slack.py`: channel implementations. The core
  roadmap should improve these before adding many new adapters.
- `agent/tools/selfie.py`: visual identity tool. Supports `huggingface`,
  `cloudflare`, and `openai-compatible` image generation. It has special payload
  behavior for `gpt-image-*`, LoRA trigger support, reference-image vision
  extraction, and delivery through outbound messages.
- `config/schema.py`: single Pydantic config surface. Already includes channels,
  model routing, providers, Google Workspace, proactive settings, gateway,
  browser safety, exec path append, image generation config, visual identity,
  plugins, `restrict_to_workspace`, `allowed_paths`, tool policy, risky tools,
  and approval mode.
- `agent/runtime.py`: JSON task checkpoint store under `workspace/state/tasks`.
  Tracks running tasks, status, events, cancellation, resume hints, and output
  previews.
- `observability/metrics.py`: append-only JSONL metrics store. Records LLM/tool
  calls, memory recall, cron runs, success rates, p95 latency, top tools, and
  alerts.
- `proactive/engine.py`: quiet hours and Google Calendar reminder dedupe.
- `cron/service.py` and `cron/types.py`: existing scheduled job runtime.
- `plugins/`: plugin base/loader. Plugins can register tools and channels.
- `agent/skills.py`: current skill loader. It is not yet a full procedural
  memory lifecycle with draft, validation, activation, and rollback.
- `agent/subagent.py` and `agent/tools/spawn.py`: existing subagent capability.
  Needs bounded toolsets, status events, cancellation hardening, and result
  summaries before becoming a public feature.
- `agent/tools/google_workspace.py`: Google Workspace access through `gws`.
  Existing issue: service environments may not see `gws` or `gcloud` unless
  PATH/config is explicit.

## Existing Tests To Preserve

Important tests under `backend/agent/tests/`:

- `test_allowed_paths.py`: workspace restriction and trusted path behavior.
- `test_selfie_tool.py`: visual identity and image generation behavior.
- `test_google_workspace_helpers.py` and `test_gws_client_env.py`: `gws` env and
  Google Workspace helper behavior.
- `test_session_new_command.py`: current JSONL session reset/archive behavior.
- `test_cli_command_surface.py`: CLI command surface expectations.
- `test_channel_reconnect.py`: channel supervisor restart behavior.
- `test_ported_channels.py`: channel compatibility behavior.
- `test_model_routing.py`, `test_provider_registry.py`,
  `test_litellm_provider.py`: provider and routing behavior.
- `test_memory_intelligence.py`: markdown memory retrieval/fact behavior.
- `test_proactive_engine.py`, `test_cron_service.py`: proactive/cron behavior.
- `test_metrics_http_server.py`, `test_metrics_retention_alerts.py`,
  `test_observability_metrics.py`: metrics behavior.
- `test_runtime_checkpoints.py`: task checkpoint behavior.
- `test_security_audit.py`, `test_security_fix.py`: safety baseline.
- `test_tool_validation.py`: tool schema/validation expectations.

Any roadmap implementation must keep these green or update them with deliberate
migration tests.

## Reference: Hermes Agent

Use Hermes for long-term runtime mechanics.

Most valuable files:

- `hermes-agent-ref/hermes_state.py`
  - SQLite-backed session store.
  - WAL mode and write-lock retry.
  - `sessions` and `messages` tables.
  - FTS5 virtual table and triggers.
  - parent session chains.
  - session titles and rich session listing.
  - model/config/token/cost fields.
- `hermes-agent-ref/tools/session_search_tool.py`
  - FTS search across all sessions.
  - recent session browsing when query is empty.
  - current session exclusion.
  - parent/child session resolution.
  - per-session transcript loading.
  - bounded parallel summarization.
  - fallback raw preview when summarizer is unavailable.
- `hermes-agent-ref/tools/approval.py`
  - dangerous command patterns.
  - context-local session identity.
  - per-session pending approval queues.
  - `/approve`, `/deny`, `/approve all`.
  - permanent allowlist.
  - CLI and gateway approval behavior.
  - cron-mode denial for unattended dangerous commands.
- `hermes-agent-ref/agent/memory_manager.py`
  - one built-in memory provider plus at most one external provider.
  - prefetch, queued prefetch, sync turn, lifecycle hooks.
  - context fencing for recalled memory.
  - provider tool routing.
- `hermes-agent-ref/tools/skill_manager_tool.py`
  - local skill create/edit/patch/delete.
  - YAML frontmatter validation.
  - content size limits.
  - path traversal protection.
  - supporting file directories.
  - atomic writes.
  - rollback on security scan failure.
- `hermes-agent-ref/tools/skills_tool.py`
  - skill listing/viewing.
  - linked file access.
  - platform compatibility.
  - disabled skill support.
  - readiness/prerequisite metadata.
  - prompt-injection checks.
- `hermes-agent-ref/agent/skill_commands.py`
  - slash-command skill invocation.
  - preload skill prompt generation.
  - absolute path guidance for scripts/references.
- `hermes-agent-ref/agent/context_engine.py`
  - pluggable context engine interface.
  - compression thresholds and optional context tools.
- `hermes-agent-ref/agent/context_compressor.py`
  - tool output pruning.
  - protected head/tail.
  - structured summary.
  - iterative summary updates.
  - redaction before summarization.
  - anti-thrashing after ineffective compression.
- `hermes-agent-ref/agent/prompt_builder.py`
  - prompt injection scan for context files.
  - tool-use guidance.
  - skill prompt cache.
  - tool/toolset-aware skill filtering.
- `hermes-agent-ref/gateway/platforms/api_server.py`
  - OpenAI-compatible `/v1/chat/completions`, `/v1/responses`, `/v1/models`.
  - request byte limits.
  - auth.
  - SSE streaming and keepalive.
  - multimodal content normalization.
  - async runs and structured lifecycle events.
- `hermes-agent-ref/toolsets.py`
  - capability-based tool grouping.
- `hermes-agent-ref/tools/environments/`
  - local, Docker, SSH, Daytona, Modal, Singularity execution backends.
- `hermes-agent-ref/agent/insights.py`
  - runtime insights for sessions, cost, tools, models, skills, and platforms.

Do not copy Hermes wholesale. G-Agent should adapt these mechanics into the
agentic character product model.

## Reference: Nanobot

Use Nanobot for app surfaces, channel/API organization, and operational
hardening.

Most valuable files:

- `nanobot-ref/nanobot/api/server.py`
  - compact OpenAI-compatible API with `/v1/chat/completions`, `/v1/models`,
    `/health`, multipart media, SSE streaming, and response shaping.
- `nanobot-ref/nanobot/channels/websocket.py`
  - WebSocket channel, auth headers, static SPA serving, media limits, signed
    media URLs, MIME hardening, streaming events, and connection handling.
- `nanobot-ref/webui/`
  - React/Vite UI components for chat list, thread shell, composer, image
    lightbox, session hooks, media encoding worker, and API client.
- `nanobot-ref/nanobot/command/router.py` and
  `nanobot-ref/nanobot/command/builtin.py`
  - shared command router pattern.
- `nanobot-ref/nanobot/agent/runner.py`
  - shared tool-using agent runner, hooks, tool result budgeting, orphan tool
    result cleanup, finalization retry, tool concurrency, and LLM timeout.
- `nanobot-ref/nanobot/agent/tools/mcp.py`
  - stdio/SSE/streamable HTTP MCP transports.
  - schema normalization for OpenAI tool definitions.
  - tool/resource/prompt wrappers.
  - per-tool timeouts.
  - transient retry.
  - enabled tool allowlists.
  - protocol pollution hints.
- `nanobot-ref/nanobot/agent/tools/schema.py`
  - reusable typed schema fragments for tool parameters.
- `nanobot-ref/nanobot/channels/telegram.py`,
  `nanobot-ref/nanobot/channels/discord.py`,
  `nanobot-ref/nanobot/channels/whatsapp.py`
  - channel reliability and test patterns.
- `nanobot-ref/tests/`
  - useful test organization by agent, channels, providers, tools, cron, config,
    API, and Web UI.

Do not bring Nanobot's broad channel set wholesale. G-Agent should prioritize
WhatsApp, Telegram, Discord, Email, CLI, Web UI, and OpenAI-compatible API.

## Current Gaps By Milestone

### v0.1 Stabilization

Current repo already has visual proxy support, Google Workspace tools, metrics,
task checkpoints, and workspace restriction. Missing pieces are mostly better
operator experience: log inspection, clearer service PATH diagnostics, and more
focused image proxy tests.

### v0.2 Session Store

Current repo keeps JSONL sessions readable through `SessionManager` and now
dual-writes into `SessionSQLiteStore` with WAL, FTS5, channel/session filters,
tool-call metadata, and media refs. The remaining gap is explicit historical
JSONL backfill plus richer context windows around search hits.

### v0.3 Commands And Approvals

Current repo now has `SlashCommandDispatcher`, `g_agent.command`, shared quoted
argument parsing, `/logs`, `/history`, `/sessions`, `/approve`, and `/deny`.
`AgentLoop` still owns live approval replay. Remaining gaps are a persisted
approval state model, narrow allowlists, broader command handler extraction, and
a dedicated risky-action classifier test matrix.

### v0.4 Channel Reliability

Current channels exist and `ChannelManager` supervises restarts. The plan should
extend existing channel files, not add new channel frameworks. Capability flags,
media envelopes, delivery diagnostics, and command parity are the key missing
pieces.

### v0.5 Web UI/API

Current repo has no first-party API server or WebSocket channel equivalent to
Nanobot/Hermes. It should start from a thin local API, then layer Web UI on top.

### v0.6 Character Profiles

Current repo now has `CharacterProfile`, `CharacterStore`, and a stable profile
prompt section. Remaining gaps are live profile switching isolation,
profile-level visual config wiring into `SelfieTool`, dedicated validation
coverage, and reviewable profile diffs.

### v0.7 Memory Manager

Current memory is markdown-backed and useful, but it is not provider-oriented
and does not have explicit lifecycle hooks. Add a manager around the existing
`MemoryStore` first; do not throw the markdown memory away.

### v0.8 Reviewed Learning

Current runtime can write memory directly through tools and now has
`LearningCandidate` plus `LearningQueue` storage. Remaining gaps are
accept/reject/edit/apply flows, rollback wiring, and a background reviewer hook.

### v0.9 Skills

Current `agent/skills.py` loads skills, and the first management slice now
includes skill store, validator, manager, drafts, and the `skill_manage` tool.
Remaining gaps are full owner-reviewed activation, rollback, and command
lifecycle coverage.

### v0.10 Context Engine

Current code has a pluggable context engine interface, `DefaultContextEngine`,
and an initial `ContextCompressor`. Remaining gaps are automatic compression
triggering inside `AgentLoop` and replacing legacy `/compact` internals.

### v0.11 Routines

Current code has routine model, store, runner, scheduler, and `/routines`.
Remaining gaps are multi-skill workflows and webhook/API triggers.

### v0.12 Toolsets/MCP/Execution

Current code has static capability toolsets, per-message tool filtering, stdio
and SSE MCP registration, a shared agent runner, subagent cancellation, and a
local execution backend. Remaining gaps are streamable HTTP MCP, Docker
execution backend, and per-profile toolset policy.

### v0.13 Public Trust

Current metrics, install docs, security docs, release checklist, and a first
insights engine are present. The latest provider/skill/failed-call insights and
guest-enforcement changes are still uncommitted and need cleanup plus targeted
test coverage before v0.13 is complete.

## Planning Standard For Roadmap Files

Each version plan should include:

- current state in this repo
- reference files to inspect
- exact module targets
- implementation slices in dependency order
- data model or API shape when relevant
- tests to add/update
- migration/backward compatibility
- risks and guardrails
- acceptance criteria
- suggested first PR boundary

If a plan does not name current G-Agent files and reference files, it is not
ready for another agent to implement.
