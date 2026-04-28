"""Builtin memory provider backed by the existing markdown MemoryStore."""

from pathlib import Path
from typing import Any

from g_agent.agent.memory import MemoryStore


class BuiltinMemoryProvider:
    """Adapter around the current markdown-backed MemoryStore."""

    name = "builtin"
    builtin = True

    def __init__(self, workspace: Path):
        self.store = MemoryStore(workspace)

    def system_prompt_block(self) -> str:
        """Return provider-specific system guidance."""
        return "Builtin memory is owner-readable local markdown plus a fact index."

    def prefetch(
        self,
        *,
        query: str | None = None,
        session_id: str = "",
        include_full: bool = True,
    ) -> str:
        """Return memory context for a turn."""
        return self.store.get_memory_context(query=query, include_full=include_full)

    def sync_turn(
        self,
        *,
        user_content: str,
        assistant_content: str,
        session_id: str = "",
    ) -> None:
        """No-op until owner-reviewed write cadence is wired."""
        return None

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """The legacy memory tools still own their schemas."""
        return []

    async def handle_tool_call(self, name: str, arguments: dict[str, Any]) -> str | None:
        """Legacy memory tools still handle tool calls."""
        return None
