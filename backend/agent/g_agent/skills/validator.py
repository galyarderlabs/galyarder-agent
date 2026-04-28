"""Skill validator for G-Agent."""

import re
from pathlib import Path
from typing import List, Tuple

import yaml


class SkillValidator:
    """Validates G-Agent skill structure and content."""

    MAX_SKILL_SIZE_BYTES = 100 * 1024  # 100KB
    ALLOWED_SUBDIRS = {"references", "templates", "scripts", "assets"}

    def validate_skill_dir(self, skill_dir: Path) -> Tuple[bool, List[str]]:
        """
        Validate a skill directory structure.
        Returns (is_valid, errors).
        """
        errors = []
        if not skill_dir.exists() or not skill_dir.is_dir():
            return False, ["Skill directory does not exist or is not a directory."]

        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            errors.append("Missing SKILL.md file.")
        else:
            # Validate SKILL.md content
            valid_content, md_errors = self.validate_skill_md(skill_md)
            errors.extend(md_errors)

        # Check for unauthorized subdirectories
        for item in skill_dir.iterdir():
            if item.is_dir() and item.name not in self.ALLOWED_SUBDIRS:
                errors.append(f"Unauthorized subdirectory: {item.name}")

        return len(errors) == 0, errors

    def validate_skill_md(self, file_path: Path) -> Tuple[bool, List[str]]:
        """Validate SKILL.md content (frontmatter, size)."""
        errors = []

        # Size check
        try:
            size = file_path.stat().st_size
            if size > self.MAX_SKILL_SIZE_BYTES:
                errors.append(
                    f"SKILL.md exceeds size limit ({size} > {self.MAX_SKILL_SIZE_BYTES} bytes)."
                )
        except OSError as e:
            return False, [f"Could not access SKILL.md: {e}"]

        # Content check
        try:
            content = file_path.read_text(encoding="utf-8")

            # Extract frontmatter
            fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
            if not fm_match:
                errors.append("SKILL.md missing YAML frontmatter (between --- delimiters).")
            else:
                fm_text = fm_match.group(1)
                try:
                    fm = yaml.safe_load(fm_text)
                    if not isinstance(fm, dict):
                        errors.append("Invalid YAML frontmatter format.")
                    else:
                        if "name" not in fm:
                            errors.append("Frontmatter missing 'name' field.")
                        if "description" not in fm:
                            errors.append("Frontmatter missing 'description' field.")
                except yaml.YAMLError as e:
                    errors.append(f"YAML parsing error in frontmatter: {e}")

        except Exception as e:
            errors.append(f"Error reading SKILL.md: {e}")

        return len(errors) == 0, errors

    def is_safe_path(self, skill_dir: Path, relative_path: str) -> bool:
        """Prevent path traversal within a skill directory."""
        try:
            target = (skill_dir / relative_path).resolve()
            return skill_dir.resolve() in target.parents or target == skill_dir.resolve()
        except Exception:
            return False
