"""Base LLM provider interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCallRequest:
    """A tool call request from the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Response from an LLM provider."""

    content: str | None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: dict[str, int] = field(default_factory=dict)
    reasoning_content: str | None = None  # Kimi, DeepSeek-R1 etc.
    thinking_blocks: list[dict[str, Any]] = field(default_factory=list)  # Anthropic thinking

    @property
    def has_tool_calls(self) -> bool:
        """Check if response contains tool calls."""
        return len(self.tool_calls) > 0


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    Implementations should handle the specifics of each provider's API
    while maintaining a consistent interface.
    """

    def __init__(self, api_key: str | None = None, api_base: str | None = None):
        self.api_key = api_key
        self.api_base = api_base

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        timeout: float | None = 120.0,
        reasoning_effort: str | None = None,
        thinking_blocks: bool = False,
    ) -> LLMResponse:
        """
        Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions.
            model: Model identifier (provider-specific).
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.
            timeout: Maximum time to wait for a response in seconds.
            reasoning_effort: Effort for reasoning models (e.g. low, medium, high).
            thinking_blocks: Enable Anthropic extended thinking blocks format.

        Returns:
            LLMResponse with content and/or tool calls.
        """
        pass

    @abstractmethod
    def get_default_model(self) -> str:
        """Get the default model for this provider."""
        pass

    @staticmethod
    def _sanitize_empty_content(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Fix provider 400 errors by replacing None/empty content with a single space."""
        for msg in messages:
            if "content" not in msg or msg["content"] is None:
                msg["content"] = " "
            elif isinstance(msg["content"], str) and not msg["content"].strip():
                msg["content"] = " "
        return messages

    @staticmethod
    def _sanitize_request_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Final sanitization pass before sending to the provider."""
        sanitized = []
        for msg in messages:
            clean_msg = msg.copy()
            # Remove any internal kwargs that shouldn't go to LLM
            clean_msg.pop("cache_control", None)
            sanitized.append(clean_msg)

        return LLMProvider._sanitize_empty_content(sanitized)
