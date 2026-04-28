"""Toolsets management for G-Agent."""

from typing import Any, Dict, List, Optional, Set


# Core toolset definitions
DEFAULT_TOOLSETS = {
    "safe": {
        "description": "Safe tools without filesystem or terminal access",
        "tools": ["web_search", "web_fetch", "message", "recall", "remember"],
        "includes": [],
    },
    "file": {
        "description": "File manipulation tools",
        "tools": ["read_file", "write_file", "edit_file", "list_dir"],
        "includes": [],
    },
    "terminal": {"description": "Terminal and shell execution", "tools": ["exec"], "includes": []},
    "web": {
        "description": "Web browsing and searching",
        "tools": ["web_search", "web_fetch"],
        "includes": [],
    },
    "browser": {
        "description": "Playwright browser automation",
        "tools": [
            "browser_open",
            "browser_click",
            "browser_type",
            "browser_snapshot",
            "browser_screenshot",
            "browser_extract",
        ],
        "includes": ["web"],
    },
    "google_workspace": {
        "description": "Google Workspace integrations (Gmail, Calendar, Drive, Docs, Sheets, Contacts)",
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
    "memory": {
        "description": "Memory and character management",
        "tools": ["remember", "recall", "update_profile", "session_search"],
        "includes": [],
    },
    "skills": {
        "description": "Procedural skills management",
        "tools": ["skill_manage"],
        "includes": [],
    },
    "routines": {
        "description": "Background routines and scheduling",
        "tools": ["cron"],
        "includes": [],
    },
    "admin": {
        "description": "Full administrative access",
        "tools": [],
        "includes": [
            "safe",
            "file",
            "terminal",
            "browser",
            "memory",
            "skills",
            "routines",
            "google_workspace",
        ],
    },
}


class ToolsetManager:
    """Manages grouping and resolution of tools into sets."""

    def __init__(self, custom_toolsets: Optional[Dict[str, Any]] = None):
        self._toolsets = dict(DEFAULT_TOOLSETS)
        if custom_toolsets:
            self._toolsets.update(custom_toolsets)

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a toolset definition by name."""
        return self._toolsets.get(name)

    def resolve(self, names: List[str]) -> Set[str]:
        """Resolve one or more toolset names into a flat set of tool names."""
        resolved: Set[str] = set()
        visited: Set[str] = set()

        def _resolve_recursive(ts_name: str):
            if ts_name in visited:
                return
            visited.add(ts_name)

            ts = self._toolsets.get(ts_name)
            if not ts:
                # If it's not a toolset name, treat it as a direct tool name
                resolved.add(ts_name)
                return

            resolved.update(ts.get("tools", []))
            for inc in ts.get("includes", []):
                _resolve_recursive(inc)

        for name in names:
            if name in ["*", "all"]:
                for ts in self._toolsets:
                    _resolve_recursive(ts)
                break
            _resolve_recursive(name)

        return resolved

    def list_names(self) -> List[str]:
        """List all available toolset names."""
        return sorted(list(self._toolsets.keys()))
