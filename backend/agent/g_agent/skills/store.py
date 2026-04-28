"""Skill store for G-Agent."""

import json
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger
from g_agent.utils.helpers import ensure_dir


class SkillStore:
    """Locates and manages skill files in builtin and custom locations."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        # Builtin skills live in the package
        self.builtin_dir = Path(__file__).parent.parent / "skills"
        # Custom skills live in the workspace
        self.custom_dir = ensure_dir(workspace / "skills")
        # Draft skills live in a separate quarantine area
        self.draft_dir = ensure_dir(workspace / "state" / "skills" / "drafts")

    def list_all(self, include_drafts: bool = False) -> Dict[str, List[str]]:
        """List names of skills in all locations."""
        result = {
            "builtin": self._list_dir(self.builtin_dir),
            "custom": self._list_dir(self.custom_dir),
        }
        if include_drafts:
            result["drafts"] = self._list_dir(self.draft_dir)
        return result

    def get_skill_path(self, name: str, location: str = "custom") -> Optional[Path]:
        """Get the directory path for a skill."""
        if location == "builtin":
            base = self.builtin_dir
        elif location == "draft":
            base = self.draft_dir
        else:
            base = self.custom_dir
        
        path = base / name
        return path if path.exists() and path.is_dir() else None

    def _list_dir(self, directory: Path) -> List[str]:
        """List subdirectories that contain a SKILL.md."""
        skills = []
        if not directory.exists():
            return []
        for item in directory.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                skills.append(item.name)
        return sorted(skills)

    def create_draft(self, name: str, content: str) -> Optional[Path]:
        """Create a new draft skill directory and SKILL.md."""
        draft_path = self.draft_dir / name
        try:
            draft_path.mkdir(parents=True, exist_ok=True)
            (draft_path / "SKILL.md").write_text(content, encoding="utf-8")
            # Create standard subdirs
            for subdir in ["references", "templates", "scripts", "assets"]:
                (draft_path / subdir).mkdir(exist_ok=True)
            return draft_path
        except Exception as e:
            logger.error(f"Failed to create draft skill {name}: {e}")
            return None
