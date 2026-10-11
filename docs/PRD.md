# G-Agent — Product Requirements

**Status**: Draft
**Scope**: This document defines what G-Agent is, who it is for, and the requirements that
scope its runtime, channels, memory, controls, learning loop, and execution surfaces. It is
the reference for issues and roadmap work.

## Problem

Most agent setups stop at chat. A conversation ends and the context is gone. Tools are
re-run from scratch, decisions are not recorded, and there is no durable scope or audit
trail. When a setup does try to persist, it usually does so by trusting a hosted service with
the owner's memory, tools, and channels.

That leaves two gaps. First, continuity: an agent that cannot remember prior work,
preferences, or decisions is not an operator, it is a search box with a prompt. Second,
control: an agent that runs tools and touches files without reviewable, reversible changes
is hard to trust with real work.

G-Agent is built around both gaps at once: persistent identity and memory on the owner's
machine, with every automatic change inspectable and reversible.

## Who it is for

- A solo builder or developer running one or more always-on agents on their own machine or
  small server.
- A small team that wants a shared operator for email, calendar, files, scheduled jobs, and
  repeatable workflows without handing state to a hosted platform.
- A person who wants a persistent digital identity — voice, memory, visual presence — that
  answers across the channels they already use.
- Contributors who want to extend channels, tools, memory, and learning without forking a
  hosted product.

## Goals

- Give a single operator the execution reach of a small company while keeping state local and
  under their control.
- Make memory durable and useful: recall prior sessions, preferences, people, projects, and
  decisions, and keep that recall from bloating every prompt.
- Make presence real: the same character answers on WhatsApp, Telegram, Discord, Email, CLI,
  a local Web UI, and OpenAI-compatible clients.
- Make autonomy safe: risky actions pass through approvals, and every automatic change to
  memory, skills, or profile is reviewable and reversible.
- Stay installable and inspectable by someone who is not the original author.

## Non-goals

- No hosted cloud service or multi-tenant SaaS.
- No broad channel set in core. Slack, Matrix, and Teams expansion is a plugin or a later
  option, not a first-priority surface.
- No self-modifying code, skills, or profile changes without owner review.
- No research, reinforcement-learning, or batch-trajectory machinery in core.
- No companion or fake-consciousness positioning. Continuity is a feature, not a claim about
  being human.
- No promise of release dates. Work is ordered by priority, not by calendar.

## Requirements

Statuses below reflect what the current source tree does. `[implemented]` means the surface
exists and is wired; `[partial]` means a first slice exists with named gaps; `[planned]` means
it is not built yet.

### Runtime and boundaries

- **R1 — Local-first runtime.** `[implemented]` — the runtime runs from a source checkout on
  the owner's machine, reads a single config surface at `~/.g-agent/config.json`
  (`g_agent/config/loader.py`), and isolates environments through the `G_AGENT_DATA_DIR`
  environment variable (`g_agent/utils/helpers.py`, `PRIMARY_DATA_DIR = ".g-agent"`).
- **R2 — Workspace and tool boundary.** `[implemented]` — file and shell tools stay inside
  the configured workspace via `tools.restrictToWorkspace`, trusted media and project folders
  are added through `tools.allowedPaths` (`g_agent/config/schema.py`), and risky actions pass
  through an approval policy (`g_agent/security/approval_policy.py`; test:
  `tests/test_allowed_paths.py`).
- **R3 — Owner and guest separation.** `[implemented]` — separate profiles keep owner and
  guest environments isolated, with guest tool boundaries enforced in the agent loop
  regardless of policy configuration (`g_agent/character/profile.py` `is_guest`; test:
  `tests/test_guest_enforcement.py`).

### Presence and channels

- **R4 — Multi-channel presence.** `[partial]` — one character answers across WhatsApp
  (bridge), Telegram, Discord, Email, Slack, CLI, and a WebSocket channel
  (`g_agent/channels/`). Shared capability contracts exist (`channels/capabilities.py`), but
  WhatsApp media send, sandbox-path error text, delivery diagnostics, and per-channel media
  tests are incomplete.
- **R5 — OpenAI-compatible API.** `[partial]` — `/v1/models` and `/v1/chat/completions` with
  SSE streaming work (`g_agent/api/server.py`, `g_agent/api/openai_compat.py`), alongside a
  local product API for sessions, approvals, learning, profiles, and routines.
  `/v1/responses` and full multimodal normalization are not implemented.
- **R6 — Local Web UI control room.** `[partial]` — a browser surface for chat plus memory,
  skills, approvals, routines, channels, and provider settings. The React source exists under
  `backend/agent/g_agent/webui/`, but no build output is tracked, the API serves `webui/dist/`
  only when present, and `webui/package.json` still names the package `nanobot-webui`.

### Memory and continuity

- **R7 — Durable session store.** `[partial]` — SQLite with WAL (`PRAGMA journal_mode=WAL`)
  and FTS5 search, `tool_calls` and `media_refs` tables, and channel/session filtering in
  `g_agent/session/sqlite_store.py`, dual-written beside legacy JSONL. Historical JSONL
  backfill and migration docs remain.
- **R8 — Recall across sessions.** `[partial]` — `session_search`
  (`g_agent/agent/tools/session_search.py`), `/history`, and `/sessions` recall prior work.
  Context windows around each hit and grouped summaries are still narrow.
