"""
Toolsets Module

Provides a flexible system for defining and managing tool aliases/toolsets.
Toolsets allow you to group tools together for specific scenarios and can be composed
from individual tools or other toolsets.

Adapted from Hermes reference to support G-Agent's instance-based ToolRegistry.
"""

from typing import Any, Dict, List, Optional, Set

from g_agent.agent.tools.registry import ToolRegistry


# Shared tool list for CLI and all messaging platform toolsets.
_HERMES_CORE_TOOLS = [
    # Web
    "web_search",
    "web_extract",
    # Terminal + process management
    "terminal",
    "process",
    # File manipulation
    "read_file",
    "write_file",
    "patch",
    "search_files",
    # Vision + image generation
    "vision_analyze",
    "image_generate",
    # Skills
    "skills_list",
    "skill_view",
    "skill_manage",
    # Browser automation
    "browser_navigate",
    "browser_snapshot",
    "browser_click",
    "browser_type",
    "browser_scroll",
    "browser_back",
    "browser_press",
    "browser_get_images",
    "browser_vision",
    "browser_console",
    "browser_cdp",
    "browser_dialog",
    # Text-to-speech
    "text_to_speech",
    # Planning & memory
    "todo",
    "memory",
    # Session history search
    "session_search",
    # Clarifying questions
    "clarify",
    # Code execution + delegation
    "execute_code",
    "delegate_task",
    # Cronjob management
    "cronjob",
    # Cross-platform messaging
    "send_message",
]


# Core toolset definitions
TOOLSETS = {
    # Basic toolsets - individual tool categories
    "web": {
        "description": "Web research and content extraction tools",
        "tools": ["web_search", "web_extract", "web_fetch"],
        "includes": [],
    },
    "terminal": {
        "description": "Terminal/command execution and process management tools",
        "tools": ["exec", "process"],
        "includes": [],
    },
    "skills": {
        "description": "Access, create, edit, and manage skill documents with specialized instructions and knowledge",
        "tools": ["skill_manage"],
        "includes": [],
    },
    "browser": {
        "description": "Browser automation for web interaction",
        "tools": [
            "browser_open",
            "browser_snapshot",
            "browser_click",
            "browser_type",
            "browser_extract",
        ],
        "includes": ["web"],
    },
    "cronjob": {"description": "Cronjob management tool", "tools": ["cron"], "includes": []},
    "file": {
        "description": "File manipulation tools",
        "tools": ["read_file", "write_file", "edit_file", "list_dir"],
        "includes": [],
    },
    "memory": {
        "description": "Persistent memory across sessions",
        "tools": ["remember", "recall", "update_profile"],
        "includes": [],
    },
    "session_search": {
        "description": "Search and recall past conversations with summarization",
        "tools": ["session_search"],
        "includes": [],
    },
    "google_workspace": {
        "description": "Google Workspace integrations",
        "tools": [
            "gmail_list_threads",
            "gmail_read_thread",
            "gmail_reply",
            "gmail_reply_all",
            "gmail_forward",
            "gmail_send",
            "gmail_draft",
            "calendar_list_events",
            "calendar_create_event",
            "calendar_update_event",
            "drive_list_files",
            "drive_read_text",
            "docs_get_document",
            "docs_append_text",
            "sheets_get_values",
            "sheets_append_values",
            "contacts_list",
            "contacts_get",
        ],
        "includes": [],
    },
    "debugging": {
        "description": "Debugging and troubleshooting toolkit",
        "tools": ["exec"],
        "includes": ["web", "file"],
    },
    "safe": {
        "description": "Safe toolkit without terminal access",
        "tools": [],
        "includes": ["web", "memory", "session_search"],
    },
    "g_agent_cli": {
        "description": "Full interactive CLI toolset",
        "tools": [],
        "includes": [
            "web",
            "terminal",
            "file",
            "skills",
            "browser",
            "cronjob",
            "memory",
            "session_search",
            "google_workspace",
        ],
    },
}


class ToolsetResolver:
    """Resolves toolsets against a specific ToolRegistry instance."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def get_toolset(self, name: str) -> Optional[Dict[str, Any]]:
        toolset = TOOLSETS.get(name)
        if toolset:
            return toolset

        # MCP or Plugin Toolsets mapped directly from the registry
        # We assume `mcp_{server_name}_*` tools are loaded, but the registry
        # doesn't inherently group them unless we do it here.
        # Let's group tools by prefix to emulate MCP server groupings.
        prefix = f"mcp_{name}_"
        mcp_tools = [t for t in self.registry.tool_names if t.startswith(prefix)]

        if mcp_tools:
            return {
                "description": f"MCP server '{name}' tools",
                "tools": mcp_tools,
                "includes": [],
            }

        return None

    def resolve_toolset(self, name: str, visited: Optional[Set[str]] = None) -> List[str]:
        if visited is None:
            visited = set()

        if name in {"all", "*"}:
            all_tools: Set[str] = set()
            for toolset_name in self.get_toolset_names():
                resolved = self.resolve_toolset(toolset_name, visited.copy())
                all_tools.update(resolved)
            return sorted(all_tools)

        if name in visited:
            return []

        visited.add(name)

        toolset = self.get_toolset(name)
        if not toolset:
            # If not a toolset, maybe it's just a direct tool name
            if name in self.registry:
                return [name]
            return []

        tools = set(toolset.get("tools", []))

        for included_name in toolset.get("includes", []):
            included_tools = self.resolve_toolset(included_name, visited)
            tools.update(included_tools)

        return sorted(tools)

    def resolve_multiple_toolsets(self, toolset_names: List[str]) -> List[str]:
        all_tools = set()
        for name in toolset_names:
            tools = self.resolve_toolset(name)
            all_tools.update(tools)
        return sorted(all_tools)

    def get_toolset_names(self) -> List[str]:
        names = set(TOOLSETS.keys())

        # Add MCP server prefixes dynamically
        for tool_name in self.registry.tool_names:
            if tool_name.startswith("mcp_"):
                parts = tool_name.split("_", 2)
                if len(parts) >= 3:
                    names.add(parts[1])

        return sorted(names)
