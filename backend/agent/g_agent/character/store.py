"""Character profile store for G-Agent."""

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from g_agent.character.profile import CharacterProfile
from g_agent.utils.helpers import ensure_dir


class CharacterStore:
    """Manages character profile files in the workspace."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.profiles_dir = ensure_dir(workspace / "characters")

    def get(self, profile_id: str) -> CharacterProfile | None:
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

    def list(self) -> list[CharacterProfile]:
        """List all available character profiles."""
        profiles: list[CharacterProfile] = []
        for path in self.profiles_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                profiles.append(CharacterProfile(**data))
            except Exception:
                continue
        return sorted(profiles, key=lambda p: p.name)

    def get_default(self) -> CharacterProfile:
        """Get the default profile (owner) or create defaults if none exist."""
        profiles = self.list()
        if profiles:
            non_guests = [p for p in profiles if not p.is_guest]
            return non_guests[0] if non_guests else profiles[0]

        return self.setup_default_profiles()[0]

    def setup_default_profiles(self) -> list[CharacterProfile]:
        """Ensure owner and guest profiles exist without overwriting local edits."""
        owner = self.get("owner")
        if owner is None:
            owner = CharacterProfile(
                id="owner",
                name="G-Agent (Owner)",
                role="Personal operator for the founder.",
                is_guest=False,
                voice="Direct and helpful.",
                boundaries=["Protect owner secrets.", "Maintain workspace integrity."],
            )
            self.save(owner)

        guest = self.get("guest")
        if guest is None:
            guest = CharacterProfile(
                id="guest",
                name="G-Agent (Guest)",
                role="Helpful digital assistant for guests.",
                is_guest=True,
                voice="Polite and helpful.",
                boundaries=["No access to private files.", "No shell or write access."],
            )
            self.save(guest)

        return [owner, guest]
