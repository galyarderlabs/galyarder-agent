# Roadmap Completion TODO

This is the master execution checklist for finishing the G-Agent roadmap. It is
derived from the current codebase plus `ROADMAP.md`, the roadmap phase files,
and `docs/reports/hermes-nanobot-reference-audit.md`.

Use this file as the working board. The phase documents explain why each item
exists; this file tracks what remains to ship.

## Product Target

G-Agent is an agentic digital character runtime. The finished product should
let an owner run durable characters with identity, memory, visual presence,
tools, routines, channel presence, safe approvals, and owner-reviewed learning.

The product is not a generic automation gateway. Hermes is the reference for
growth loops, memory, learning, skills, context, approvals, and routines.
Nanobot is the reference for channels, Web UI, OpenAI-compatible API, MCP,
runner structure, and operational hardening.

## Current Baseline

- [x] Python runtime lives in `backend/agent/g_agent/`.
- [x] WhatsApp bridge lives in `backend/agent/bridge/`.
- [x] MkDocs source lives in `docs/`.
- [x] Tests are flat under `backend/agent/tests/`.
- [x] Session SQLite first slice exists in `session/sqlite_store.py`.
- [x] Shared command router exists in `command/`.
- [x] Character profile core exists in `character/`.
- [x] Learning queue first slice exists in `learning/`.
- [x] Skill lifecycle first slice exists in `skills/` and `agent/tools/skills.py`.
- [x] Context engine and compressor first slice exists in `context/`.
- [x] Routine first slice exists in `routines/`.
- [x] Toolset and MCP first slice exists in `agent/tools/toolsets.py` and
  `mcp/manager.py`.
- [x] Insights and public-trust first slice exists in `observability/insights.py`
  plus docs.
- [x] Shared channel contracts exist for capability flags, media envelopes, and
  delivery result/error types.
- [ ] No first-party product API server exists under `g_agent/api/`.
- [ ] No WebSocket channel exists at `channels/websocket.py`.
- [ ] No first-party `webui/` exists.
- [ ] No formal memory manager exists under `g_agent/memory/`.
- [ ] No background learning reviewer exists.
- [ ] No streamable HTTP MCP transport exists.
- [ ] No Docker execution backend exists.

## Execution Order

Build in this order unless a production bug forces a hotfix:

1. Finish v0.4 channel reliability.
2. Finish v0.7 memory manager and owner model.
3. Finish v0.8/v0.9 learning and skills growth loop.
4. Finish v0.10 context compression integration.
5. Finish v0.11 routines and triggers.
6. Finish v0.12 MCP and execution backend gaps.
7. Build v0.5 API, WebSocket, and Web UI after backend state is stable.
8. Keep v0.13 trust docs current after each shipped slice.

Reason: sessions, commands, approvals, channels, memory, and learning are the
substrate. Web UI should become a control room on top of real state, not a thin
chat page over unfinished internals.

## P0: Commit And Push Hygiene

- [ ] Keep commits scoped to one roadmap slice.
- [ ] After every commit, update this TODO with what shipped and what is next.
- [ ] After every commit, report:
  - commit hash
  - changed files
  - verification commands
  - next best move
- [ ] Push only when the owner asks or when explicitly finishing a release slice.

## v0.1: Stabilize Current Runtime

Status: mostly shipped, keep as maintenance baseline.

- [x] Keep workspace restriction enabled by default.
- [x] Keep `tools.allowedPaths` as the official trusted-path mechanism.
- [x] OpenAI-compatible image proxy path exists in visual/selfie tooling.
- [x] Google Workspace helper paths are covered by tests.
- [x] `/logs` exists and exposes bounded task checkpoint output.
- [x] Troubleshooting docs exist for setup and runtime operations.
- [ ] Keep image proxy docs updated when provider payloads change.
- [ ] Keep service/PATH troubleshooting updated when `gws`, `gcloud`, or bridge
  service behavior changes.
- [ ] Keep runtime log redaction tests current as new secret-like fields are
  introduced.

Verification target:

