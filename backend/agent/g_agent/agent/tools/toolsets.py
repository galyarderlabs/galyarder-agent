"""Toolset definitions for capability-scoped tool exposure."""

from typing import Any

from g_agent.agent.tools.registry import ToolRegistry


# Static capability groups. The runtime intersects these names with the active
# registry, so optional tools such as cron/selfie are exposed only when registered.
TOOLSETS = {
    "web": {
        "description": "Web research and content extraction tools",
        "tools": ["web_search", "web_fetch"],
        "includes": [],
    },
    "terminal": {
        "description": "Host shell command execution",
        "tools": ["exec"],
        "includes": [],
    },
    "code_execution": {
        "description": "Code and command execution tools",
        "tools": ["exec"],
        "includes": [],
    },
    "file": {
        "description": "Workspace file inspection and editing tools",
        "tools": ["read_file", "write_file", "edit_file", "list_dir"],
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
            "browser_screenshot",
        ],
        "includes": ["web"],
    },
    "vision": {
        "description": "Visual identity and image-oriented tools",
        "tools": ["selfie"],
        "includes": [],
    },
    "image": {
        "description": "Image generation and image delivery tools",
        "tools": ["selfie", "message"],
        "includes": [],
    },
    "messaging": {
        "description": "Cross-channel outbound messaging tools",
        "tools": ["message", "send_email", "slack_webhook_send"],
        "includes": [],
    },
    "memory": {
        "description": "Persistent memory and profile recall",
        "tools": ["remember", "recall", "update_profile", "log_feedback"],
        "includes": ["session_search"],
    },
    "session_search": {
        "description": "Search and recall past conversations with summarization",
        "tools": ["session_search"],
        "includes": [],
    },
    "skills": {
        "description": "Access, create, edit, and manage skill documents with specialized instructions and knowledge",
        "tools": ["skill_manage"],
        "includes": [],
    },
    "routines": {"description": "Routine and cron scheduling tools", "tools": ["cron"], "includes": []},
    "cronjob": {"description": "Alias for routine scheduling tools", "tools": [], "includes": ["routines"]},
    "subagents": {
        "description": "Background delegation tools",
        "tools": ["spawn"],
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
            "messaging",
            "subagents",
        ],
    },
}


class ToolsetResolver:
    """Resolves toolsets against a specific ToolRegistry instance."""

    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def get_toolset(self, name: str) -> dict[str, Any] | None:
        toolset = TOOLSETS.get(name)
        if toolset:
            return toolset

        if name == "mcp":
            mcp_tools = [tool for tool in self.registry.tool_names if tool.startswith("mcp_")]
            return {
                "description": "All registered MCP tools",
                "tools": mcp_tools,
                "includes": [],
            }

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

    def resolve_toolset(self, name: str, visited: set[str] | None = None) -> list[str]:
        if visited is None:
            visited = set()

        if name in {"all", "*"}:
            all_tools: set[str] = set()
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

    def resolve_multiple_toolsets(self, toolset_names: list[str]) -> list[str]:
        all_tools = set()
        for name in toolset_names:
            tools = self.resolve_toolset(name)
            all_tools.update(tools)
        return sorted(all_tools)

    def get_toolset_names(self) -> list[str]:
        names = set(TOOLSETS.keys())
        if any(tool_name.startswith("mcp_") for tool_name in self.registry.tool_names):
            names.add("mcp")

        # Add MCP server prefixes dynamically
        for tool_name in self.registry.tool_names:
            if tool_name.startswith("mcp_"):
                parts = tool_name.split("_", 2)
                if len(parts) >= 3:
                    names.add(parts[1])

        return sorted(names)
