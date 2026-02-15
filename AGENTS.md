# AGENTS.md — Coding Agent Guidelines

> For AI coding agents operating in this repository. Not for the runtime agent (see `backend/agent/workspace/AGENTS.md`).

## Repository Layout

Monorepo with these areas:

- `backend/agent/` — Python runtime (`g_agent` package). **This is where most code lives.**
- `backend/agent/bridge/` — Node.js/TypeScript WhatsApp bridge (`package-lock.json` → use `npm`). Agents should rarely touch this.
- `docs/` — MkDocs documentation site source.
- `deploy/` — Install/uninstall scripts per OS (Arch, Debian, macOS, Windows).
- `.githooks/` — Local pre-commit and pre-push guards.

The Python package root is `backend/agent/g_agent/` with submodules: `agent/`, `bus/`, `channels/`, `cli/`, `config/`, `cron/`, `heartbeat/`, `observability/`, `plugins/`, `proactive/`, `providers/`, `security/`, `session/`, `skills/`, `utils/`.

Tests live in `backend/agent/tests/` (flat directory, no `conftest.py`). Lockfile is `uv.lock` — the project uses `uv` for dependency management, but `pip install -e ".[dev]"` works and is what CI uses.

## Build / Lint / Test Commands

All backend commands run from `backend/agent/`:

```bash
# Install (editable + dev deps)
pip install -e ".[dev]"

# Lint (fatal errors only — matches CI)
ruff check g_agent tests --select F

# Compile check
python -m compileall -q g_agent

# Run ALL tests
pytest -q

# Run one test file
pytest tests/test_security_audit.py -q

# Run one test function
pytest tests/test_security_audit.py::test_security_audit_secure_baseline -q

# CLI docs sync (required before committing CLI changes)
python scripts/generate_cli_docs.py
```

Docs (run from repo root):

```bash
pip install -r docs/requirements.txt
mkdocs build --strict
```

## CI Pipeline (`.github/workflows/ci.yml`)

Triggers: push to `main`, all PRs, manual dispatch. Python **3.11**.

Steps in order:
1. `pip install -e ".[dev]"`
2. `python scripts/generate_cli_docs.py` + verify `docs/cli-commands.md` unchanged
3. `python -m compileall -q g_agent`
4. `ruff check g_agent tests --select F`
5. `pytest -q`

Docs job runs `mkdocs build --strict` separately.

## Git Hooks (`.githooks/`)

Enable: `git config core.hooksPath .githooks`

- **pre-commit**: If CLI files (`g_agent/cli/`, `scripts/generate_cli_docs.py`, `docs/cli-commands.md`) are staged, regenerates CLI docs and verifies sync.
- **pre-push** (main only): Runs compile + ruff + tests. Modes via `G_AGENT_PRE_PUSH_MODE`: `quick` (default, subset of tests), `full` (all tests), `changed` (only modified files).

## Ruff Configuration

From `pyproject.toml`:
- `line-length = 100`
- `target-version = "py311"`
- `select = ["E", "F", "I", "N", "W"]`
- `ignore = ["E501", "N803"]`

## Code Style

### Imports

Order: stdlib → third-party → local (`g_agent.*`). Enforced by ruff `I` rules.

```python
"""Module docstring."""

from __future__ import annotations          # used in some modules

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger                    # standard logger everywhere

from g_agent.agent.context import ContextBuilder
from g_agent.bus.events import InboundMessage

if TYPE_CHECKING:                            # heavy/circular imports go here
    from g_agent.config.schema import ExecToolConfig
```

### Naming

| Element | Convention | Examples |
|---------|-----------|----------|
| Functions | `snake_case` | `get_data_path`, `run_security_audit` |
| Private helpers | `_snake_case` | `_make_check`, `_format_mode` |
| Classes | `PascalCase` | `AgentLoop`, `BaseChannel`, `ToolRegistry` |
| Constants | `UPPER_SNAKE` | `PRIMARY_DATA_DIR`, `DATA_DIR_ENV_VAR` |
| Test functions | `test_<feature>_<scenario>` | `test_auto_mode_prefers_proxy_for_unprefixed_model` |

### Type Annotations

Required on all function signatures (params + return). Use modern Python 3.11+ syntax:

```python
def get(self, name: str) -> Tool | None:        # not Optional[Tool]
    ...

def get_definitions(self) -> list[dict[str, Any]]:  # lowercase generics
    ...

async def chat(self, messages: list[dict[str, Any]], model: str | None = None) -> LLMResponse:
    ...
```