- [ ] `ruff check g_agent tests --select F`
- [ ] `python -m compileall -q g_agent`
- [ ] focused tests around visual providers, Google Workspace helpers, runtime
  checkpoints, and security audit.

## v0.2: Session Store And Recall

Status: first slice shipped; polish remains.

- [x] Add `SessionSQLiteStore`.
- [x] Add `sessions`, `messages`, `tool_calls`, `media_refs`, and FTS tables.
- [x] Enable WAL and schema idempotency.
- [x] Add write retry.
- [x] Keep JSONL sessions readable.
- [x] Dual-write from `SessionManager.save()`.
- [x] Add SQLite cleanup for `/new`, archive, and delete.
- [x] Add `session_search`.
- [x] Add `/history` recall.
- [x] Preserve `/search` as web search.
- [x] Add punctuation-heavy fallback search for commands, paths, and URLs.
- [ ] Add explicit JSONL historical backfill/import command.
- [ ] Add backfill dry-run output.
- [ ] Add backfill conflict handling for duplicate session keys.
- [ ] Add richer context windows around each search hit.
- [ ] Add grouped search summaries by session.
- [ ] Add owner-facing SQLite/session status command.
- [ ] Add session title generation or owner-editable titles.
- [ ] Add parent-session lineage support for compacted/forked sessions.
- [ ] Add more channel/source filtering tests.
- [ ] Add migration docs for old JSONL-only workspaces.

Verification target:

- [ ] `pytest -q tests/test_session_sqlite_store.py tests/test_session_new_command.py`
- [ ] Search tests must preserve commands, paths, URLs, decisions, and unresolved
  items.

## v0.3: Commands, Logs, And Approvals

Status: core shipped; approval state remains incomplete.

- [x] Add shared `CommandRouter`.
- [x] Add shared `CommandContext`.
- [x] Wire direct CLI/chat command dispatch through shared router.
- [x] Add quoted-argument parsing.
- [x] Add helpful unknown command responses.
- [x] Add `/status`.
- [x] Add `/logs`.
- [x] Add `/new`.
- [x] Add `/sessions`.
- [x] Add `/history`.
- [x] Add `/approve` replay path.
- [x] Add `/deny`.
- [x] Add `/learn`.
- [x] Add `/skills`.
- [ ] Persist approval decisions into first-class approval state.
- [ ] Add approval ids that survive process restarts.
- [ ] Add approve-once behavior.
- [ ] Add approve-for-session behavior.
- [ ] Add narrow persistent allowlist behavior.
- [ ] Add owner command to list pending approvals.
- [ ] Add owner command to clear one pending approval by id.
- [ ] Add owner command to clear all pending approvals for a session.
- [ ] Add `security/approval_policy.py`.
- [ ] Add risky shell classifier examples.
- [ ] Add risky filesystem classifier examples.
- [ ] Add tests for dangerous command detection.
- [ ] Add tests for denied command replay safety.
- [ ] Move more legacy handlers from `channels/slash_commands.py` into
  `command/builtin.py`.
- [ ] Regenerate CLI docs after CLI command surface changes.

Verification target:

- [ ] `pytest -q tests/test_slash_command_router.py`
- [ ] Add `tests/test_approval_policy.py`.

## v0.4: Core Channel Reliability

Status: next best move; partial, not shipped.

- [x] Telegram channel file exists.
- [x] WhatsApp channel file exists.
- [x] Discord channel file exists.
- [x] Email channel file exists.
- [x] Slack channel file exists.
- [x] `BaseChannel._handle_message()` normalizes inbound text/media basics.
- [x] `BaseChannel._handle_message()` enforces `allow_from`.
- [x] `ChannelManager` supervises channel restarts.
- [x] `ChannelManager` retries outbound sends.
- [x] Tests cover reconnects, ported channel config, bridge token auth,
  CLI bridge login, and multimodal outbound basics.
