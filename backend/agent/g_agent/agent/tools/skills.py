"""Tool for managing G-Agent procedural skills."""

import json
from pathlib import Path
from typing import Any

from g_agent.agent.tools.base import Tool
from g_agent.skills.manager import SkillManager


class SkillManageTool(Tool):
    """List, view, and manage agent skills."""

    name = "skill_manage"
    description = (
        "Manage procedural skills. Use this to list active skills, "
        "view skill content, create or patch draft skills, or deactivate skills."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "view", "create_draft", "patch_draft", "activate_draft", "delete_draft", "deactivate"],
                "description": "Action to perform",
            },
            "name": {"type": "string", "description": "Skill name (folder name)"},
            "content": {
                "type": "string",
                "description": "Full SKILL.md content (required for create_draft)",
            },
            "find": {
                "type": "string",
                "description": "Exact text to replace when patching a draft skill",
            },
            "replace": {
                "type": "string",
                "description": "Replacement text when patching a draft skill",
            },
            "path": {
                "type": "string",
                "default": "SKILL.md",
                "description": "Draft skill file path to patch, relative to the skill directory",
            },
            "location": {
                "type": "string",
                "enum": ["builtin", "custom", "draft"],
                "default": "custom",
                "description": "Location to look for the skill",
            },
        },
        "required": ["action"],
    }

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.manager = SkillManager(workspace)

    async def execute(
        self,
        action: str,
        name: str | None = None,
        content: str | None = None,
        find: str | None = None,
        replace: str | None = None,
        path: str = "SKILL.md",
        location: str = "custom",
        **kwargs: Any,
    ) -> str:
        if action == "list":
            skills = self.manager.list_all()
            return json.dumps(skills, indent=2)

        if action == "view":
            if not name:
                return "Error: 'name' is required for action 'view'."
            path = self.manager.store.get_skill_path(name, location=location)
            if not path:
                return f"Error: Skill '{name}' not found in {location}."

            skill_md = path / "SKILL.md"
            if not skill_md.exists():
                return f"Error: SKILL.md missing for '{name}'."

            return skill_md.read_text(encoding="utf-8")

        if action == "create_draft":
            if not name or not content:
                return "Error: 'name' and 'content' are required for 'create_draft'."

            ok, errors = self.manager.create_draft(name, content)
            if ok:
                return f"Success: Draft skill '{name}' created and validated."
            else:
                return f"Validation failed for draft '{name}':\n" + "\n".join(
                    f"- {e}" for e in errors
                )

        if action == "patch_draft":
            if not name or find is None or replace is None:
                return "Error: 'name', 'find', and 'replace' are required for 'patch_draft'."

            ok, errors = self.manager.patch_draft(
                name,
                find,
                replace,
                relative_path=path or "SKILL.md",
            )
            if ok:
                return f"Success: Draft skill '{name}' patched and validated."
            return f"Validation failed for draft patch '{name}':\n" + "\n".join(
                f"- {e}" for e in errors
            )

        if action == "activate_draft":
            if not name:
                return "Error: 'name' is required for 'activate_draft'."
            ok, errors = self.manager.activate_skill(name)
            if ok:
                return f"Success: Skill '{name}' activated."
            return f"Activation failed for '{name}':\n" + "\n".join(f"- {e}" for e in errors)

        if action == "delete_draft":
            if not name:
                return "Error: 'name' is required for 'delete_draft'."
            if self.manager.delete_draft(name):
                return f"Success: Draft skill '{name}' deleted."
            return f"Error: Could not delete draft skill '{name}'."

        if action == "deactivate":
            if not name:
                return "Error: 'name' is required for 'deactivate'."
            if self.manager.disable_skill(name):
                return f"Success: Skill '{name}' moved to drafts."
            else:
                return (
                    f"Error: Could not deactivate skill '{name}' (maybe it's builtin or not found)."
                )

        return f"Error: Unknown action '{action}'."
