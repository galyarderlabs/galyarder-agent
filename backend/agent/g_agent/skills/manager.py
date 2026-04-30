"""Skill manager for G-Agent lifecycle operations."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from g_agent.skills.store import SkillStore
from g_agent.skills.validator import SkillValidator


class SkillManager:
    """Handles skill draft, patch, activation, and rollback."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.store = SkillStore(workspace)
        self.validator = SkillValidator()
        self.backup_dir = workspace / "state" / "skills" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_draft(self, name: str, content: str) -> tuple[bool, list[str]]:
        """Create a new skill draft and validate it."""
        draft_path = self.store.create_draft(name, content)
        if not draft_path:
            return False, ["File system error during draft creation."]

        return self.validator.validate_skill_dir(draft_path)

    def patch_draft(
        self,
        name: str,
        find: str,
        replace: str,
        *,
        relative_path: str = "SKILL.md",
    ) -> tuple[bool, list[str]]:
        """Patch a draft skill file and rollback if validation fails."""
        draft_path = self.store.get_skill_path(name, location="draft")
        if not draft_path:
            return False, [f"Draft skill '{name}' not found."]
        if not find:
            return False, ["Patch find text cannot be empty."]
        if not self.validator.is_safe_path(draft_path, relative_path):
            return False, [f"Unsafe skill path: {relative_path}"]

        target = (draft_path / relative_path).resolve()
        if not target.exists() or not target.is_file():
            return False, [f"Draft file '{relative_path}' not found."]

        try:
            original = target.read_text(encoding="utf-8")
        except OSError as exc:
            return False, [f"Could not read draft file '{relative_path}': {exc}"]

        if find not in original:
            return False, ["Patch find text was not found."]

        updated = original.replace(find, replace, 1)
        try:
            target.write_text(updated, encoding="utf-8")
            ok, errors = self.validator.validate_skill_dir(draft_path)
            if ok:
                return True, []
            target.write_text(original, encoding="utf-8")
            return False, errors
        except OSError as exc:
            try:
                target.write_text(original, encoding="utf-8")
            except OSError:
                logger.error("Failed to restore draft skill {} after patch error", name)
            return False, [f"Patch failed for '{relative_path}': {exc}"]

    def activate_skill(self, name: str) -> tuple[bool, list[str]]:
        """Move a draft skill to the active custom skills directory."""
        ok, errors, _metadata = self.activate_skill_with_metadata(name)
        return ok, errors

    def activate_skill_with_metadata(
        self, name: str, activation_id: str | None = None
    ) -> tuple[bool, list[str], dict[str, Any]]:
        """Activate a draft skill and return rollback metadata."""
        draft_path = self.store.get_skill_path(name, location="draft")
        if not draft_path:
            return False, [f"Draft skill '{name}' not found."], {}

        ok, errors = self.validator.validate_skill_dir(draft_path)
        if not ok:
            return False, errors, {}

        target_path = self.store.custom_dir / name
        backup_path = self._backup_path(name, activation_id)
        metadata = {
            "skill_name": name,
            "activation_id": activation_id,
            "activated_path": str(target_path),
            "backup_path": str(backup_path),
            "had_previous": target_path.exists(),
        }

        try:
            if target_path.exists():
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                if backup_path.exists():
                    shutil.rmtree(backup_path)
                shutil.move(target_path, backup_path)

            shutil.move(draft_path, target_path)
            self._write_activation_record(name, metadata)
            return True, [], metadata
        except Exception as exc:
            logger.error("Failed to activate skill {}: {}", name, exc)
            if metadata["had_previous"] and backup_path.exists() and not target_path.exists():
                try:
                    shutil.move(backup_path, target_path)
                except Exception:
                    logger.error("Failed to restore skill {} after activation failure", name)
            return False, [str(exc)], metadata

    def rollback_activation(
        self,
        name: str,
        activation_id: str | None = None,
    ) -> tuple[bool, list[str]]:
        """Rollback the latest or named skill activation."""
        target_path = self.store.custom_dir / name
        record = self._read_activation_record(name)
        backup_path = Path(str(record.get("backup_path") or self._backup_path(name, activation_id)))
        had_previous = bool(record.get("had_previous"))

        try:
            if had_previous and not backup_path.exists():
                return False, [f"Rollback backup for skill '{name}' is missing."]

            if target_path.exists():
                rollback_draft = self.store.draft_dir / f"{name}.rolled-back"
                if rollback_draft.exists():
                    shutil.rmtree(rollback_draft)
                shutil.move(target_path, rollback_draft)

            if had_previous:
                shutil.move(backup_path, target_path)

            self._delete_activation_record(name)
            return True, []
        except Exception as exc:
            logger.error("Failed to rollback skill {}: {}", name, exc)
            return False, [str(exc)]

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

    def delete_draft(self, name: str) -> bool:
        """Delete a skill draft."""
        draft_path = self.store.get_skill_path(name, location="draft")
        if not draft_path:
            return False
        try:
            shutil.rmtree(draft_path)
            return True
        except Exception:
            return False

    def list_all(self, include_drafts: bool = True) -> dict[str, list[str]]:
        """Proxy to store.list_all."""
        return self.store.list_all(include_drafts=include_drafts)

    def _backup_path(self, name: str, activation_id: str | None = None) -> Path:
        """Build a rollback backup path."""
        token = activation_id or datetime.now().strftime("%Y%m%d%H%M%S")
        return self.backup_dir / name / token

    def _activation_record_path(self, name: str) -> Path:
        return self.backup_dir / name / "latest.json"

    def _write_activation_record(self, name: str, metadata: dict[str, Any]) -> None:
        path = self._activation_record_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    def _read_activation_record(self, name: str) -> dict[str, Any]:
        path = self._activation_record_path(name)
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            logger.warning("Failed to read activation record for skill {}", name)
        return {}

    def _delete_activation_record(self, name: str) -> None:
        try:
            self._activation_record_path(name).unlink(missing_ok=True)
        except Exception:
            logger.warning("Failed to delete activation record for skill {}", name)
