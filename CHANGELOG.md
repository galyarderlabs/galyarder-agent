# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- Configurable `proxy_provider` in `RoutingConfig` (default: `vllm` for backward compatibility).
- Generic `proxy` provider in `ProvidersConfig` for CLIProxyAPI and similar OpenAI-compatible proxies.
- Provider-agnostic proxy routing via `_resolve_proxy_route()` helper.
- Tests for backward-compatible vLLM proxy, generic proxy provider, and explicit `proxy/` prefix in auto mode.
- `g-agent help`, `g-agent version`, and `g-agent login` command aliases for better CLI discoverability.
- Auto-generated command reference page at `docs/cli-commands.md` via `backend/agent/scripts/generate_cli_docs.py`.
- Local pre-commit guard (`.githooks/pre-commit`) and CI/release checks to keep CLI docs synchronized.
- CLI error-style guideline doc at `docs/cli-error-style.md`.
- CLI command-surface regression tests for help/version/login aliases and no-subcommand group help behavior.
- Embeddable `Agent` lifecycle API (`close`, `aclose`, async context manager) plus safe closed-state guards.
- `g-agent plugins list` and `g-agent plugins doctor` commands for plugin policy diagnostics.
- Channel manager supervisor restart loop for long-running channel crash recovery.
- Outbound dispatch retries with capped backoff for transient channel send failures.
- Compact metrics alert summaries now surfaced in `status`/`doctor`, with alert gauges exported in Prometheus output.

### Changed
- `resolve_model_route()` now uses `proxy_provider` instead of hardcoding `vllm`.
- `_resolve_direct_provider()` dynamically skips configured proxy providers.
- README routing docs updated with CLIProxyAPI, vLLM, and direct provider examples.
- Default model updated to `claude-opus-4-6-thinking` for proxy-based setups.
- Group commands (`channels`, `google`, `cron`, `policy`) now show help when called without subcommand.

### Fixed
- Deprecated `opus 4.5` model aliases are now migrated to `claude-opus-4-6-thinking` during config load.
- `channels login` now performs bridge preflight checks and reports clearer causes/fixes for port bind failures.
- Missing API key failures now include provider-aware remediation hints.
- `channels login` now auto-rebuilds local bridge assets when bundled bridge source changes, preventing stale bridge runtime mismatches.
- `channels login` now passes bridge runtime env (`BRIDGE_PORT`, `AUTH_DIR`) from config/data-dir so npm bridge start matches configured URL and auth storage path.
- `channels login --restart-existing` can now stop stale bridge listeners on configured port before starting a fresh QR login.
- `channels login --restart-existing --force-kill` now supports SIGKILL escalation when stale listeners ignore SIGTERM.

## [0.1.4] - 2026-02-09

### Added
- Model routing system with configurable modes (`auto`/`proxy`/`direct`).
- Deterministic model failover chain via `routing.fallbackModels` config.
- `LLMRoute` and `RoutingConfig` schema classes for structured routing resolution.
- `_chat_with_model_failover()` method for automatic retry with backup models.
- Error classification for failover triggers (rate limit, timeout, auth, 503, etc.).
- Runtime event logging for model fallback transitions.
- 166 lines of model routing unit tests.

### Changed
- Refactored provider resolution logic into `resolve_model_route()` method.
- CLI commands (`gateway`, `agent`, `digest`, `status`) now use unified routing.
- `g-agent status` displays routing mode, provider, and fallback chain info.

### Fixed
- Forward reference error (`F821 Undefined name RoutingConfig`) by reordering class definitions.

## [0.1.3.post5] - 2026-02-09

### Fixed
- CodeQL `py/bad-tag-filter` alert by replacing regex HTML stripping with parser-based extraction in web tools.
- Code scanning `actions/missing-workflow-permissions` alerts by declaring read-only workflow permissions.
- Required checks now run for Dependabot PRs (no longer skipped), unblocking protected-branch merges.

### Changed
- Merged dependency update PRs for GitHub Actions and backend bridge npm packages.

## [0.1.3.post4] - 2026-02-08

### Added
- OpenClaw-delta runtime checkpoints with persisted task state and resume flow.
- Proactive engine primitives (calendar reminders, quiet-hours handling, state dedupe).
- Workflow pack orchestration (`daily_brief`, `meeting_prep`, `inbox_zero_batch`) with multimodal flags.
- Multimodal outbound support upgrades (voice/image/sticker generation pathways).
- Guest safety presets (`personal_full`, `guest_limited`, `guest_readonly`).
- Observability metrics store and runtime snapshot plumbing.
- Focused backend test coverage for runtime, memory, proactive, workflow, and policy behavior.
- Roadmap tracking doc at `docs/roadmap/openclaw-delta.md`.

### Changed
- Rebrand consistency updates across docs and channel surfaces for `g-agent`.
- Reliability hardening across tool and channel error paths.

### Fixed
- CI memory tests now tolerate non-JSON header lines in `FACTS.md`.
- CI memory tests now scope assertions to targeted `timezone` fact records.
- Signature mismatch class of static warnings reduced via tool interface tightening.