- [ ] Add `channels/capabilities.py`.
- [ ] Define `ChannelCapabilities`.
- [ ] Add `supports_media_send`.
- [ ] Add `supports_media_receive`.
- [ ] Add `supports_buttons`.
- [ ] Add `supports_typing`.
- [ ] Add `supports_threads`.
- [ ] Add `supports_reactions`.
- [ ] Add `max_text_chars`.
- [ ] Add `parse_mode`.
- [ ] Expose capabilities from WhatsApp.
- [ ] Expose capabilities from Telegram.
- [ ] Expose capabilities from Discord.
- [ ] Expose capabilities from Email.
- [ ] Expose capabilities from Slack.
- [ ] Surface channel capabilities through `/status` or a channel diagnostics
  command.
- [ ] Add `channels/media.py`.
- [ ] Define normalized inbound media envelope.
- [ ] Define normalized outbound media envelope.
- [ ] Include path/url fields.
- [ ] Include mime type.
- [ ] Include filename.
- [ ] Include size.
- [ ] Include content hash when local file exists.
- [ ] Include channel metadata.
- [ ] Keep `InboundMessage.media: list[str]` compatibility while adding richer
  metadata.
- [ ] Add `channels/errors.py`.
- [ ] Define delivery result model.
- [ ] Define delivery error codes.
- [ ] Normalize auth failure errors.
- [ ] Normalize disconnected bridge errors.
- [ ] Normalize unsupported-media errors.
- [ ] Normalize sandbox/allowed-path errors.
- [ ] Normalize rate/flood errors.
- [ ] Normalize message-too-long errors.
- [ ] Add shared long-message splitter.
- [ ] Add per-channel split limits.
- [ ] Preserve code blocks when splitting where possible.
- [ ] Preserve links when splitting where possible.
- [ ] Add tests for splitter edge cases.
- [ ] Harden WhatsApp bridge diagnostics.
- [ ] Add WhatsApp QR/login status command or diagnostics surface.
- [ ] Distinguish bridge disconnected vs auth failed vs media failed.
- [ ] Improve WhatsApp local-file media send errors.
- [ ] Improve WhatsApp sandbox/allowed-path error text.
- [ ] Add WhatsApp media delivery tests.
- [ ] Harden Telegram formatting.
- [ ] Add Telegram HTML/Markdown escape helper tests.
- [ ] Add Telegram DM/group policy tests.
- [ ] Add Telegram rate/flood handling tests where practical.
- [ ] Harden Discord attachment replies.
- [ ] Add Discord DM/mention policy tests.
- [ ] Add Discord thread/session key mapping tests.
- [ ] Add delivery receipts/errors where channel APIs expose them.
- [ ] Extend `test_multimodal_outbound.py`.
- [ ] Add `test_channel_capabilities.py`.
- [ ] Add `test_media_envelope.py`.
- [ ] Add `test_whatsapp_media_delivery.py`.
- [ ] Add `test_telegram_formatting.py`.
- [ ] Add `test_discord_session_mapping.py`.
- [ ] Update `docs/channels.md`.
- [ ] Update `docs/troubleshooting.md` for channel diagnostics.

First PR boundary:

- [ ] Channel capabilities + media envelope + shared tests.

Verification target:

- [ ] `pytest -q tests/test_channel_reconnect.py tests/test_ported_channels.py tests/test_multimodal_outbound.py`
- [ ] new v0.4 tests listed above.

## v0.5: Web UI And OpenAI-Compatible API

Status: not shipped; build after core backend state is reliable.

- [x] `GatewayConfig` exists in `config/schema.py`.
- [x] `Agent`, `AgentLoop`, `MessageBus`, `ChannelManager`, and
  `SessionManager` expose reusable runtime hooks.
