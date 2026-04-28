"""Memory provider contracts."""

from typing import Any, Protocol


class MemoryProvider(Protocol):
    """Provider interface for memory recall and write lifecycle hooks."""

    name: str
    builtin: bool

    def system_prompt_block(self) -> str:
        """Return provider-specific system guidance."""
        ...

    def prefetch(
        self,
        *,
        query: str | None = None,
        session_id: str = "",
        include_full: bool = True,
    ) -> str:
        """Return memory context for a turn."""
        ...

    def sync_turn(
        self,
        *,
        user_content: str,
        assistant_content: str,
        session_id: str = "",
    ) -> None:
        """Sync a completed turn according to provider policy."""
        ...

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Return provider tool schemas, if any."""
        ...

    async def handle_tool_call(self, name: str, arguments: dict[str, Any]) -> str | None:
        """Handle a provider-owned tool call."""
        ...
