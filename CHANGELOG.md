# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- Placeholder section for upcoming changes.

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