- [x] `observability/http_server.py` exists for metrics.
- [ ] Add `g_agent/api/`.
- [ ] Add `g_agent/api/server.py`.
- [ ] Add `g_agent/api/openai_compat.py`.
- [ ] Add API auth/token config.
- [ ] Add local-first bind defaults.
- [ ] Add request size limits.
- [ ] Add response error model.
- [ ] Add `GET /health`.
- [ ] Add `GET /status`.
- [ ] Add `GET /sessions`.
- [ ] Add `GET /sessions/{id}`.
- [ ] Add session history response model.
- [ ] Add media upload endpoint.
- [ ] Store uploaded media as refs, not raw blobs in sessions.
- [ ] Add `GET /approvals`.
- [ ] Add `POST /approvals/{id}/approve`.
- [ ] Add `POST /approvals/{id}/deny`.
- [ ] Add `GET /learning`.
- [ ] Add learning candidate detail endpoint.
- [ ] Add learning approve/reject/edit/apply endpoints.
- [ ] Add `GET /profiles`.
- [ ] Add profile detail endpoint.
- [ ] Add profile switch endpoint after profile isolation is implemented.
- [ ] Add `GET /v1/models`.
- [ ] Add `POST /v1/chat/completions`.
- [ ] Add non-streaming OpenAI-compatible chat response.
- [ ] Add streaming/SSE chat response.
- [ ] Normalize text input.
- [ ] Normalize image input.
- [ ] Normalize base64 data URLs.
- [ ] Add remote URL policy for multimodal input.
- [ ] Add `POST /v1/responses` later.
- [ ] Add `channels/websocket.py`.
- [ ] Add WebSocket token auth.
- [ ] Add WebSocket session mapping.
- [ ] Add streaming deltas.
- [ ] Add lifecycle events.
- [ ] Add tool-call events.
- [ ] Add approval-needed events.
- [ ] Add learning-candidate events.
- [ ] Add media-upload events.
- [ ] Add channel-status events.
- [ ] Add `webui/`.
- [ ] Build session sidebar.
- [ ] Build chat thread.
- [ ] Build image lightbox.
- [ ] Build connection/channel status panel.
- [ ] Build character/profile switcher.
- [ ] Build memory review panel.
- [ ] Build skill review panel.
- [ ] Build approvals panel.
- [ ] Build routine scheduler panel.
- [ ] Build provider and visual settings panel.
- [ ] Add Web UI tests or smoke tests.
- [ ] Add API tests.
- [ ] Add WebSocket tests.
- [ ] Add docs for API auth and local bind behavior.

First PR boundary:

- [ ] Minimal product API with health/status/sessions plus `/v1/models`.

Verification target:

- [ ] `pytest -q tests/test_api_*.py tests/test_websocket_*.py`
- [ ] Web UI smoke command once `webui/` exists.

## v0.6: Character Profiles And Visual Identity

Status: core shipped; isolation and visual merge remain.

- [x] `CharacterProfile` model exists.
- [x] `CharacterStore` can save/load/list profiles.
- [x] `CharacterStore` can create default owner and guest profiles.
- [x] `ContextBuilder` renders `# Character Profile`.
- [x] `/profile` can inspect and list profiles.
- [x] Global visual/selfie configuration exists.
- [x] OpenAI-compatible image proxy support exists.
- [x] Guest profile tool enforcement exists.
- [ ] Add dedicated profile validation tests.
- [ ] Fully wire profile switching into live `AgentLoop`.
- [ ] Ensure profile switching does not mix session history.
- [ ] Ensure profile switching does not mix memory context.
- [ ] Ensure profile switching does not mix tool policy.
- [ ] Add profile-level visual config.
- [ ] Merge profile-level visual config with global defaults.
- [ ] Pass merged visual config into `SelfieTool`.
- [ ] Add visual identity prompt template per profile.
- [ ] Add selfie template per profile.
- [ ] Add mirror template per profile.
- [ ] Add avatar template per profile.
- [ ] Add outfit template per profile.
- [ ] Add scene template per profile.
- [ ] Add identity anchor fields per profile.
- [ ] Add reference image roots per profile.
- [ ] Add fallback behavior when image provider fails.
- [ ] Add owner-visible profile diffs.
- [ ] Add profile diff apply/reject flow through learning queue.
- [ ] Keep docs generic and free of private character defaults.
- [ ] Update `docs/persona.md`.

Verification target:

- [ ] `pytest -q tests/test_character_profiles.py tests/test_selfie_tool.py tests/test_guest_enforcement.py`
- [ ] Add dedicated visual identity tests.

