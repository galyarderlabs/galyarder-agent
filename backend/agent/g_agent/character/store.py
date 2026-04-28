"""Character profile store for G-Agent."""

import json
from pathlib import Path
from typing import List, Optional

from loguru import logger
from g_agent.character.profile import CharacterProfile
from g_agent.utils.helpers import ensure_dir


class CharacterStore:
    """Manages character profile files in the workspace."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.profiles_dir = ensure_dir(workspace / "characters")

    def get(self, profile_id: str) -> Optional[CharacterProfile]:
        """Load a character profile by ID."""
        path = self.profiles_dir / f"{profile_id}.json"
        if not path.exists():
            return None

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return CharacterProfile(**data)
        except Exception as e:
            logger.error(f"Failed to load character profile {profile_id}: {e}")
            return None

    def save(self, profile: CharacterProfile) -> bool:
        """Save a character profile to disk."""
        path = self.profiles_dir / f"{profile.id}.json"
        try:
            path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
            return True
        except Exception as e:
            logger.error(f"Failed to save character profile {profile.id}: {e}")
            return False

    def list(self) -> List[CharacterProfile]:
        """List all available character profiles."""
        profiles = []
        for path in self.profiles_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                profiles.append(CharacterProfile(**data))
            except Exception:
                continue
        return sorted(profiles, key=lambda p: p.name)

    def get_default(self) -> CharacterProfile:
        """Get the default profile or create one if none exist."""
        profiles = self.list()
        if profiles:
            return profiles[0]

        # Create generic default
        default = CharacterProfile(
            id="default",
            name="G-Agent",
            role="Agentic digital character and personal operator.",
            voice="Direct, helpful, and continuity-focused.",
            boundaries=["Do not violate user privacy.", "Stay within workspace boundaries."],
        )
        self.save(default)
        return default
