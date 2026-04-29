from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class MemoryFragment:
    """A single piece of retrieved memory."""

    content: str
    source: str
    relevance: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


class MemoryProvider(ABC):
    """Interface for memory storage and retrieval backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique provider name."""
        pass

    @abstractmethod
    def system_prompt_block(self) -> str:
        """Instructions for the agent on how to use this memory."""
        pass

    @abstractmethod
    async def prefetch(self, query: str, session_id: str = "") -> list[MemoryFragment]:
        """Retrieve relevant fragments for a query."""
        pass

    @abstractmethod
    async def sync_turn(self, user_content: str, assistant_content: str, session_id: str = "") -> None:
        """Store new information from a conversation turn."""
        pass

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        """Return JSON schemas for tools provided by this memory backend."""
        return []

    async def handle_tool_call(self, name: str, args: dict[str, Any], session_id: str = "") -> Any:
        """Handle a memory-specific tool call."""
        raise NotImplementedError(f"Tool {name} not implemented by {self.name}")