## v0.7: Memory Manager And Owner Model

Status: not shipped; highest priority after v0.4.

- [x] `MemoryStore` exists in `agent/memory.py`.
- [x] Markdown memory files exist.
- [x] `FACTS.md` exists.
- [x] `remember`, `recall`, and `update_profile` use current memory store.
- [x] `ContextBuilder` retrieves relevant memory before prompt assembly.
- [ ] Add `g_agent/memory/`.
- [ ] Add `memory/types.py`.
- [ ] Add `MemoryProvider` interface.
- [ ] Add provider `name`.
- [ ] Add provider `system_prompt_block()`.
- [ ] Add provider `prefetch(query, session_id="")`.
- [ ] Add provider `sync_turn(user_content, assistant_content, session_id="")`.
- [ ] Add provider `get_tool_schemas()`.
- [ ] Add provider `handle_tool_call(...)`.
- [ ] Add `memory/builtin.py`.
- [ ] Wrap existing `MemoryStore` as `BuiltinMemoryProvider`.
- [ ] Keep markdown files readable and writable.
- [ ] Keep current recall behavior stable.
- [ ] Add `memory/context.py`.
- [ ] Add context fencing helpers.
- [ ] Use explicit `<memory-context>` markers or equivalent.
- [ ] Strip nested memory tags from provider output.
- [ ] Add injection-pattern stripping for recalled memory blocks.
- [ ] Add `memory/manager.py`.
- [ ] Register builtin provider by default.
- [ ] Allow at most one external provider.
- [ ] Reject second external provider.
- [ ] Make provider failure non-fatal when builtin still works.
- [ ] Add manager-level pre-turn recall.
- [ ] Add manager-level post-turn sync hook.
- [ ] Add write cadence config.
- [ ] Add manual write cadence.
- [ ] Add async-after-turn write cadence.
- [ ] Add session-end write cadence.
- [ ] Add every-N-turns write cadence.
- [ ] Update `ContextBuilder` to call `MemoryManager`.
- [ ] Keep memory section order stable in prompts.
- [ ] Record memory recall metrics through manager.
- [ ] Add owner facts category.
- [ ] Add preferences category.
- [ ] Add people/relationships category.
- [ ] Add projects category.
- [ ] Add routines category.
- [ ] Add environment/tool quirks category.
- [ ] Add character reflections category.
- [ ] Add memory feedback/update/remove actions.
- [ ] Defer Honcho dependency.
- [ ] Defer external memory provider until local manager is stable.
- [ ] Update docs for memory architecture.

First PR boundary:

- [ ] Provider interface + builtin adapter + manager prefetch integration.

Verification target:

- [ ] Add `tests/test_memory_manager.py`.
- [ ] Add `tests/test_memory_context_fencing.py`.
- [ ] Existing memory tests still pass.

## v0.8: Owner-Reviewed Learning Loop

Status: partial; background reviewer missing.

- [x] `LearningCandidate` model exists.
- [x] `LearningQueue` persists candidates in SQLite.
- [x] `/learn` lists pending candidates.
- [x] `/learn` inspects pending candidates.
- [x] `/learn` approves candidates.
- [x] `/learn` rejects candidates.
- [x] `/learn` edits candidates.
- [x] `/learn` applies skill candidates.
- [x] `/learn` rolls back skill candidates.
- [x] Queue persists `diff_preview`.
- [x] Queue persists `applied_at`.
- [x] Queue persists rollback metadata.
- [ ] Add `learning/reviewer.py`.
- [ ] Add background review hook after response delivery.
- [ ] Ensure review never blocks the main response.
- [ ] Add reviewer config and cadence.
- [ ] Add memory review cadence.
- [ ] Add skill review cadence.
- [ ] Add routine review cadence.
- [ ] Add profile review cadence.
- [ ] Inspect recent conversation.
- [ ] Inspect tool-heavy work.
- [ ] Inspect repeated errors.
- [ ] Inspect new owner preferences.
- [ ] Inspect new project facts.
- [ ] Inspect reusable workflow patterns.
- [ ] Inspect character/profile drift.
- [ ] Produce `memory_candidate`.
- [ ] Produce `profile_candidate`.
- [ ] Produce `skill_candidate`.
- [ ] Produce `routine_candidate`.
- [ ] Produce `relationship_update`.
- [ ] Produce `tool_quirk`.
- [ ] Add source session ids.
- [ ] Add source message ids.
- [ ] Add reason field.
- [ ] Add risk level.
- [ ] Add candidate evidence hash.
- [ ] Add dedupe for repeated candidates.
- [ ] Ensure rejected candidates do not immediately reappear without new
  evidence.