Do **not** use `Optional[X]`, `List[X]`, `Dict[K, V]` — use `X | None`, `list[x]`, `dict[k, v]`.

### Data Modeling

- **Pydantic `BaseModel`** for configuration schemas (see `config/schema.py`):
  ```python
  class TelegramConfig(BaseModel):
      enabled: bool = False
      token: str = ""
      allow_from: list[str] = Field(default_factory=list)
  ```

- **`@dataclass`** for simple data carriers (see `providers/base.py`, `bus/events.py`):
  ```python
  @dataclass
  class ToolCallRequest:
      id: str
      name: str
      arguments: dict[str, Any]
  ```

### Docstrings

Module-level one-liner required. Classes and non-trivial functions use Google-style:

```python
"""Security baseline audit routines for g-agent profiles."""

class BaseChannel(ABC):
    """
    Abstract base class for chat channel implementations.

    Each channel (Telegram, Discord, etc.) should implement this interface
    to integrate with the Galyarder Agent message bus.
    """

def get_workspace_path(self, workspace: str | None = None) -> Path:
    """
    Get the workspace path.

    Args:
        workspace: Optional workspace path. Defaults to <data-dir>/workspace.

    Returns:
        Expanded and ensured workspace path.
    """
```

Short helpers get one-line docstrings: `"""Ensure a directory exists, creating it if necessary."""`

### Logging

Use `loguru` exclusively — never `logging` stdlib:

```python
from loguru import logger

logger.info("Starting gateway on port {}", port)
logger.warning("Channel {} has empty allowlist", channel_name)
logger.error("Tool '{}' execution failed: {}", name, err)
```

### Error Handling

- Tool execution returns error strings instead of raising: `return f"Error: Tool '{name}' not found"`
- Enrich exceptions with context before re-raising.
- No silent `try/except: pass` blocks.

## Testing Conventions

- **Framework**: pytest + pytest-asyncio (`asyncio_mode = "auto"` — no `@pytest.mark.asyncio` needed).
- **No `conftest.py`** — each test file is self-contained.
- **Fixtures dir**: `tests/fixtures/` has markdown templates for memory/state tests.
- **Mocking**: Prefer subclassing base classes (`LLMProvider`, `Tool`, `BaseChannel`) over `unittest.mock`. Use `monkeypatch` for env vars and `tmp_path` for filesystem isolation. Use `SimpleNamespace` for lightweight config stubs.
- **Assertions**: Standard `assert`. For collections: `assert any("msg" in e for e in errors)`.

```python
def test_security_audit_secure_baseline(tmp_path: Path):
    data_dir = tmp_path / ".g-agent-secure"
    config = _build_config(restrict_to_workspace=True, ...)
    result = run_security_audit(config, data_dir=data_dir)
    assert result["overall"] == "pass"
```

## Key Architectural Patterns

- **Message bus**: Channels publish `InboundMessage` → bus → `AgentLoop` processes → `OutboundMessage` dispatched back.
- **Tool registry**: Tools register via `ToolRegistry.register()`, expose OpenAI-format schemas via `to_schema()`. Tools that need per-message routing context use `set_context(channel, chat_id)` (see `MessageTool`, `SelfieTool`).
- **Provider abstraction**: All LLM calls go through `LLMProvider` ABC (`providers/base.py`). LiteLLM is the primary implementation.
- **Visual identity**: `SelfieTool` (`agent/tools/selfie.py`) generates selfies via text-to-image providers. Config in `visual` section. Feature-gated by `visual.enabled`. Uses lazy import in `_register_default_tools()` to avoid loading when disabled.
- **Config**: Single `Config` Pydantic model loaded from `~/.g-agent/config.json`. Env override via `G_AGENT_DATA_DIR`. Key sections: `agents`, `channels`, `providers`, `tools`, `visual`, `google`, `integrations`.

## Things to Avoid

- Do not use `typing.Optional`, `typing.List`, `typing.Dict` — use `X | None`, `list`, `dict`.
- Do not use `logging` stdlib — use `loguru`.
- Do not add dependencies without strong justification (see `pyproject.toml`).
- Do not edit `workspace/AGENTS.md` — that file is runtime agent instructions, not dev guidelines.
- Do not commit secrets or tokens. Config lives in `~/.g-agent/config.json` at runtime.
- Do not mix package managers. Bridge uses `npm` (`package-lock.json`). Python uses `uv`/`pip`.
