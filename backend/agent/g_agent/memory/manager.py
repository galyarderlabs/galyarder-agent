import asyncio
from pathlib import Path
from typing import Any

from loguru import logger
from g_agent.memory.types import MemoryFragment, MemoryProvider
from g_agent.memory.builtin import BuiltinMemoryProvider


class MemoryManager:
    """Manages multiple memory providers and coordinates recall/sync."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.providers: dict[str, MemoryProvider] = {}
        
        # Register builtin provider by default
        self.register_provider(BuiltinMemoryProvider(workspace))

    def register_provider(self, provider: MemoryProvider) -> None:
        """Register a new memory provider."""
        if provider.name in self.providers:
            logger.warning(f"Memory provider {provider.name} already registered, overwriting.")
        self.providers[provider.name] = provider
        logger.info(f"Memory provider {provider.name} registered.")

    async def prefetch(self, query: str, session_id: str = "") -> list[MemoryFragment]:
        """Fetch relevant fragments from all registered providers in parallel."""
        from time import perf_counter
        start = perf_counter()
        
        tasks = [p.prefetch(query, session_id) for p in self.providers.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_fragments: list[MemoryFragment] = []
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                provider_name = list(self.providers.keys())[i]
                logger.error(f"Memory provider {provider_name} prefetch failed: {res}")
                continue
            all_fragments.extend(res)
            
        # Sort by relevance
        all_fragments.sort(key=lambda f: f.relevance, reverse=True)
        
        duration = perf_counter() - start
        logger.debug(f"Memory prefetch recalled {len(all_fragments)} fragments in {duration:.3f}s")
        
        return all_fragments

    async def sync_turn(self, user_content: str, assistant_content: str, session_id: str = "") -> None:
        """Sync a turn to all providers in parallel."""
        tasks = [p.sync_turn(user_content, assistant_content, session_id) for p in self.providers.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

    def get_system_prompt_blocks(self) -> list[str]:
        """Collect prompt blocks from all providers."""
        return [p.system_prompt_block() for p in self.providers.values()]

    def get_all_tool_schemas(self) -> list[dict[str, Any]]:
        """Collect all memory-specific tool schemas."""
        all_schemas = []
        for p in self.providers.values():
            all_schemas.extend(p.get_tool_schemas())
        return all_schemas

    async def handle_tool_call(self, name: str, args: dict[str, Any], session_id: str = "") -> Any:
        """Route tool call to the provider that owns it."""
        for p in self.providers.values():
            try:
                # This is a bit inefficient if multiple providers have same tool names,
                # but currently only one provider will own a specific memory tool.
                return await p.handle_tool_call(name, args, session_id)
            except NotImplementedError:
                continue
        raise ValueError(f"No memory provider found for tool: {name}")