- [ ] Add memory candidate apply flow.
- [ ] Add profile candidate diff/apply flow.
- [ ] Add routine candidate apply flow.
- [ ] Add relationship update apply flow.
- [ ] Add tool quirk apply flow.
- [ ] Add rollback path for non-skill candidates.
- [ ] Add `/learn` filters by type.
- [ ] Add `/learn` filters by risk.
- [ ] Add `/learn` filters by status.
- [ ] Add Web UI-ready queue APIs later.
- [ ] Keep auto-apply disabled by default.
- [ ] Add tests for reviewer candidate creation.
- [ ] Add tests for reviewer non-blocking behavior.
- [ ] Add tests for dedupe and rejected-candidate suppression.
- [ ] Update docs for owner-reviewed learning.

First PR boundary:

- [ ] Background reviewer skeleton + deterministic heuristic candidate creation
  behind opt-in config.

Verification target:

- [ ] `pytest -q tests/test_learning_skill_lifecycle.py`
- [ ] Add `tests/test_learning_reviewer.py`.

## v0.9: Skills As Procedural Memory

Status: partial; local lifecycle strong, background proposal missing.

- [x] Built-in skill store exists.
- [x] Custom skill store exists.
- [x] Draft skill directory exists under workspace state.
- [x] Skill validator exists.
- [x] Skill manager exists.
- [x] `skill_manage` tool exists.
- [x] Owner-reviewed skill candidate apply/edit/rollback exists.
- [x] Focused lifecycle command coverage exists.
- [x] Atomic draft patch operation exists.
- [x] Validation rollback exists for draft patches.
- [x] `/skills list` exists.
- [x] `/skills view` exists.
- [x] `/skills patch-draft` exists.
- [ ] Background reviewer proposes skill candidates.
- [ ] Add broader supporting-file lifecycle commands.
- [ ] Add create draft command through `/skills`.
- [ ] Add validate draft command through `/skills`.
- [ ] Add activate draft command through `/skills` or `/learn`.
- [ ] Add disable skill command.
- [ ] Add rollback active skill command outside candidate flow.
- [ ] Add delete draft command.
- [ ] Add supporting file add/update/delete operations.
- [ ] Enforce allowed supporting-file directories.
- [ ] Validate `references/`.
- [ ] Validate `templates/`.
- [ ] Validate `scripts/`.
- [ ] Validate `assets/`.
- [ ] Add optional security scan for scripts.
- [ ] Add prompt-injection scan for skill files.
- [ ] Add hidden-character scan for skill files.
- [ ] Add max-size policy per skill package.
- [ ] Add `/skill <name>` invocation later.
- [ ] Add skill setup metadata later.
- [ ] Add progressive loading improvements.
- [ ] Add tests for supporting-file operations.
- [ ] Add tests for script security scan.
- [ ] Add tests for prompt-injection scan.
- [ ] Update docs for procedural skills.

First PR boundary:

- [ ] Background skill candidate proposal using existing `LearningQueue` and
  `SkillManager`.

Verification target:

- [ ] `pytest -q tests/test_skill_commands.py tests/test_learning_skill_lifecycle.py`
- [ ] Add validator tests for supporting files and injection scanning.

## v0.10: Context Engine And Compression

Status: partial; automatic integration missing.

