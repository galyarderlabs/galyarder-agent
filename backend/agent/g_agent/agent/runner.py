"""Shared execution loop for tool-using agents."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from g_agent.agent.tools.registry import ToolRegistry
from g_agent.providers.base import LLMProvider


@dataclass(slots=True)
class AgentRunSpec:
    """Configuration for a single agent execution."""

    initial_messages: list[dict[str, Any]]
    tools: ToolRegistry
    model: str
    max_iterations: int
    temperature: float | None = None
    max_tokens: int | None = None


@dataclass(slots=True)
class AgentRunResult:
    """Outcome of a shared agent execution."""

    final_content: str | None
    messages: list[dict[str, Any]]
    tools_used: list[str] = field(default_factory=list)
    stop_reason: str = "completed"
    error: str | None = None


class AgentRunner:
    """Run a tool-capable LLM loop without product-layer concerns."""

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def run(self, spec: AgentRunSpec) -> AgentRunResult:
        """Execute the core LLM-tool iteration loop."""
        messages = list(spec.initial_messages)
        tools_used = []
        iteration = 0
        final_content = None
        error_msg = None
        stop_reason = "completed"

        while iteration < spec.max_iterations:
            iteration += 1

            try:
                response = await self.provider.chat(
                    messages=messages,
                    tools=spec.tools.get_definitions(),
                    model=spec.model,
                    temperature=spec.temperature,
                    max_tokens=spec.max_tokens,
                )
            except Exception as e:
                logger.error(f"AgentRunner LLM error: {e}")
                error_msg = str(e)
                stop_reason = "error"
                break

            if not response.has_tool_calls:
                final_content = response.content
                break

            # Add assistant message with tool calls
            tool_call_dicts = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in response.tool_calls
            ]

            messages.append(
                {
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": tool_call_dicts,
                }
            )

            # Execute tools
            for tool_call in response.tool_calls:
                tools_used.append(tool_call.name)
                try:
                    result = await spec.tools.execute(tool_call.name, tool_call.arguments)
                except Exception as e:
                    result = f"Error executing tool {tool_call.name}: {e}"

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.name,
                        "content": str(result),
                    }
                )
        else:
            stop_reason = "max_iterations"
            final_content = "Task reached maximum iterations without completing."

        return AgentRunResult(
            final_content=final_content,
            messages=messages,
            tools_used=tools_used,
            stop_reason=stop_reason,
            error=error_msg,
        )
