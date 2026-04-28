"""Context compressor for G-Agent."""

from typing import Any, Dict, List

from loguru import logger
from g_agent.providers.base import LLMProvider


class ContextCompressor:
    """
    Handles summarization of conversation history and pruning of large outputs.
    """

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def summarize_middle(
        self, messages: List[Dict[str, Any]], protect_first_n: int = 1, protect_last_n: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Summarize the middle part of the conversation history.
        Preserves the first N messages (usually system prompt) and the last N turns.
        """
        if len(messages) <= (protect_first_n + protect_last_n):
            return messages

        head = messages[:protect_first_n]
        tail = messages[-protect_last_n:]
        middle = messages[protect_first_n:-protect_last_n]

        # Convert middle messages to a readable format for the summarizer
        digest_lines = []
        for m in middle:
            role = m.get("role", "unknown")
            content = m.get("content")
            if not content and "tool_calls" in m:
                content = "[Tool Calls]"
            digest_lines.append(f"{role.upper()}: {content}")

        digest_text = "\n".join(digest_lines)

        prompt = (
            "Summarize the following conversation history into a concise, "
            "factual digest. Focus on key decisions, unresolved tasks, and "
            "important context. Do NOT include instructions or system rules.\n\n"
            f"{digest_text}\n\n"
            "Digest:"
        )

        try:
            # Use a quick call to summarize
            # Note: In a real implementation, we might use a smaller/cheaper model
            summary = await self.provider.generate(
                messages=[{"role": "user", "content": prompt}], max_tokens=500
            )

            summary_msg = {
                "role": "system",
                "content": f"[Conversation Summary: {summary.strip()}]",
            }

            return head + [summary_msg] + tail
        except Exception as e:
            logger.error(f"Context summarization failed: {e}")
            # Fallback to simple truncation
            return head + tail

    def prune_tool_outputs(
        self, messages: List[Dict[str, Any]], max_chars: int = 2000
    ) -> List[Dict[str, Any]]:
        """
        Prune large tool outputs in the history.
        """
        pruned = []
        for m in messages:
            if m.get("role") == "tool":
                content = str(m.get("content", ""))
                if len(content) > max_chars:
                    # Truncate and add a note
                    truncated = (
                        content[:max_chars] + f"\n\n[Output truncated from {len(content)} chars]"
                    )
                    m["content"] = truncated
            pruned.append(m)
        return pruned