- [x] `ContextEngine` interface exists.
- [x] `DefaultContextEngine` adapter exists.
- [x] Deterministic prompt section building exists.
- [x] `ContextCompressor` exists.
- [x] Initial summarization exists.
- [x] Initial tool pruning exists.
- [ ] Add automated compression trigger in `AgentLoop`.
- [ ] Define token/message thresholds.
- [ ] Protect recent tail.
- [ ] Protect identity/profile head.
- [ ] Protect active approval context.
- [ ] Protect active tool results needed for current task.
- [ ] Prune large tool output.
- [ ] Redact sensitive data before compression.
- [ ] Add fallback model behavior for compression failures.
- [ ] Ensure summaries are reference-only, not instructions.
- [ ] Replace `/compact` internals with `ContextCompressor`.
- [ ] Preserve current `/compact` user-facing behavior.
- [ ] Add prompt-injection tests from context files.
- [ ] Add prompt-injection tests from memory blocks.
- [ ] Add prompt-injection tests from retrieved transcripts.
- [ ] Add tests for compression failure degradation.
- [ ] Add tests for protected recent tail.
- [ ] Add tests for tool output pruning.
- [ ] Update docs for context engine and compression.

First PR boundary:

- [ ] Replace `/compact` internals with `ContextCompressor`, then wire automatic
  trigger after tests are stable.

Verification target:

- [ ] Add/extend `tests/test_context_engine.py`.
- [ ] Add/extend `tests/test_context_compression.py`.

## v0.11: Routines, Cron, And Triggers

Status: partial; trigger/workflow depth missing.

- [x] Routine config model exists.
- [x] Routine persistence store exists.
- [x] Routine runner exists.
- [x] Routine scheduler skeleton exists.
- [x] Cron bridge exists.
- [x] `/routines` management command exists.
- [ ] Add script pre-processing step.
- [ ] Run approved script before agent turn.
- [ ] Capture stdout as context.
- [ ] Capture stderr as diagnostics.
- [ ] Bound script runtime.
- [ ] Bound script output size.
- [ ] Apply tool/approval policy to script routines.
- [ ] Add multi-skill workflow model.
- [ ] Add routine step list.
- [ ] Add step-level allowed tools.
- [ ] Add step-level approval policy.
- [ ] Add step-level timeout.
- [ ] Add webhook trigger type.
- [ ] Add API trigger type.
- [ ] Add trigger auth.
- [ ] Add trigger replay/idempotency key.
- [ ] Add quiet hours enforcement tests.
- [ ] Add delivery policy tests.
- [ ] Add destination channel policy tests.
- [ ] Add routine failure diagnostics.
- [ ] Add routine history/log inspection.
- [ ] Add docs for recurring workflows.

First PR boundary:

- [ ] Script preprocessing for routines with bounded stdout context.

Verification target:

- [ ] Add/extend `tests/test_routines_*.py`.
- [ ] Existing cron/proactive tests still pass.

## v0.12: Toolsets, MCP, And Execution Backends

Status: partial; streamable HTTP MCP and Docker missing.

- [x] `ToolsetResolver` exists.
- [x] Per-message tool filtering exists in `AgentLoop`.
- [x] MCP stdio transport exists.
- [x] MCP SSE transport exists.
- [x] Dynamic MCP tool registration exists.
- [x] Tool grouping by capability exists.
- [x] Shared runner first slice exists.
- [x] Local execution backend exists.
- [ ] Add streamable HTTP MCP transport.
- [ ] Add streamable HTTP config schema.
- [ ] Add streamable HTTP auth config.
- [ ] Add streamable HTTP timeout tests.
- [ ] Add streamable HTTP retry tests.
- [ ] Add MCP OAuth only when needed.
- [ ] Add MCP path traversal checks where file paths are accepted.
- [ ] Add MCP tool schema edge-case tests.
- [ ] Add subagent status events.
- [ ] Add subagent cancellation events.
- [ ] Add subagent completion summaries routed to origin channel.
- [ ] Add subagent artifact summary model.
- [ ] Add Docker execution backend.
- [ ] Add Docker availability check.
- [ ] Add Docker image config.
- [ ] Add Docker workspace mount policy.
- [ ] Add Docker allowed-path policy.
- [ ] Add Docker network policy.
- [ ] Add Docker timeout policy.
- [ ] Add Docker cleanup policy.
- [ ] Add Docker tests with skip when Docker unavailable.
- [ ] Add SSH/VPS backend later only after Docker/local are stable.
- [ ] Keep Modal/Daytona/Singularity out of core.
- [ ] Update MCP docs.
- [ ] Update execution backend docs.