- **R9 — Memory manager.** `[partial]` — one builtin markdown-backed provider with prefetch
  recall and context fencing (`g_agent/memory/manager.py`, `memory/builtin.py`,
  `memory/context.py`). Write cadence, manager-routed memory tools, and explicit
  feedback/update/remove actions remain.
- **R10 — Character profile.** `[partial]` — identity, voice, boundaries, and visual config
  exist as a profile model and a stable prompt section (`g_agent/character/profile.py`,
  `store.py`, `visual.py`). Live switching isolation, per-profile visual merge, and
  owner-visible profile diffs remain.

### Control and observability

- **R11 — Shared command surface.** `[implemented]` — one command router
  (`g_agent/command/router.py`, `command/builtin.py`) serves all channels with a consistent
  set of slash commands for status, logs, sessions, memory, skills, routines, approvals, and
  context.
- **R12 — Approvals and audit.** `[partial]` — risky shell and filesystem actions are
  classified and persisted as approval records, and can be approved, denied, or allowlisted
  per session or permanently (`g_agent/security/approval_policy.py`,
  `security/approval_state.py`). A broader risky-action test matrix and security-doc updates
  remain.
- **R13 — Insights and logs.** `[implemented]` — metrics, insights, and task checkpoints
  expose session, tool, model, and provider activity, plus recent failed calls, to the owner
  (`g_agent/observability/insights.py`, `metrics.py`; tests: `tests/test_insights.py`).

### Learning

- **R14 — Owner-reviewed learning loop.** `[partial]` — a learning queue holds memory,
  profile, skill, routine, relationship, and tool-quirk candidates with diff, reason, risk,
  and rollback metadata (`g_agent/learning/queue.py`, `reviewer.py`). Apply and rollback are
  complete for skill candidates only (`learning/apply.py` `_apply_skill`); a memory candidate
  applies only with an explicit directive, and profile, routine, relationship, and tool-quirk
  candidates return `manual_review_required`. Auto-apply stays off by default.
- **R15 — Skills as procedural memory.** `[partial]` — a `SKILL.md` store, validator,
  manager, drafts, and owner-reviewed activation exist, with background skill proposals
  (`g_agent/skills/store.py`, `validator.py`, `manager.py`, `agent/tools/skills.py`).
  Supporting-file lifecycle and injection/script security scans remain.
- **R16 — Background review.** `[partial]` — an opt-in reviewer
  (`g_agent/learning/reviewer.py`, `BackgroundLearningReviewer`) inspects recent work and
  proposes candidates after a response, so learning never blocks the main turn. Review cadence
  per candidate type is not yet configurable.

### Execution and long-running work

- **R17 — Context engine and compression.** `[partial]` — a pluggable context engine
  (`g_agent/context/engine.py`) and a `ContextCompressor` (`context/compressor.py`) build a
  stable prompt order and produce reference-only summaries behind `/compact`. Automatic
  triggering inside the agent loop, protected tail/head policy, and tool-output pruning on the
  live path remain.
- **R18 — Routines, cron, and triggers.** `[partial]` — a routine model, store, runner,
  scheduler, and script pre-processing exist (`g_agent/routines/`). `routines/model.py`
  declares `cron`, `webhook`, `api_event`, and `file_change` trigger types, but
  `routines/scheduler.py` only wires cron routines; multi-skill workflows and authenticated
  webhook/API triggers with idempotency remain.
- **R19 — Toolsets, MCP, and execution backends.** `[partial]` — capability toolsets
  (`agent/tools/toolsets.py`), stdio/SSE/streamable-HTTP MCP (`mcp/manager.py`), subagents
  (`agent/subagent.py`), and local plus transient Docker execution (`execution/local.py`,
  `execution/docker.py`) exist. Subagent status/cancellation events, per-profile toolset
  policy, and additional backends remain.
- **R20 — Public trust and packaging.** `[implemented]` — install scripts for Linux, macOS,
  and Windows (`deploy/linux/install.sh`, `deploy/macos/install.sh`,
  `deploy/windows/install.ps1`), a release checklist
  (`docs/release-notes/checklist.md`), security docs (`docs/security.md`), and an install
  matrix (`docs/install-matrix.md`) exist. Docs must stay aligned with shipped behavior.

## Success signals

- An owner can run the agent for a week and trust it without reading raw logs to know what it
  did.
- Every automatic change to memory, skills, or profile is reviewable and reversible from chat
  or CLI before it takes effect.
- A channel failure surfaces a clear, actionable error instead of a silent drop.
- Recall finds the relevant prior decision or file from an earlier session.
- A new user can install, onboard, and reach a working channel from the docs without help from
  the original author.
- The Web UI lets the owner control character, memory, approvals, and routines without editing
  JSON by hand.

## Open questions

- Should local memory be simple SQLite facts, markdown files, or both?
- Should an external memory provider for cross-session user modeling ship in the first release,
  or stay deferred until the local manager is stable?
- Which visual identity anchor is the default: a LoRA trigger, a reference image folder, or a
  generated profile description?
- How strict should auto-apply be for low-risk memory candidates, if it is allowed at all?
- Should routines ship before the Web UI review screens, or only once owner review is
  ergonomic?
- Is the Docker sandbox part of the first public release, or documented as advanced setup?
