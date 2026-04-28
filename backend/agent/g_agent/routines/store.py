"""Routine store for G-Agent."""

import json
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger
from g_agent.routines.model import Routine
from g_agent.utils.helpers import ensure_dir


class RoutineStore:
    """Manages persistence of routines in the workspace."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.routines_dir = ensure_dir(workspace / "routines")
        self._cache: Dict[str, Routine] = {}
        self.reload()

    def reload(self):
        """Reload all routines from disk."""
        self._cache = {}
        if not self.routines_dir.exists():
            return

        for path in self.routines_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                routine = Routine.model_validate(data)
                self._cache[routine.id] = routine
            except Exception as e:
                logger.error(f"Failed to load routine from {path}: {e}")

    def list(self, enabled_only: bool = False) -> List[Routine]:
        """List all routines."""
        routines = list(self._cache.values())
        if enabled_only:
            routines = [r for r in routines if r.enabled]
        return sorted(routines, key=lambda x: x.name)

    def get(self, routine_id: str) -> Optional[Routine]:
        """Get a routine by ID."""
        return self._cache.get(routine_id)

    def save(self, routine: Routine) -> bool:
        """Save a routine to disk."""
        path = self.routines_dir / f"{routine.id}.json"
        try:
            path.write_text(routine.model_dump_json(indent=2), encoding="utf-8")
            self._cache[routine.id] = routine
            return True
        except Exception as e:
            logger.error(f"Failed to save routine {routine.id}: {e}")
            return False

    def delete(self, routine_id: str) -> bool:
        """Delete a routine from disk."""
        path = self.routines_dir / f"{routine_id}.json"
        try:
            if path.exists():
                path.unlink()
            self._cache.pop(routine_id, None)
            return True
        except Exception as e:
            logger.error(f"Failed to delete routine {routine_id}: {e}")
            return False