First PR boundary:

- [ ] Streamable HTTP MCP transport with focused tests.

Verification target:

- [ ] `pytest -q tests/test_toolsets.py tests/test_execution_backend.py`
- [ ] Add/extend `tests/test_mcp_*.py`.

## v0.13: Insights, Packaging, And Public Trust

Status: completed slice; keep current as new features ship.

- [x] `docs/release-notes/checklist.md` exists.
- [x] `docs/security.md` documents current sandbox, policy, and secrets surfaces.
- [x] `docs/install-matrix.md` exists.
- [x] `InsightsEngine` exists.
- [x] Provider stats exist.
- [x] Failed-call parsing exists.
- [x] Skill usage exists.
- [x] Guest enforcement exists.
- [x] Tests cover provider stats.
- [x] Tests cover failed-call parsing.
- [x] Tests cover skill usage formatting.
- [x] Tests cover guest enforcement.
- [x] Tests cover default profile setup.
- [ ] Keep insights updated when MemoryManager lands.
- [ ] Keep insights updated when background reviewer lands.
- [ ] Keep insights updated when WebSocket/API lands.
- [ ] Keep insights updated when routines grow trigger/workflow history.
- [ ] Keep security docs updated when approval persistence lands.
- [ ] Keep security docs updated when Docker backend lands.
- [ ] Keep install docs updated when Web UI/API service lands.
- [ ] Add third-party notices if code/assets are copied from references.
- [ ] Add release notes for each shipped slice.
- [ ] Keep `mkdocs build --strict` clean.

Verification target:

- [ ] `pytest -q tests/test_insights.py tests/test_guest_enforcement.py tests/test_security_audit.py`
- [ ] `mkdocs build --strict`

## Cross-Cutting Done Definition

Every task is not done until:

- [ ] Code exists in the expected module path.
- [ ] Tests cover happy path.
- [ ] Tests cover at least one failure path.
- [ ] Owner-facing command/API behavior is documented if exposed.
- [ ] Security/approval behavior is documented if risky.
- [ ] Roadmap phase file is updated.
- [ ] This TODO is updated.
- [ ] `CHANGELOG.md` is updated.
- [ ] `ruff check g_agent tests --select F` passes.
- [ ] `python -m compileall -q g_agent` passes.
- [ ] Relevant focused tests pass.
- [ ] Full `pytest -q` passes before commit unless the owner explicitly asks for
  a partial checkpoint.
- [ ] `mkdocs build --strict` passes for docs changes.

## Immediate Queue

### Next Commit

- [x] v0.4 channel contracts:
  - [x] add channel capability types
  - [x] add media envelope types
  - [x] add delivery result/error types
  - [x] add tests for shared contracts
  - [x] update channel roadmap docs

### After That

- [x] v0.4 channel-specific hardening:
  - [x] wire delivery result/error contracts into send paths
  - [x] expose channel capabilities through diagnostics/status
  - [x] WhatsApp diagnostics
  - [x] Telegram formatting safety
  - [x] Discord session/thread mapping

### Then

- [ ] v0.7 MemoryManager first PR:
  - [ ] provider interface
  - [ ] builtin adapter
  - [ ] manager prefetch
  - [ ] memory context fencing

### Then

- [ ] v0.8/v0.9 background reviewer:
  - [ ] reviewer skeleton
  - [ ] candidate generation
  - [ ] dedupe/rejection suppression
  - [ ] skill proposal path

### Then

- [ ] v0.10 compression integration.
- [ ] v0.11 routine script preprocessing.
- [ ] v0.12 streamable HTTP MCP.
- [ ] v0.5 minimal product API.
