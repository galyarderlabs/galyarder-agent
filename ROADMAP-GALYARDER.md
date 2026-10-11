# G-Agent — Roadmap

G-Agent is a local-first runtime for building an agentic character: a persistent digital
identity with its own voice, memory, tools, and presence across WhatsApp, Telegram,
Discord, Email, CLI, and OpenAI-compatible clients. It is for one person or a small team
who wants an operator that remembers context, runs scheduled work, and stays under local
control instead of a hosted chat box. This document describes where the runtime is now and
the order in which it grows. It is a direction, not a schedule.

## Where this comes from

This project started from an early copy of [nanobot](https://github.com/HKUDS/nanobot)
and [hermes-agent](https://github.com/NousResearch/hermes-agent), both MIT licensed, and
has since been substantially rewritten and extended. It is not a GitHub fork; it is a
derivative copy with its own product direction. Both upstream copyright notices are
retained in [`LICENSE`](LICENSE), and a file-level comparison is recorded in
[`docs/reports/hermes-nanobot-reference-audit.md`](docs/reports/hermes-nanobot-reference-audit.md).

nanobot informs the Web UI, the WebSocket/API layer, channel reliability, MCP, the shared
runner, and test organization. hermes-agent informs session search, the memory manager,
the learning loop, skills, approvals, context compression, and routines. The direction
that is G-Agent's own is character depth: identity, relationship memory, visual presence,
owner-reviewed learning, and channel presence under local control. The upstreams are
acknowledged as lineage, not as ongoing merge sources.

## Where it is now

The runtime is real and in daily use. Most code lives in `backend/agent/g_agent/`, with a
Node.js WhatsApp bridge in `backend/agent/bridge/`, install scripts in `deploy/`, and a
MkDocs site in `docs/`. The repository carries 429 tracked files, 68 backend test files,
and release notes through `v0.1.21` (the latest published release).

What runs today, verified against the source tree:

- **Channels.** WhatsApp (through the bridge), Telegram, Discord, Email, Slack, CLI, and a
  WebSocket channel. Shared capability contracts live in `g_agent/channels/capabilities.py`,
  with normalized media and error envelopes in `channels/media.py` and `channels/errors.py`.
- **Session store.** `g_agent/session/sqlite_store.py` uses SQLite with WAL
  (`PRAGMA journal_mode=WAL`), FTS5 search (`messages_fts`), plus `tool_calls` and
  `media_refs` tables, dual-written beside legacy JSONL.
- **Shared command router.** `g_agent/command/router.py` and `command/builtin.py` serve one
  set of slash commands across channels: `/status`, `/logs`, `/new`, `/sessions`, `/history`,
  `/search`, `/approve`, `/deny`, `/approvals`, `/tools`, `/memory`, `/skills`, `/learn`,
  `/routines`, `/cron`, `/compact`, `/insights`, `/profile`, and more.
- **Approvals.** Risky shell and filesystem classification in
  `g_agent/security/approval_policy.py`, durable approval state in
  `security/approval_state.py`, approve-once, approve-for-session, and narrow allowlists.
- **Character profiles.** `g_agent/character/profile.py`, `store.py`, and `visual.py`, with a
  stable `# Character Profile` prompt section and guest tool boundaries enforced in the
  agent loop regardless of policy config.
- **Memory.** Markdown-backed memory plus a first `MemoryManager` slice
  (`g_agent/memory/manager.py`) with a builtin provider and context fencing.
- **Learning.** An owner-reviewed queue (`g_agent/learning/queue.py`) with skill
  apply/rollback (`learning/apply.py`) and an opt-in background reviewer
  (`learning/reviewer.py`).
- **Skills.** A `SKILL.md` store, validator, manager, and owner-reviewed activation under
  `g_agent/skills/`, with builtin skills for cron, github, summarize, tmux, weather, and
  skill-creator.
- **Context.** A pluggable context engine (`g_agent/context/engine.py`) and a
  `ContextCompressor` (`context/compressor.py`) behind `/compact`.
- **Routines.** A routine model, store, runner, scheduler, and script pre-processing under
  `g_agent/routines/`.
- **Tools.** Capability toolsets (`agent/tools/toolsets.py`), stdio/SSE/streamable-HTTP MCP
  (`mcp/manager.py`), subagents (`agent/subagent.py`), and local plus transient Docker
  execution (`execution/local.py`, `execution/docker.py`).
- **Product API.** A local HTTP server (`g_agent/api/server.py`) with health, status,
  sessions, media upload, approvals, learning, profiles, routines, `/v1/models`, and
  `/v1/chat/completions` with SSE streaming.
- **Observability and packaging.** Metrics and insights (`g_agent/observability/`), install
  scripts for Linux, macOS, and Windows (`deploy/`), a release checklist
  (`docs/release-notes/checklist.md`), and an install matrix (`docs/install-matrix.md`).

What is still thin or rough:

- **The Web UI is not a shipped surface.** The React source exists under
  `backend/agent/g_agent/webui/`, but no build output is tracked, the API only serves
  `webui/dist/` if it happens to exist, and `webui/package.json` still names the package
  `nanobot-webui`.
- **Channel reliability is uneven.** Capability contracts exist, but WhatsApp media send,
  sandbox-path error text, delivery receipts, and per-channel media tests are incomplete.
- **Learning apply is partial.** `learning/apply.py` applies skill candidates and applies a
  memory candidate only when it carries an explicit directive. Profile, routine,
  relationship, and tool-quirk candidates return `manual_review_required` and cannot be
  applied or rolled back yet.
- **The session store still leans on legacy JSONL.** There is no backfill/import command for
  old JSONL-only workspaces, and search returns narrow context windows around hits.
- **Context compression is manual.** It runs when the owner calls `/compact`; it does not
  trigger automatically inside the agent loop.
- **Routine triggers are schedule-only.** `routines/model.py` declares `cron`, `webhook`,
  `api_event`, and `file_change` trigger types, but `routines/scheduler.py` only wires cron
  routines ("for now we assume `routine.schedule` is a cron expression").
- **Google Workspace tools can fail in service environments** when `gws` or `gcloud` is not
  on the service PATH.
- **The OpenAI-compatible API covers chat completions and model listing.** `/v1/responses`
  is not implemented.

## Now

- **Finish channel reliability for the daily channels.** WhatsApp, Telegram, and Discord are
  how the character is actually reached. Local-file media send errors, sandbox and
  allowed-path error text, delivery diagnostics, and per-channel media tests need to be solid
  before more channels are considered.
- **Ship the Web UI as a control room.** The source is present but the surface is not
  shipped, and it still carries reference naming. The owner should be able to review memory,
  skills, approvals, and routines without editing JSON by hand.
- **Extend the owner-reviewed learning loop to non-skill candidates.** Memory, profile,
  routine, relationship, and tool-quirk candidates can be queued but not applied or rolled
  back. A queue that cannot be acted on is not yet a learning loop.
- **Add session backfill and richer recall.** Import historical JSONL into SQLite with a
  dry-run, and widen the context returned around each search hit. Without this, old work
  stays only half-searchable.
- **Trigger context compression inside the agent loop.** Today the owner runs `/compact` by
  hand. Automatic triggering with a protected recent tail and identity head keeps long
  sessions useful without prompt bloat.

## Next

- **Add the OpenAI-compatible `/v1/responses` endpoint.** Clients that speak the newer
  response shape cannot use the runtime yet. This also needs clearer multimodal input
  normalization and request limits.
- **Wire routine webhook and API triggers.** The trigger types are declared but only cron is
  scheduled. External events should be able to start a workflow, with trigger auth and a
  replay/idempotency key.
- **Finish the skill file lifecycle.** Supporting-file add/update/delete plus
  prompt-injection and script security scans. Skills are procedural memory, and they need the
  same review rigor as declarative memory.
- **Wire memory write cadence and manager-routed memory tools.** The manager exists but the
  write path and tool routing are not fully in place. This is what makes memory durable
  instead of incidental.
- **Harden subagents.** Status and cancellation events, bounded toolsets, and completion
  summaries routed back to the origin channel.
- **Fix Google Workspace discovery from service environments.** `gws` and `gcloud` should be
  found from the service environment, with owner-facing troubleshooting docs.

## Later

- **Additional execution backends.** Local is the default and Docker handles transient risky
  commands. An SSH/VPS target for always-on deployment is a later step, and only after local
  and Docker are stable.
- **One optional external memory provider.** A single provider may be added alongside the
  builtin one for cross-session user modeling. This is deferred until the local manager is
  stable.
- **Editor and agent-client integration.** An adapter that lets editors and agent clients
  talk to the runtime, considered only after the API surface settles.

## Not planned

- **No hosted cloud service.** G-Agent is local-first and self-hosted by design.
- **No broad channel set in core.** Slack, Matrix, and Teams expansion stays a plugin or a
  later option, not a core priority.
- **No self-modifying code, skills, or profile changes without owner review and rollback.**
- **No research, reinforcement-learning, or batch-trajectory machinery in the core.**
- **No wholesale import of every reference memory plugin or every execution backend.**
- **No fake-consciousness or companion framing.** The character is a tool with continuity,
  not a claim about being human.

## How to follow along

Open an issue using the repository templates (`.github/ISSUE_TEMPLATE/bug_report.yml` or
`feature_request.yml`) for a bug or a focused feature. For a change you want to make
yourself, read [`CONTRIBUTING.md`](CONTRIBUTING.md) and open a pull request; keep it scoped
to one slice. The phase-by-phase build plans live in `docs/roadmap/`, and the documentation
site is at https://galyarderlabs.github.io/galyarder-agent/.
