# AGENTS.md — Coding Agent Guidelines

> For AI coding agents operating in this repository. Not for the runtime agent (see `backend/agent/workspace/AGENTS.md`).

## Repository Layout

- `backend/agent/` — Python runtime (`g_agent` package). **Most code lives here.**
- `backend/agent/bridge/` — Node.js/TypeScript WhatsApp bridge (`package-lock.json` → use `npm`). Rarely touched.
- `docs/` — MkDocs documentation site source.
- `deploy/` — Install/uninstall scripts per OS (Arch, Debian, macOS, Windows).
- `.githooks/` — Local pre-commit and pre-push guards.

Package root: `backend/agent/g_agent/` with submodules: `agent/`, `bus/`, `channels/`, `cli/`, `config/`, `cron/`, `heartbeat/`, `observability/`, `plugins/`, `proactive/`, `providers/`, `security/`, `session/`, `skills/`, `utils/`.

Tests: `backend/agent/tests/` (flat, no `conftest.py`). Dep manager: `uv` (`uv.lock`), but CI uses `pip install -e ".[dev]"`.

## Build / Lint / Test Commands

All commands run from `backend/agent/`:

```bash
pip install -e ".[dev]"                    # Install editable + dev deps
ruff check g_agent tests --select F        # Lint (fatal only — matches CI)
python -m compileall -q g_agent            # Compile check
pytest -q                                  # All tests
pytest tests/test_security_audit.py -q     # One file
pytest tests/test_security_audit.py::test_security_audit_secure_baseline -q  # One test
python scripts/generate_cli_docs.py        # CLI docs sync (required before committing CLI changes)
```

Docs (from repo root): `pip install -r docs/requirements.txt && mkdocs build --strict`

## CI Pipeline (`.github/workflows/ci.yml`)

Triggers: push to `main`, all PRs, manual dispatch. Python **3.11**. Steps:

1. `pip install -e ".[dev]"` → 2. CLI docs sync check → 3. `compileall` → 4. `ruff check --select F` → 5. `pytest -q`

Docs job: `mkdocs build --strict` (separate).

## Git Hooks

Enable: `git config core.hooksPath .githooks`

- **pre-commit**: Auto-regenerates CLI docs if CLI files are staged.
- **pre-push** (main only): compile + ruff + tests. Mode via `G_AGENT_PRE_PUSH_MODE`: `quick` (default), `full`, `changed`.

## Ruff (`pyproject.toml`)

`line-length = 100`, `target-version = "py311"`, `select = ["E", "F", "I", "N", "W"]`, `ignore = ["E501", "N803"]`

## Code Style

### Imports

Order: stdlib → third-party → local (`g_agent.*`). Enforced by ruff `I`. Use `if TYPE_CHECKING:` for heavy/circular imports.

```python
"""Module docstring."""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from g_agent.agent.context import ContextBuilder

if TYPE_CHECKING:
    from g_agent.config.schema import ExecToolConfig
```

### Naming

| Element | Convention | Example |
|---------|-----------|---------|
| Functions | `snake_case` | `get_data_path` |
| Private helpers | `_snake_case` | `_make_check` |
| Classes | `PascalCase` | `AgentLoop`, `ToolRegistry` |
| Constants | `UPPER_SNAKE` | `PRIMARY_DATA_DIR` |
| Tests | `test_<feature>_<scenario>` | `test_auto_mode_prefers_proxy` |

### Type Annotations

Required on all signatures. Modern 3.11+ syntax only — **never** `Optional[X]`, `List[X]`, `Dict[K, V]`:

```python
def get(self, name: str) -> Tool | None: ...
def get_definitions(self) -> list[dict[str, Any]]: ...
async def chat(self, messages: list[dict[str, Any]], model: str | None = None) -> LLMResponse: ...
```

### Data Modeling

- **Pydantic `BaseModel`** for config schemas (`config/schema.py`).
- **`@dataclass`** for simple data carriers (`providers/base.py`, `bus/events.py`).

### Docstrings

Module-level one-liner required. Classes and non-trivial functions: Google-style with `Args:`/`Returns:`. Short helpers: one-line docstring.

### Logging

`loguru` exclusively — **never** `logging` stdlib. Use `{}` placeholders: `logger.info("Starting on port {}", port)`

### Error Handling

- Tools return error strings: `return f"Error: Tool '{name}' not found"` (no raising).
- Enrich exceptions with context before re-raising.
- No silent `try/except: pass`.

## Testing Conventions

- **pytest + pytest-asyncio** (`asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed).
- **No `conftest.py`** — each test file is self-contained.
- **Fixtures**: `tests/fixtures/` for markdown templates.
- **Mocking**: Prefer subclassing (`LLMProvider`, `Tool`, `BaseChannel`) over `unittest.mock`. Use `monkeypatch` for env vars, `tmp_path` for filesystem, `SimpleNamespace` for config stubs.
- **Assertions**: Standard `assert`. Collections: `assert any("msg" in e for e in errors)`.

```python
def test_security_audit_secure_baseline(tmp_path: Path):
    config = _build_config(restrict_to_workspace=True, ...)
    result = run_security_audit(config, data_dir=tmp_path / ".g-agent-secure")
    assert result["overall"] == "pass"
```

## Key Architecture

- **Message bus**: Channels → `InboundMessage` → bus → `AgentLoop` → `OutboundMessage` → dispatch.
- **Tool registry**: `ToolRegistry.register()`, OpenAI-format schemas via `to_schema()`. Per-message context via `set_context(channel, chat_id)`.
- **Providers**: All LLM calls through `LLMProvider` ABC (`providers/base.py`). LiteLLM is primary.
- **Visual/Selfie**: `SelfieTool` (`agent/tools/selfie.py`) generates selfies via text-to-image providers. Feature-gated by `visual.enabled`. Lazy-imported in `_register_default_tools()` to avoid loading when disabled. Identity anchor: LoRA trigger word (preferred, ~90-95% consistency) or vision-extracted `physicalDescription` (legacy, ~70-80%).
- **Config**: Single Pydantic `Config` from `~/.g-agent/config.json`. Override via `G_AGENT_DATA_DIR`. Sections: `agents`, `channels`, `providers`, `tools`, `visual`, `google`, `integrations`.

## Things to Avoid

- `typing.Optional`, `typing.List`, `typing.Dict` → use `X | None`, `list`, `dict`.
- `logging` stdlib → use `loguru`.
- Adding dependencies without strong justification (check `pyproject.toml`).
- Editing `workspace/AGENTS.md` (runtime agent instructions, not dev guidelines).
- Committing secrets/tokens. Config lives in `~/.g-agent/config.json` at runtime.
- Mixing package managers. Bridge = `npm`. Python = `uv`/`pip`.
