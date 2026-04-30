"""Abstract base class for pluggable context engines in G-Agent."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class ContextEngine(ABC):
    """Base class all context engines must implement."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for the engine."""

    @abstractmethod
    async def build_system_prompt(
        self,
        skill_names: Optional[List[str]] = None,
        current_message: Optional[str] = None,
        tool_names: Optional[List[str]] = None,
        profile: Optional[Any] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """Build the system prompt."""

    @abstractmethod
    async def build_messages(
        self,
        history: List[Dict[str, Any]],
        current_message: str,
        skill_names: Optional[List[str]] = None,
        media: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        channel: Optional[str] = None,
        chat_id: Optional[str] = None,
        tool_names: Optional[List[str]] = None,
        profile: Optional[Any] = None,
        llm_provider: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Build the complete message list for an LLM call."""

    @abstractmethod
    def should_compress(self, messages: List[Dict[str, Any]]) -> bool:
        """Check if context compression is needed."""

    @abstractmethod
    def compress(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Compress the conversation history."""

    def on_turn_end(self, messages: List[Dict[str, Any]], usage: Dict[str, Any]):
        """Callback after a turn is completed."""
        pass
