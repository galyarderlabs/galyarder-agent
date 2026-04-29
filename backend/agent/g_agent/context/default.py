"""Default context engine for G-Agent."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from g_agent.agent.context import ContextBuilder
from g_agent.context.engine import ContextEngine


class DefaultContextEngine(ContextEngine):
    """
    Default context engine that uses ContextBuilder for assembly.
    Currently does minimal compression (truncation by message count).
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.builder = ContextBuilder(workspace)

    @property
    def name(self) -> str:
        return "default"

    def build_system_prompt(
        self,
        skill_names: Optional[List[str]] = None,
        current_message: Optional[str] = None,
        tool_names: Optional[List[str]] = None,
        profile: Optional[Any] = None,
    ) -> str:
        return self.builder.build_system_prompt(
            skill_names=skill_names,
            current_message=current_message,
            tool_names=tool_names,
            profile=profile,
        )

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
        return await self.builder.build_messages(
            history=history,
            current_message=current_message,
            skill_names=skill_names,
            media=media,
            metadata=metadata,
            channel=channel,
            chat_id=chat_id,
            tool_names=tool_names,
            profile=profile,
            llm_provider=llm_provider,
        )

    def should_compress(self, messages: List[Dict[str, Any]]) -> bool:
        # Default behavior: compress if history > 50 messages
        # (excluding system prompt and cold-start priming)
        return len(messages) > 60

    def compress(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Simple truncation for now.
        In Milestone v0.10.4 we will replace this with smart summarization.
        """
        if len(messages) <= 20:
            return messages

        # Keep system prompt (index 0)
        system = messages[0]
        # Keep last 10 turns (20 messages if user/assistant pairs)
        tail = messages[-20:]

        return [system] + tail
