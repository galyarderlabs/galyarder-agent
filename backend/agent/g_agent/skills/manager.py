"""Skill manager for G-Agent lifecycle operations."""

import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loguru import logger
from g_agent.skills.store import SkillStore
from g_agent.skills.validator import SkillValidator


class SkillManager:
    """Handles skill draft, patch, activation, and rollback."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.store = SkillStore(workspace)
        self.validator = SkillValidator()

    def create_draft(self, name: str, content: str) -> Tuple[bool, List[str]]:
        """Create a new skill draft and validate it."""
        draft_path = self.store.create_draft(name, content)
        if not draft_path:
            return False, ["File system error during draft creation."]
        
        return self.validator.validate_skill_dir(draft_path)

    def activate_skill(self, name: str) -> Tuple[bool, List[str]]:
        """Move a draft skill to the active custom skills directory."""
        draft_path = self.store.get_skill_path(name, location="draft")
        if not draft_path:
            return False, [f"Draft skill '{name}' not found."]

        # Validate one last time
        ok, errors = self.validator.validate_skill_dir(draft_path)
        if not ok:
            return False, errors

        # Ensure custom dir exists
        target_path = self.store.custom_dir / name
        
        try:
            # Backup existing if any
            if target_path.exists():
                backup_path = target_path.with_suffix(".bak")
                if backup_path.exists():
                    shutil.rmtree(backup_path)
                shutil.move(target_path, backup_path)

            # Move draft to active
            shutil.move(draft_path, target_path)
            return True, []
        except Exception as e:
            logger.error(f"Failed to activate skill {name}: {e}")
            return False, [str(e)]

    def disable_skill(self, name: str) -> bool:
        """Move an active custom skill to drafts (deactivate)."""
        active_path = self.store.get_skill_path(name, location="custom")
        if not active_path:
            return False

        target_path = self.store.draft_dir / name
        try:
            if target_path.exists():
                shutil.rmtree(target_path)
            shutil.move(active_path, target_path)
            return True
        except Exception:
            return False

    def list_all(self, include_drafts: bool = True) -> Dict[str, List[str]]:
        """Proxy to store.list_all."""
        return self.store.list_all(include_drafts=include_drafts)
