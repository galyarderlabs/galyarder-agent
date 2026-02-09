# OpenClaw Delta Roadmap — Lean `g-agent` Runtime

Last updated: 2026-02-09

This roadmap tracks what we deliberately adopted from OpenClaw direction, while keeping `g-agent` lightweight, cross-platform, and operator-controlled.

---

## North Star

Build a personal assistant that is:

- proactive (can initiate useful work),
- memory-strong (recalls user context reliably across sessions),
- workflow-capable (Google + browser + channel orchestration),
- safe by default (strict boundaries for personal and guest modes).

---

## Scope Boundaries

This roadmap is **delta-only**.  
We are not trying to reproduce OpenClaw’s full platform surface.

In scope:

- high-value runtime behavior
- memory quality
- proactive orchestration
- security posture for mixed personal/guest usage
- observability for daily operations

Out of scope:

- heavy framework expansion
- channel sprawl without clear reliability/ops value
- large control-plane abstractions that reduce local clarity

---

## Delta Tracks and Status

### 1) Execution Runtime with Checkpoints

**Status:** implemented (`v1`)

Implemented:

- task lifecycle checkpoints (`plan -> execute -> verify -> reflect -> done`)
- persisted task state in workspace (`state/tasks/*.json`)
- restart-safe completion tracking

Code:

- `backend/agent/g_agent/agent/runtime.py`
- `backend/agent/g_agent/agent/loop.py`

### 2) Memory Retrieval Intelligence

**Status:** implemented (`v1`)

Implemented:

- memory metadata schema (`type`, `confidence`, `source`, `last_seen`, `supersedes`)
- dedup/supersede behavior
- ranked recall via confidence + recency + relevance

Code:

- `backend/agent/g_agent/agent/memory.py`

### 3) Proactive Agent Engine

**Status:** implemented (`v1`)

Implemented:

- perfect-day schedule prompts
- calendar watch lead-time reminders
- quiet-hours gating + dedupe state

Code:

- `backend/agent/g_agent/proactive/engine.py`
- `backend/agent/g_agent/cli/commands.py`
- `backend/agent/g_agent/cron/service.py`

### 4) Multimodal Output

**Status:** implemented (`v1`)

Implemented:

- outbound `message` tool supports text/image/voice/sticker/document
- generated voice + sticker fallback from plain text
- workflow-pack media flags (`--voice`, `--image`, `--sticker`)

Code:

- `backend/agent/g_agent/agent/tools/message.py`
- `backend/agent/g_agent/agent/workflow_packs.py`

### 5) Workflow Packs (Google-first)

**Status:** implemented (`v1`)

Implemented packs:

- `daily_brief`
- `meeting_prep`
- `inbox_zero_batch`

Implemented scope:

- intent-level orchestration prompting
- multimodal output options
- media-first `--silent` mode

Code:

- `backend/agent/g_agent/agent/workflow_packs.py`
- `backend/agent/g_agent/agent/loop.py`

### 6) Guest Safety Boundary

**Status:** implemented (`v1`)

Implemented:

- policy presets: `personal_full`, `guest_limited`, `guest_readonly`
- channel/sender scoped policy map
- deny-by-default behavior for guest restrictions

Code:

- `backend/agent/g_agent/config/presets.py`
- `backend/agent/g_agent/agent/loop.py`
- `backend/agent/g_agent/cli/commands.py`

### 7) Observability and Evaluation Harness

**Status:** implemented (`v1`)

Implemented:

- local metrics event sink
- tool/cron reliability snapshots
- latency + success-rate surfaces in status/doctor paths

Code:

- `backend/agent/g_agent/observability/metrics.py`
- `backend/agent/g_agent/cli/commands.py`

---

## What Remains (Hardening Backlog)

### Recently Completed

- Telegram/WhatsApp reconnect harness coverage:
  - `backend/agent/tests/test_channel_reconnect.py`
- OAuth edge-case regression checks added for expired refresh token and scope drift:
  - `backend/agent/tests/test_google_oauth_edges.py`
  - `backend/agent/g_agent/agent/tools/google_workspace.py`
- Provider-specific retry taxonomy for transient tool failures:
  - `backend/agent/g_agent/agent/loop.py`
  - `backend/agent/tests/test_retry_and_idempotency.py`
- Memory quality fixtures and ranking consistency assertions:
  - `backend/agent/tests/fixtures/memory_conflicts.md`
  - `backend/agent/tests/test_memory_intelligence.py`
  - `backend/agent/g_agent/agent/memory.py`
- Multilingual overlap fixture coverage + summary/fact drift checks:
  - `backend/agent/tests/fixtures/memory_multilingual.md`
  - `backend/agent/tests/test_memory_intelligence.py`
  - `backend/agent/g_agent/agent/memory.py`
- Metrics export path + dashboard-friendly scrape summary:
  - `backend/agent/g_agent/observability/metrics.py`
  - `backend/agent/g_agent/cli/commands.py`
  - `backend/agent/tests/test_observability_metrics.py`
- Optional lightweight HTTP `/metrics` endpoint mode (disabled by default):
  - `backend/agent/g_agent/observability/http_server.py`
  - `backend/agent/g_agent/cli/commands.py`
  - `backend/agent/tests/test_metrics_http_server.py`

### P0 — Reliability Gaps (next)

1. expand integration-level reconnect harness (beyond unit-level channel tests)

### P1 — Memory Quality

1. add semantic normalization checks for mixed-language synonym drift
2. add regression checks for conflicting facts across profile/long-term/custom scopes

### P2 — Observability Ops

1. add retention/pruning controls for `events.jsonl` growth management
2. add alert-threshold summary output for uptime/SLO monitoring

---

## Exit Criteria for Delta Phase

Delta phase is considered complete when:

- all P0 items are implemented and covered by automated tests
- memory regression fixtures are in CI and stable
- one optional metrics export path is available and documented
- production checklist in `backend/agent/SECURITY.md` remains valid without exceptions

---

## Relationship to Main Docs

- product-level narrative: `README.md`
- backend setup and operations: `backend/agent/README.md`
- security posture and hardening: `backend/agent/SECURITY.md`

This roadmap only tracks the remaining OpenClaw-derived delta work.
