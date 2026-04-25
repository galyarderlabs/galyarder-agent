# Code Review

This project treats code review as a security and reliability gate.

## Scope

This checklist applies to:

- uncommitted local changes
- pull requests
- release branches

## Quick commands

Changed files:

```bash
git diff --name-only HEAD
```

Review the full diff:

```bash
git diff
```

Local validation (matches CI intent):

```bash
cd backend/agent
python -m compileall -q g_agent
ruff check g_agent tests --select F
pytest -q
```

## Severity model

- CRITICAL: exploitable security issue, credential exposure, authorization bypass
- HIGH: likely production incident, data loss/corruption risk, missing timeouts/retries on critical I/O
- MEDIUM: maintainability risk, edge-case correctness gaps, missing tests for new behavior
- LOW: style issues, minor refactors, readability

Commit/merge policy:

- Block commit/merge if any CRITICAL or HIGH issues remain.

## Security checks (CRITICAL)

Look for:

- hardcoded credentials (API keys, tokens, OAuth secrets, passwords)
- unsafe shell execution (command injection, missing allowlist)
- path traversal (joining untrusted paths, missing workspace restriction)
- injection risks (SQL/NoSQL/template injection)
- XSS risks (rendering unsanitized user content in HTML contexts)
- missing input validation for any user-controlled data
- insecure dependency changes (new deps, version bumps, lockfile changes)

Suggested spot checks:

```bash
# secrets-like strings in changes
git diff | rg -n "(api[_-]?key|token|secret|password|oauth|bearer|authorization)" -i

# new dependency introductions
git diff --name-only HEAD | rg -n "(pyproject\.toml|uv\.lock|package\.json|package-lock\.json)" || true
```

## Code quality checks (HIGH)

Look for:

- functions over ~50 lines without a strong reason
- files over ~800 lines without clear module boundaries
- nesting depth greater than 4 (prefer early returns / helpers)
- missing error handling on I/O (network, filesystem, subprocess)
- debug logging left behind (e.g. print/console.log)
- TODO/FIXME without an issue link or clear owner

## Best practices (MEDIUM)

Look for:

- mutation-heavy patterns where immutable updates are clearer/safer
- missing tests for new code paths or bug fixes
- missing docstrings for public APIs (modules, classes, public functions)
- accessibility regressions (semantic elements, focus states, labels) for UI changes

## Review output format

When writing a review, include for each issue:

- severity (CRITICAL/HIGH/MEDIUM/LOW)
- file path and line number(s)
- short description of the issue and why it matters
- suggested fix (concrete and minimal)

## Notes

- Prefer minimal, root-cause fixes over broad refactors.
- If a change affects CLI behavior, ensure CLI docs are regenerated via `backend/agent/scripts/generate_cli_docs.py`.
