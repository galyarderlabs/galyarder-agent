"""Memory manager orchestration."""

from pathlib import Path

from loguru import logger

from g_agent.memory.builtin import BuiltinMemoryProvider
from g_agent.memory.context import fence_memory_context
from g_agent.memory.types import MemoryProvider


class MemoryManager:
    """Single integration point for memory providers."""

    def __init__(
        self,
        workspace: Path,
        providers: list[MemoryProvider] | None = None,
    ):
        self.workspace = workspace
        self.providers: list[MemoryProvider] = providers or [BuiltinMemoryProvider(workspace)]
        self._validate_provider_set()

    def _validate_provider_set(self) -> None:
        external = [provider for provider in self.providers if not provider.builtin]
        if len(external) > 1:
            names = ", ".join(provider.name for provider in external)
            raise ValueError(f"Only one external memory provider can be active: {names}")

    def prefetch_all(
        self,
        *,
        query: str | None = None,
        session_id: str = "",
        include_full: bool = True,
    ) -> str:
        """Fetch fenced memory context from all active providers."""
        blocks: list[str] = []
        for provider in self.providers:
            try:
                context = provider.prefetch(
                    query=query,
                    session_id=session_id,
                    include_full=include_full,
                )
            except Exception as exc:
                logger.warning("Memory provider {} prefetch failed: {}", provider.name, exc)
                continue

            fenced = fence_memory_context(provider.name, context)
            if fenced:
                blocks.append(fenced)
        return "\n\n".join(blocks)

    def sync_turn_all(
        self,
        *,
        user_content: str,
        assistant_content: str,
        session_id: str = "",
    ) -> None:
        """Run post-turn memory sync hooks for all providers."""
        for provider in self.providers:
            try:
                provider.sync_turn(
                    user_content=user_content,
                    assistant_content=assistant_content,
                    session_id=session_id,
                )
            except Exception as exc:
                logger.warning("Memory provider {} sync failed: {}", provider.name, exc)
