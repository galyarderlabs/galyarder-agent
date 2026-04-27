"""Tool for searching conversation history using SQLite FTS5."""

import time
from typing import Any

from g_agent.agent.tools.base import Tool
from g_agent.session.manager import SessionManager


class SessionSearchTool(Tool):
    """Search through past conversation history."""

    name = "session_search"
    description = (
        "Search through past conversation history across all channels. "
        "Find old decisions, shared links, paths, and topics discussed in previous sessions."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Text to search for in past messages. Leave empty to see recent sessions.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return",
                "default": 10,
                "minimum": 1,
                "maximum": 50,
            },
            "channel": {
                "type": "string",
                "description": "Optional channel filter, such as telegram, whatsapp, discord, or cli.",
            },
            "exclude_session_key": {
                "type": "string",
                "description": "Optional session key to exclude from recall results.",
            },
        },
    }

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    async def execute(
        self,
        query: str | None = None,
        limit: int = 10,
        channel: str | None = None,
        exclude_session_key: str | None = None,
        **kwargs: Any,
    ) -> str:
        store = self.session_manager.sqlite_store
        limit = max(1, min(limit, 50))

        if not query or not query.strip():
            # List recent sessions
            sessions = store.list_sessions(limit=limit)
            if not sessions:
                return "No past sessions found."

            lines = ["Recent sessions:"]
            for s in sessions:
                lines.append(f"- [{s['channel']}] {s['key']} (updated: {s['updated_at']})")
            return "\n".join(lines)

        # Full-text search
        results = store.search_messages(
            query,
            limit=limit,
            channel=channel,
            exclude_session_key=exclude_session_key,
        )
        if not results:
            return f"No results found for query: '{query}'"

        grouped: dict[str, list[dict[str, Any]]] = {}
        for result in results:
            grouped.setdefault(str(result["session_key"]), []).append(result)

        lines = [f"Search results for '{query}':"]
        for session_key, session_results in grouped.items():
            first = session_results[0]
            channel_name = first.get("channel") or "unknown"
            ts = first.get("created_at")
            if isinstance(ts, int | float):
                timestamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(float(ts)))
            else:
                timestamp = "unknown time"
            lines.append(f"- [{channel_name}] {session_key} ({timestamp})")
            for result in session_results[:3]:
                content = " ".join(str(result.get("content") or "").split())
                preview = content[:220] + ("..." if len(content) > 220 else "")
                lines.append(f"  {str(result.get('role') or 'message').upper()}: {preview}")

        return "\n".join(lines)
