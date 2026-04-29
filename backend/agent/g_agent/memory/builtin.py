from typing import Any
from pathlib import Path

from g_agent.agent.memory import MemoryStore
from g_agent.memory.types import MemoryFragment, MemoryProvider


class BuiltinMemoryProvider(MemoryProvider):
    """Memory provider that uses the local filesystem (Markdown + SQLite fact index)."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.store = MemoryStore(workspace)

    @property
    def name(self) -> str:
        return "builtin"

    def system_prompt_block(self) -> str:
        return (
            "You have access to a local memory store. Facts you 'remember' are saved to MEMORY.md "
            "and indexed for semantic recall. Use the `remember` tool to store durable info about the user."
        )

    async def prefetch(self, query: str, session_id: str = "") -> list[MemoryFragment]:
        """Recall relevant fragments from the builtin store."""
        recalled = self.store.recall(query, max_items=15)
        return [
            MemoryFragment(
                content=item["text"],
                source=item["source"],
                relevance=float(item.get("score", 0)) / 1000.0, # Approximate normalization
                metadata={
                    "type": item.get("type"),
                    "confidence": item.get("confidence"),
                    "age_days": item.get("age_days"),
                }
            )
            for item in recalled
        ]

    async def sync_turn(self, user_content: str, assistant_content: str, session_id: str = "") -> None:
        """
        Record the turn in daily notes. 
        Note: Actual 'learning' of facts happens via tools or background reviewer.
        """
        # Append to today's notes
        self.store.append_today(f"User: {user_content}")
        self.store.append_today(f"Assistant: {assistant_content}")
