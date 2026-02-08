# OpenClaw Delta Roadmap (Post-Nanobot Parity)

Last update: 2026-02-08

This roadmap tracks the focused features adopted from the OpenClaw direction, without pulling in a heavy/macOS-centric stack.

## Goal

Build a personal assistant that is:
- proactive (can initiate useful actions),
- memory-strong (accurate recall across sessions),
- workflow-capable (Google + browser + channel orchestration),
- safe for personal and guest profiles.

## Delta Tracks

### 1) Execution Runtime with Checkpoints
- Status: **implemented (v1)**
- Scope:
  - task lifecycle checkpoints (`plan -> execute -> verify -> reflect -> done`)
  - persisted task state in workspace (`state/tasks/*.json`)
  - restart-safe task completion tracking
- Code:
  - `backend/agent/g_agent/agent/runtime.py`
  - `backend/agent/g_agent/agent/loop.py`

### 2) Memory Retrieval Intelligence
- Status: **implemented (v1)**
- Scope:
  - memory schema metadata (`type`, `confidence`, `source`, `last_seen`, `supersedes`)
  - dedup + supersede logic
  - ranked recall using confidence + recency + relevance
- Code:
  - `backend/agent/g_agent/agent/memory.py`

### 3) Proactive Agent Engine
- Status: **implemented (v1)**
- Scope:
  - perfect-day style scheduled prompts
  - calendar watch reminders (lead-time windows)
  - quiet-hours gating + state dedupe
- Code:
  - `backend/agent/g_agent/proactive/engine.py`
  - `backend/agent/g_agent/cli/commands.py`
  - `backend/agent/g_agent/cron/service.py`

### 4) Multimodal Output
- Status: **implemented (v1)**
- Scope:
  - outbound `message` tool supports text/image/voice/sticker/document
  - generated voice and sticker media from plain text fallback
  - workflow-pack media mode flags (`--voice`, `--image`, `--sticker`)
- Code:
  - `backend/agent/g_agent/agent/tools/message.py`
  - `backend/agent/g_agent/agent/workflow_packs.py`

### 5) Workflow Packs (Google-first)
- Status: **implemented (v1)**
- Packs:
  - `daily_brief`
  - `meeting_prep`
  - `inbox_zero_batch`
- Scope:
  - intent-level orchestration prompting
  - multi-mode output support
  - `--silent` media-first response mode
- Code:
  - `backend/agent/g_agent/agent/workflow_packs.py`
  - `backend/agent/g_agent/agent/loop.py`

### 6) Guest Safety Boundary
- Status: **implemented (v1)**
- Presets:
  - `personal_full`
  - `guest_limited`
  - `guest_readonly`
- Scope:
  - policy matrix enforcement by channel/sender scope
  - deny-by-default tool restrictions for guest profiles
- Code:
  - `backend/agent/g_agent/config/presets.py`
  - `backend/agent/g_agent/agent/loop.py`
  - `backend/agent/g_agent/cli/commands.py`

### 7) Observability + Evaluation Harness
- Status: **implemented (v1)**
- Scope:
  - local metrics event sink
  - tool/cron reliability snapshots
  - latency and success-rate summary surface in CLI status/doctor paths
- Code:
  - `backend/agent/g_agent/observability/metrics.py`
  - `backend/agent/g_agent/cli/commands.py`

## Remaining Hardening Work

1. Expand E2E harness for Telegram/WhatsApp reconnect and OAuth edge cases.
2. Add regression fixture set for memory conflict resolution quality.
3. Add optional metrics export endpoint/file shipper for dashboarding.
4. Add broader failure taxonomy for tool retries (provider-specific mapping).

