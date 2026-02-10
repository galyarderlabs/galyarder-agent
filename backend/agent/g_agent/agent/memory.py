"""Memory system for persistent agent memory."""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from g_agent.utils.helpers import ensure_dir, today_date


class MemoryStore:
    """
    Memory system for the agent.

    Supports daily notes (memory/YYYY-MM-DD.md) and long-term memory (MEMORY.md).
    """

    STOPWORDS = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "have",
        "your",
        "you",
        "are",
        "was",
        "were",
        "will",
        "can",
        "not",
        "just",
        "buat",
        "yang",
        "dan",
        "dari",
        "atau",
        "itu",
        "ini",
        "aja",
        "saya",
        "aku",
        "gua",
        "kamu",
        "nya",
    }
    SOURCE_WEIGHTS = {
        "profile": 240,
        "relationships": 210,
        "projects": 190,
        "long-term": 170,
        "lessons": 150,
        "custom": 145,
        "summary": 130,
        "daily": 110,
    }
    SOURCE_DEFAULT_CONFIDENCE = {
        "profile": 0.95,
        "relationships": 0.9,
        "projects": 0.85,
        "long-term": 0.8,
        "lessons": 0.78,
        "custom": 0.74,
        "summary": 0.7,
        "daily": 0.64,
    }
    CORE_MEMORY_FILES = {
        "MEMORY.md",
        "LESSONS.md",
        "PROFILE.md",
        "RELATIONSHIPS.md",
        "PROJECTS.md",
        "SUMMARIES.md",
        "user_profile.md",
        "FACTS.md",
    }
    SEMANTIC_PHRASE_MAP = (
        ("time zone", "timezone"),
        ("zona waktu", "timezone"),
    )
    SEMANTIC_TOKEN_MAP = {
        "jadwal": "schedule",
        "schedule": "schedule",
        "rapat": "meeting",
        "meeting": "meeting",
        "mingguan": "weekly",
        "weekly": "weekly",
        "fokus": "focus",
        "focus": "focus",
        "arsitektur": "architecture",
        "architecture": "architecture",
        "proyek": "project",
        "project": "project",
        "bahasa": "language",
        "language": "language",
        "pengingat": "reminder",
        "reminder": "reminder",
        "memori": "memory",
        "memory": "memory",
    }

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory_dir = ensure_dir(workspace / "memory")
        self.memory_file = self.memory_dir / "MEMORY.md"
        self.lessons_file = self.memory_dir / "LESSONS.md"
        self.profile_file = self.memory_dir / "PROFILE.md"
        self.profile_alias_file = self.memory_dir / "user_profile.md"
        self.relationships_file = self.memory_dir / "RELATIONSHIPS.md"
        self.projects_file = self.memory_dir / "PROJECTS.md"
        self.summaries_file = self.memory_dir / "SUMMARIES.md"
        self.facts_file = self.memory_dir / "FACTS.md"
        self._ensure_scaffold()

    def _ensure_scaffold(self) -> None:
        """Create baseline memory files when missing."""
        templates = {
            self.memory_file: ("# Long-term Memory\n\nDurable facts to keep across sessions.\n"),
            self.profile_file: (
                "# Profile\n\n"
                "## Identity\n"
                "- name: \n"
                "- timezone: \n"
                "- language: \n\n"
                "## Preferences\n"
                "- communication_style: \n"
                "- notification_style: \n"
            ),
            self.relationships_file: ("# Relationships\n\n- [name] role, context, preference\n"),
            self.projects_file: (
                "# Projects\n\n## Active\n- [project] status: ; next: \n\n## Backlog\n"
            ),
            self.facts_file: (
                "# Fact Index (Machine-readable)\n\n"
                "JSON lines with fields: id, type, confidence, source, last_seen, supersedes.\n"
            ),
        }
        for file_path, content in templates.items():
            if file_path.exists():
                continue
            try:
                file_path.write_text(content, encoding="utf-8")
            except OSError:
                continue
        self._sync_profile_alias()

    def _sync_profile_alias(self) -> None:
        """Ensure user_profile.md mirrors PROFILE.md for compatibility."""
        profile_content = self._safe_read(self.profile_file)
        alias_content = self._safe_read(self.profile_alias_file)

        if not profile_content and alias_content:
            self._safe_write(self.profile_file, alias_content)
            profile_content = alias_content

        if self.profile_alias_file.exists():
            alias_is_symlink = False
            try:
                alias_is_symlink = self.profile_alias_file.is_symlink()
            except OSError:
                alias_is_symlink = False
            if alias_is_symlink:
                return
            if profile_content and alias_content != profile_content:
                self._safe_write(self.profile_alias_file, profile_content)
            return

        try:
            self.profile_alias_file.symlink_to(self.profile_file.name)
            return
        except OSError:
            if profile_content:
                self._safe_write(self.profile_alias_file, profile_content)
            return

        if profile_content:
            self._safe_write(self.profile_alias_file, profile_content)

    def _write_profile(self, content: str) -> bool:
        """Write PROFILE.md and keep user_profile.md in sync."""
        ok = self._safe_write(self.profile_file, content)
        if not ok:
            return False
        self._sync_profile_alias()
        return True

    def _normalize_for_dedup(self, text: str) -> str:
        """Normalize text for lightweight dedup checks."""
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    def _semantic_normalize(self, text: str) -> str:
        """Apply lightweight phrase normalization for multilingual matching."""
        normalized = self._normalize_for_dedup(text)
        if not normalized:
            return ""
        for source, target in self.SEMANTIC_PHRASE_MAP:
            normalized = re.sub(rf"\b{re.escape(source)}\b", target, normalized)
        return normalized

    def _safe_read(self, path: Path) -> str:
        """Read file safely (returns empty string on error)."""
        try:
            if path.exists():
                return path.read_text(encoding="utf-8")
        except OSError:
            return ""
        return ""

    def _safe_write(self, path: Path, content: str) -> bool:
        """Write file safely."""
        try:
            path.write_text(content, encoding="utf-8")
            return True
        except OSError:
            return False

    def _now_iso(self) -> str:
        """Current timestamp in ISO-8601 UTC."""
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    def _parse_timestamp(self, value: str | None) -> datetime | None:
        """Parse mixed timestamp formats used in memory files."""
        raw = (value or "").strip()
        if not raw:
            return None
        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            pass
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    def _timestamp_to_iso(self, value: str | None, fallback_iso: str) -> str:
        parsed = self._parse_timestamp(value)
        if not parsed:
            return fallback_iso
        return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()

    def _age_days(self, iso_value: str | None) -> int:
        parsed = self._parse_timestamp(iso_value)
        if not parsed:
            return 30
        delta = datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)
        return max(0, int(delta.total_seconds() // 86400))

    def _clamp_confidence(self, value: Any) -> float:
        try:
            conf = float(value)
        except (TypeError, ValueError):
            conf = 0.75
        return max(0.0, min(1.0, conf))

    def _default_confidence_for_category(self, category: str) -> float:
        category_norm = (category or "").strip().lower()
        if category_norm in {"identity", "profile"}:
            return 0.95
        if category_norm in {"preference", "preferences"}:
            return 0.9
        if category_norm in {"relationship", "relationships"}:
            return 0.88
        if category_norm in {"project", "projects"}:
            return 0.82
        if category_norm in {"lesson", "lessons"}:
            return 0.78
        return 0.75

    def _build_fact_id(self, fact_text: str, fact_type: str, created_at: str) -> str:
        seed = f"{fact_type}|{self._normalize_for_dedup(fact_text)}|{created_at}"
        digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]
        return f"fact_{digest}"

    def _extract_fact_key(self, text: str) -> str:
        raw = (text or "").strip().lower()
        if not raw:
            return ""
        for separator in (":", "="):
            if separator not in raw:
                continue
            head = raw.split(separator, 1)[0].strip()
            head_tokens = re.findall(r"[a-z0-9]{2,}", head)
            if 1 <= len(head_tokens) <= 7:
                return " ".join(head_tokens)
        direct_key = re.match(
            r"^(?:my|i|i'm|i am|saya|aku|gua)\s+"
            r"(name|timezone|language|email|phone|location|goal|focus)\s+"
            r"(?:is|are|adalah)\b",
            raw,
        )
        if direct_key:
            return direct_key.group(1)
        return ""

    def _extract_fact_value(self, text: str) -> str:
        raw = (text or "").strip()
        if not raw:
            return ""
        if raw.startswith("- "):
            raw = raw[2:].strip()
        for separator in (":", "="):
            if separator in raw:
                value = raw.split(separator, 1)[1].strip()
                if value:
                    return value
        direct_value = re.match(
            r"^(?:my|i|i'm|i am|saya|aku|gua)\s+[a-z0-9_ \-]{2,40}\s+"
            r"(?:is|are|adalah)\s+(.+)$",
            raw.lower(),
        )
        if direct_value:
            return direct_value.group(1).strip()
        return ""

    def _normalize_fact_value(self, value: str) -> str:
        normalized = self._semantic_normalize(value)
        normalized = normalized.strip(" .;,|")
        return re.sub(r"\s+", " ", normalized)

    def _parse_long_term_entry(self, line: str, fallback_iso: str) -> dict[str, Any] | None:
        raw = line.strip()
        if not raw or raw.startswith("#"):
            return None
        if raw.startswith("- "):
            raw = raw[2:].strip()
        if not raw:
            return None

        timestamp_label = ""
        meta_blob = ""
        text = raw

        full_match = re.match(r"^\[([^\]]+)\]\s*(?:\(([^)]*)\))?\s*(.+)$", raw)
        if full_match:
            timestamp_label = full_match.group(1).strip()
            meta_blob = (full_match.group(2) or "").strip()
            text = full_match.group(3).strip()

        if not text or text.startswith("#"):
            return None

        fact_type = "general"
        source = "legacy_import"
        confidence = self._default_confidence_for_category(fact_type)
        if meta_blob:
            if "=" in meta_blob:
                pairs = [
                    item.strip()
                    for item in re.split(r"[;,]", meta_blob)
                    if item.strip() and "=" in item
                ]
                parsed_meta: dict[str, str] = {}
                for pair in pairs:
                    key, value = pair.split("=", 1)
                    parsed_meta[key.strip().lower()] = value.strip()
                fact_type = parsed_meta.get("type", parsed_meta.get("category", fact_type)).lower()
                source = parsed_meta.get("source", source)
                if "confidence" in parsed_meta:
                    confidence = self._clamp_confidence(parsed_meta.get("confidence"))
                else:
                    confidence = self._default_confidence_for_category(fact_type)
            else:
                fact_type = meta_blob.lower()
                confidence = self._default_confidence_for_category(fact_type)

        created_at = self._timestamp_to_iso(timestamp_label, fallback_iso)
        return {
            "id": self._build_fact_id(text, fact_type, created_at),
            "text": text,
            "normalized": self._normalize_for_dedup(text),
            "type": fact_type,
            "confidence": confidence,
            "source": source,
            "created_at": created_at,
            "last_seen": created_at,
            "fact_key": self._extract_fact_key(text),
            "supersedes": [],
            "status": "active",
        }

    def _write_fact_index(self, records: list[dict[str, Any]]) -> bool:
        header = (
            "# Fact Index (Machine-readable)\n\n"
            "JSON lines with fields: id, type, confidence, source, last_seen, supersedes.\n\n"
        )
        lines = [header]
        for item in records:
            lines.append(json.dumps(item, ensure_ascii=False, sort_keys=True))
        payload = "\n".join(lines).rstrip() + "\n"
        return self._safe_write(self.facts_file, payload)

    def _bootstrap_fact_index_from_long_term(self) -> list[dict[str, Any]]:
        baseline_iso = self._now_iso()
        records: list[dict[str, Any]] = []
        by_normalized: dict[str, int] = {}
        active_by_key: dict[str, int] = {}

        for line in self.read_long_term().splitlines():
            parsed = self._parse_long_term_entry(line, fallback_iso=baseline_iso)
            if not parsed:
                continue
            normalized = parsed.get("normalized", "")
            if not normalized:
                continue
            existing_idx = by_normalized.get(normalized)
            if existing_idx is not None:
                records[existing_idx]["last_seen"] = parsed["last_seen"]
                continue

            fact_key = parsed.get("fact_key", "")
            if fact_key:
                previous_idx = active_by_key.get(fact_key)
                if previous_idx is not None:
                    previous = records[previous_idx]
                    previous["status"] = "superseded"
                    previous["superseded_by"] = parsed["id"]
                    previous["last_seen"] = parsed["created_at"]
                    parsed["supersedes"] = [previous["id"]]

            records.append(parsed)
            new_idx = len(records) - 1
            by_normalized[normalized] = new_idx
            if fact_key:
                active_by_key[fact_key] = new_idx

        return records

    def _load_fact_index(self) -> list[dict[str, Any]]:
        """Load schema-based fact index; bootstrap from MEMORY.md if missing."""
        records: list[dict[str, Any]] = []
        for raw_line in self._safe_read(self.facts_file).splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                records.append(item)

        if records:
            return records

        bootstrapped = self._bootstrap_fact_index_from_long_term()
        if bootstrapped:
            self._write_fact_index(bootstrapped)
        return bootstrapped

    def get_today_file(self) -> Path:
        """Get path to today's memory file."""
        return self.memory_dir / f"{today_date()}.md"

    def read_today(self) -> str:
        """Read today's memory notes."""
        return self._safe_read(self.get_today_file())

    def append_today(self, content: str) -> None:
        """Append content to today's memory notes."""
        today_file = self.get_today_file()

        existing = self._safe_read(today_file)
        if existing:
            content = existing + "\n" + content
        else:
            # Add header for new day
            header = f"# {today_date()}\n\n"
            content = header + content

        self._safe_write(today_file, content)

    def read_long_term(self) -> str:
        """Read long-term memory (MEMORY.md)."""
        return self._safe_read(self.memory_file)

    def write_long_term(self, content: str) -> None:
        """Write to long-term memory (MEMORY.md)."""
        self._safe_write(self.memory_file, content)

    def read_profile(self) -> str:
        """Read user profile memory."""
        profile = self._safe_read(self.profile_file)
        if profile:
            return profile
        legacy = self._safe_read(self.profile_alias_file)
        if legacy:
            self._safe_write(self.profile_file, legacy)
            self._sync_profile_alias()
            return legacy
        return ""

    def read_relationships(self) -> str:
        """Read relationships memory."""
        return self._safe_read(self.relationships_file)

    def read_projects(self) -> str:
        """Read projects memory."""
        return self._safe_read(self.projects_file)

    def read_summaries(self) -> str:
        """Read session summaries memory."""
        return self._safe_read(self.summaries_file)

    def upsert_profile_field(self, section: str, key: str, value: str) -> bool:
        """Upsert a key/value field in PROFILE.md under the given section."""
        section_name = (section or "Preferences").strip().title()
        field = (key or "").strip()
        val = (value or "").strip()
        if not field:
            return False

        content = self.read_profile()
        if not content:
            content = "# Profile\n\n"

        lines = content.splitlines()
        section_header = f"## {section_name}"

        if section_header not in lines:
            if lines and lines[-1].strip():
                lines.append("")
            lines.append(section_header)
            lines.append(f"- {field}: {val}")
            return self._write_profile("\n".join(lines).rstrip() + "\n")

        start = lines.index(section_header)
        end = len(lines)
        for idx in range(start + 1, len(lines)):
            if lines[idx].startswith("## "):
                end = idx
                break

        field_pattern = re.compile(rf"^\s*-\s*{re.escape(field)}\s*:\s*", flags=re.I)
        for idx in range(start + 1, end):
            if field_pattern.match(lines[idx]):
                lines[idx] = f"- {field}: {val}"
                return self._write_profile("\n".join(lines).rstrip() + "\n")

        insert_at = end
        if insert_at > start + 1 and lines[insert_at - 1].strip():
            lines.insert(insert_at, f"- {field}: {val}")
        else:
            lines.insert(insert_at, f"- {field}: {val}")
        return self._write_profile("\n".join(lines).rstrip() + "\n")

    def remember_fact(
        self,
        fact: str,
        category: str = "general",
        source: str = "remember_tool",
        confidence: float | None = None,
    ) -> dict[str, Any]:
        """Persist durable fact using schema metadata and supersede rules."""
        text = (fact or "").strip()
        fact_type = (category or "general").strip().lower() or "general"
        source_label = (source or "remember_tool").strip() or "remember_tool"
        if not text:
            return {"ok": False, "status": "empty"}

        records = self._load_fact_index()
        now_iso = self._now_iso()
        normalized = self._normalize_for_dedup(text)
        fact_key = self._extract_fact_key(text)
        confidence_value = self._clamp_confidence(
            confidence
            if confidence is not None
            else self._default_confidence_for_category(fact_type)
        )

        for item in records:
            if item.get("status", "active") != "active":
                continue
            if item.get("normalized") != normalized:
                continue
            item["last_seen"] = now_iso
            item["confidence"] = max(
                self._clamp_confidence(item.get("confidence")), confidence_value
            )
            if not item.get("source"):
                item["source"] = source_label
            if self._write_fact_index(records):
                return {
                    "ok": True,
                    "status": "duplicate",
                    "fact_id": item.get("id", ""),
                    "superseded_ids": [],
                }
            return {"ok": False, "status": "write_error"}

        fact_id = self._build_fact_id(text, fact_type, now_iso)
        superseded_ids: list[str] = []
        if fact_key:
            for item in records:
                if item.get("status", "active") != "active":
                    continue
                if item.get("fact_key") != fact_key:
                    continue
                if item.get("normalized") == normalized:
                    continue
                item["status"] = "superseded"
                item["superseded_by"] = fact_id
                item["last_seen"] = now_iso
                prior_id = str(item.get("id", "")).strip()
                if prior_id:
                    superseded_ids.append(prior_id)

        new_record = {
            "id": fact_id,
            "text": text,
            "normalized": normalized,
            "type": fact_type,
            "confidence": confidence_value,
            "source": source_label,
            "created_at": now_iso,
            "last_seen": now_iso,
            "fact_key": fact_key,
            "supersedes": superseded_ids,
            "status": "active",
        }
        records.append(new_record)

        if not self._write_fact_index(records):
            return {"ok": False, "status": "write_error"}

        current = self.read_long_term()
        if not current:
            current = "# Long-term Memory\n\nDurable facts to keep across sessions.\n"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        metadata = f"type={fact_type}; confidence={confidence_value:.2f}; source={source_label}"
        if superseded_ids:
            metadata += f"; supersedes={','.join(superseded_ids)}"
        entry = f"- [{timestamp}] ({metadata}) {text}"
        updated = current.rstrip() + "\n" + entry + "\n"
        if not self._safe_write(self.memory_file, updated):
            return {"ok": False, "status": "write_error"}

        status = "superseded" if superseded_ids else "added"
        return {
            "ok": True,
            "status": status,
            "fact_id": fact_id,
            "superseded_ids": superseded_ids,
        }

    def append_long_term_fact(self, fact: str, category: str = "general") -> bool:
        """Backward-compatible wrapper for remember_fact."""
        result = self.remember_fact(fact=fact, category=category)
        return bool(result.get("ok")) and result.get("status") != "duplicate"

    def read_lessons(self) -> str:
        """Read lessons learned (LESSONS.md)."""
        return self._safe_read(self.lessons_file)

    def append_lesson(self, lesson: str, source: str = "user", severity: str = "medium") -> bool:
        """Append a lesson learned entry."""
        text = (lesson or "").strip()
        if not text:
            return False
        existing = self.read_lessons()
        if not existing:
            existing = (
                "# Lessons Learned\n\nActionable feedback and mistakes to avoid repeating.\n\n"
            )

        normalized = self._normalize_for_dedup(text)
        if normalized and normalized in self._normalize_for_dedup(existing):
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"- [{timestamp}] ({severity}/{source}) {text}"
        return self._safe_write(self.lessons_file, existing.rstrip() + "\n" + entry + "\n")

    def append_session_summary(self, session_key: str, summary: str) -> bool:
        """Append a compact session summary entry."""
        text = (summary or "").strip()
        if not text:
            return False

        existing = self.read_summaries()
        if not existing:
            existing = "# Session Summaries\n\n"

        normalized = self._normalize_for_dedup(text)
        if normalized and normalized in self._normalize_for_dedup(existing):
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"## {timestamp} ({session_key})\n- {text}"
        return self._safe_write(self.summaries_file, existing.rstrip() + "\n" + entry + "\n")

    def get_recent_memories(self, days: int = 7) -> str:
        """
        Get memories from the last N days.

        Args:
            days: Number of days to look back.

        Returns:
            Combined memory content.
        """
        from datetime import timedelta

        memories = []
        today = datetime.now().date()

        for i in range(days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            file_path = self.memory_dir / f"{date_str}.md"

            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                memories.append(content)

        return "\n\n---\n\n".join(memories)

    def list_memory_files(self) -> list[Path]:
        """List all memory files sorted by date (newest first)."""
        if not self.memory_dir.exists():
            return []

        files = list(self.memory_dir.glob("????-??-??.md"))
        return sorted(files, reverse=True)

    def list_custom_memory_files(self) -> list[Path]:
        """List non-core markdown files in memory dir."""
        if not self.memory_dir.exists():
            return []
        files: list[Path] = []
        for file_path in sorted(self.memory_dir.glob("*.md")):
            name = file_path.name
            if name in self.CORE_MEMORY_FILES:
                continue
            if re.match(r"^\d{4}-\d{2}-\d{2}\.md$", name):
                continue
            files.append(file_path)
        return files

    def _read_custom_memory_sections(
        self,
        max_files: int = 8,
        max_chars_per_file: int = 2800,
    ) -> str:
        """Read custom memory markdown files as labeled sections."""
        sections: list[str] = []
        for file_path in self.list_custom_memory_files()[:max_files]:
            content = self._safe_read(file_path).strip()
            if not content:
                continue
            if len(content) > max_chars_per_file:
                content = content[:max_chars_per_file].rstrip() + "\n..."
            sections.append(f"### {file_path.name}\n{content}")
        return "\n\n".join(sections)

    def _tokenize(self, text: str) -> set[str]:
        """Tokenize text for lightweight lexical matching."""
        normalized = self._semantic_normalize((text or "").replace("_", " "))
        tokens = re.findall(r"[a-zA-Z0-9]{3,}", normalized)
        canonical = [self.SEMANTIC_TOKEN_MAP.get(token, token) for token in tokens]
        return {token for token in canonical if token not in self.STOPWORDS}

    def _iter_memory_candidates(
        self,
        lookback_days: int = 30,
        scopes: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Collect memory candidates with score metadata."""
        from datetime import timedelta

        candidates: list[dict[str, Any]] = []
        active_scopes = scopes or {
            "profile",
            "relationships",
            "projects",
            "long-term",
            "lessons",
            "custom",
            "summary",
            "daily",
        }

        def add_candidate(
            source_label: str,
            text: str,
            age_days: int,
            source_type: str,
            confidence: float | None = None,
            metadata: dict[str, Any] | None = None,
        ) -> None:
            clean_text = (text or "").strip()
            if not clean_text or clean_text.startswith("#"):
                return
            if re.match(r"^[a-zA-Z0-9_ \-]+:\s*$", clean_text):
                return
            candidates.append(
                {
                    "source": source_label,
                    "text": clean_text,
                    "age_days": max(0, age_days),
                    "type": source_type,
                    "confidence": self._clamp_confidence(
                        confidence
                        if confidence is not None
                        else self.SOURCE_DEFAULT_CONFIDENCE.get(source_type, 0.72)
                    ),
                    "meta": metadata or {},
                }
            )

        if "profile" in active_scopes:
            for line in self.read_profile().splitlines():
                text = line.strip().lstrip("-* ").strip()
                add_candidate("profile", text, 0, "profile")

        if "relationships" in active_scopes:
            for line in self.read_relationships().splitlines():
                text = line.strip().lstrip("-* ").strip()
                add_candidate("relationships", text, 0, "relationships")

        if "projects" in active_scopes:
            for line in self.read_projects().splitlines():
                text = line.strip().lstrip("-* ").strip()
                add_candidate("projects", text, 0, "projects")

        if "long-term" in active_scopes:
            records = self._load_fact_index()
            for item in records:
                if item.get("status", "active") != "active":
                    continue
                fact_text = str(item.get("text", "")).strip()
                if not fact_text:
                    continue
                add_candidate(
                    source_label="long-term",
                    text=fact_text,
                    age_days=self._age_days(item.get("last_seen") or item.get("created_at")),
                    source_type="long-term",
                    confidence=self._clamp_confidence(item.get("confidence")),
                    metadata={
                        "fact_id": item.get("id", ""),
                        "fact_type": item.get("type", "general"),
                        "fact_source": item.get("source", "unknown"),
                    },
                )

        if "lessons" in active_scopes:
            lessons = self.read_lessons()
            if lessons:
                for line in lessons.splitlines():
                    text = line.strip().lstrip("-* ").strip()
                    add_candidate("lessons", text, 0, "lessons")

        if "summary" in active_scopes:
            summaries = self.read_summaries()
            if summaries:
                for line in summaries.splitlines():
                    text = line.strip().lstrip("-* ").strip()
                    add_candidate("summary", text, 0, "summary")

        if "custom" in active_scopes:
            for file_path in self.list_custom_memory_files():
                source_label = file_path.stem
                for line in self._safe_read(file_path).splitlines():
                    text = line.strip().lstrip("-* ").strip()
                    add_candidate(source_label, text, 0, "custom")

        if "daily" in active_scopes:
            today = datetime.now().date()
            for i in range(lookback_days):
                date = today - timedelta(days=i)
                date_str = date.strftime("%Y-%m-%d")
                file_path = self.memory_dir / f"{date_str}.md"
                if not file_path.exists():
                    continue
                for line in self._safe_read(file_path).splitlines():
                    text = line.strip().lstrip("-* ").strip()
                    add_candidate(date_str, text, i, "daily")

        return candidates

    def recall(
        self,
        query: str,
        max_items: int = 12,
        lookback_days: int = 30,
        scopes: list[str] | None = None,
        explain: bool = False,
    ) -> list[dict[str, Any]]:
        """Recall ranked memory snippets relevant to a query."""
        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        scope_set = {s.strip().lower() for s in (scopes or []) if s.strip()} if scopes else None
        scored: list[dict[str, Any]] = []
        seen: set[str] = set()

        for candidate in self._iter_memory_candidates(
            lookback_days=lookback_days,
            scopes=scope_set,
        ):
            source_label = candidate["source"]
            text = candidate["text"]
            age_days = int(candidate.get("age_days", 0))
            source_type = candidate["type"]
            confidence = self._clamp_confidence(candidate.get("confidence"))
            normalized = self._normalize_for_dedup(text)
            if not normalized or normalized in seen:
                continue

            text_terms = self._tokenize(text)
            overlap_terms = sorted(query_terms & text_terms)
            overlap = len(overlap_terms)
            if overlap == 0:
                continue

            seen.add(normalized)
            source_bonus = self.SOURCE_WEIGHTS.get(source_type, 100)
            lexical_ratio = overlap / max(1, len(query_terms))
            union_terms = max(1, len(query_terms | text_terms))
            semantic_similarity = overlap / union_terms
            recency_bonus = max(0.0, 40.0 - age_days * 1.5)

            score = int(
                overlap * 90
                + lexical_ratio * 70
                + semantic_similarity * 80
                + confidence * 70
                + recency_bonus
                + source_bonus * 0.2
            )

            item: dict[str, Any] = {
                "source": source_label,
                "type": source_type,
                "score": score,
                "text": text,
                "confidence": confidence,
                "age_days": age_days,
            }
            if candidate.get("meta"):
                item["meta"] = candidate["meta"]
            if explain:
                item["why"] = {
                    "overlap_terms": overlap_terms,
                    "overlap_count": overlap,
                    "lexical_ratio": round(lexical_ratio, 3),
                    "semantic_similarity": round(semantic_similarity, 3),
                    "confidence": round(confidence, 3),
                    "age_days": age_days,
                    "source_bonus": source_bonus,
                    "recency_bonus": round(recency_bonus, 2),
                }
            scored.append(item)

        scored.sort(
            key=lambda item: (
                -int(item.get("score", 0)),
                -float(item.get("confidence", 0.0)),
                int(item.get("age_days", 0)),
                str(item.get("source", "")),
                str(item.get("text", "")),
            )
        )
        return scored[:max_items]

    def get_relevant_memories(
        self,
        query: str,
        max_items: int = 12,
        lookback_days: int = 30,
        scopes: list[str] | None = None,
    ) -> str:
        """Get ranked memory snippets relevant to a query."""
        recalled = self.recall(
            query=query,
            max_items=max_items,
            lookback_days=lookback_days,
            scopes=scopes,
        )
        if not recalled:
            return ""

        lines = [f"- [{item['source']}] {item['text']}" for item in recalled]
        return "\n".join(lines)

    def _get_recent_activity(self, limit: int = 10) -> str:
        """Get compact recent activity lines from today's notes."""
        today = self.read_today()
        if not today:
            return ""

        entries = []
        for line in today.splitlines():
            text = line.strip()
            if text and not text.startswith("#"):
                entries.append(text)
        if not entries:
            return ""
        return "\n".join(entries[-limit:])

    def _get_recent_lessons(self, limit: int = 8) -> str:
        """Get recent lessons lines."""
        lessons = self.read_lessons()
        if not lessons:
            return ""

        entries = []
        for line in lessons.splitlines():
            text = line.strip()
            if text.startswith("- "):
                entries.append(text)
        if not entries:
            return ""
        return "\n".join(entries[-limit:])

    def _get_recent_summaries(self, limit: int = 6) -> str:
        """Get recent session summary bullets."""
        summaries = self.read_summaries()
        if not summaries:
            return ""

        entries = []
        for line in summaries.splitlines():
            text = line.strip()
            if text.startswith("- "):
                entries.append(text)
        if not entries:
            return ""
        return "\n".join(entries[-limit:])

    def _collect_scope_fact_entries(self, scopes: set[str]) -> list[dict[str, Any]]:
        """Collect key/value facts across selected memory scopes."""
        entries: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str, str]] = set()

        def add_entry(scope: str, source: str, text: str) -> None:
            body = (text or "").strip().lstrip("-* ").strip()
            if not body or body.startswith("#"):
                return
            key = self._extract_fact_key(body)
            if not key:
                return
            value = self._extract_fact_value(body)
            if not value:
                return
            value_norm = self._normalize_fact_value(value)
            if not value_norm:
                return
            signature = (scope, key, value_norm, body)
            if signature in seen:
                return
            seen.add(signature)
            entries.append(
                {
                    "scope": scope,
                    "source": source,
                    "key": key,
                    "value": value.strip(),
                    "value_normalized": value_norm,
                    "text": body,
                }
            )

        if "long-term" in scopes:
            for item in self._load_fact_index():
                if item.get("status", "active") != "active":
                    continue
                add_entry("long-term", "long-term", str(item.get("text", "")))

        if "profile" in scopes:
            for line in self.read_profile().splitlines():
                add_entry("profile", "profile", line)

        if "custom" in scopes:
            for file_path in self.list_custom_memory_files():
                source_name = file_path.stem
                for line in self._safe_read(file_path).splitlines():
                    add_entry("custom", source_name, line)

        if "projects" in scopes:
            for line in self.read_projects().splitlines():
                add_entry("projects", "projects", line)

        if "relationships" in scopes:
            for line in self.read_relationships().splitlines():
                add_entry("relationships", "relationships", line)

        return entries

    def detect_cross_scope_fact_conflicts(
        self,
        scopes: list[str] | None = None,
        limit: int = 80,
    ) -> list[dict[str, Any]]:
        """
        Detect conflicting fact values across memory scopes.

        Default scope set: profile + long-term + custom.
        """
        scope_set = (
            {item.strip().lower() for item in (scopes or []) if item.strip()}
            if scopes
            else {"profile", "long-term", "custom"}
        )
        if not scope_set:
            return []

        by_key: dict[str, list[dict[str, Any]]] = {}
        for entry in self._collect_scope_fact_entries(scope_set):
            by_key.setdefault(entry["key"], []).append(entry)

        conflicts: list[dict[str, Any]] = []
        for key in sorted(by_key.keys()):
            entries = by_key[key]
            if len(entries) < 2:
                continue
            unique_values = {item["value_normalized"] for item in entries}
            if len(unique_values) < 2:
                continue
            involved_scopes = {item["scope"] for item in entries}
            if len(involved_scopes) < 2:
                continue

            ordered = sorted(
                entries,
                key=lambda item: (
                    -self.SOURCE_WEIGHTS.get(item["scope"], 100),
                    item["scope"],
                    item["source"],
                    item["text"],
                ),
            )
            preferred = ordered[0]
            conflicting = [
                item
                for item in ordered
                if item["value_normalized"] != preferred["value_normalized"]
            ]
            if not conflicting:
                continue

            conflicts.append(
                {
                    "key": key,
                    "preferred_scope": preferred["scope"],
                    "preferred_source": preferred["source"],
                    "preferred_fact": preferred["text"],
                    "preferred_value": preferred["value"],
                    "scopes": sorted(involved_scopes),
                    "conflicting_facts": [
                        {
                            "scope": item["scope"],
                            "source": item["source"],
                            "text": item["text"],
                            "value": item["value"],
                        }
                        for item in conflicting
                    ],
                }
            )

        if limit > 0:
            return conflicts[:limit]
        return conflicts

    def detect_summary_fact_drift(self, limit: int = 80) -> list[dict[str, Any]]:
        """
        Detect summary facts that conflict with active durable facts.

        Returns list entries containing:
        - key
        - summary_fact
        - active_fact
        - fact_id
        - summary_line
        """
        active_by_key: dict[str, dict[str, Any]] = {}
        for item in self._load_fact_index():
            if item.get("status", "active") != "active":
                continue
            key = str(item.get("fact_key", "")).strip()
            text = str(item.get("text", "")).strip()
            if not key or not text:
                continue
            active_by_key[key] = item

        if not active_by_key:
            return []

        summary_lines = [
            line.strip()
            for line in self.read_summaries().splitlines()
            if line.strip().startswith("- ")
        ]
        if limit > 0:
            summary_lines = summary_lines[-limit:]

        drifts: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()

        for line in summary_lines:
            body = line[2:].strip()
            if not body:
                continue

            fragments: list[str] = []
            fragments.extend(
                match.group(1).strip()
                for match in re.finditer(r"([a-zA-Z0-9_ \-]{2,40}\s*[:=]\s*[^;,.|]+)", body)
            )
            if not fragments:
                fragments = [body]

            for fragment in fragments:
                key = self._extract_fact_key(fragment)
                if not key:
                    continue
                active = active_by_key.get(key)
                if not active:
                    continue

                summary_value = self._extract_fact_value(fragment) or fragment
                summary_norm = self._normalize_fact_value(summary_value)
                active_text = str(active.get("text", "")).strip()
                active_value = self._extract_fact_value(active_text) or active_text
                active_norm = self._normalize_fact_value(active_value)
                if not summary_norm or not active_norm:
                    continue
                if summary_norm == active_norm:
                    continue
                if summary_norm in active_norm or active_norm in summary_norm:
                    continue

                signature = (key, summary_norm, active_norm)
                if signature in seen:
                    continue
                seen.add(signature)
                drifts.append(
                    {
                        "key": key,
                        "summary_fact": fragment,
                        "active_fact": active_text,
                        "fact_id": str(active.get("id", "")),
                        "summary_line": body,
                    }
                )

        return drifts

    def get_memory_context(self, query: str | None = None, include_full: bool = True) -> str:
        """
        Get memory context for the agent.

        Returns:
            Formatted memory context including long-term and recent memories.
        """
        parts = []

        if include_full:
            profile = self.read_profile()
            if profile:
                parts.append("## Profile\n" + profile)

            relationships = self.read_relationships()
            if relationships:
                parts.append("## Relationships\n" + relationships)

            projects = self.read_projects()
            if projects:
                parts.append("## Projects\n" + projects)

            # Long-term memory
            long_term = self.read_long_term()
            if long_term:
                parts.append("## Long-term Memory\n" + long_term)

            lessons = self.read_lessons()
            if lessons:
                parts.append("## Lessons Learned\n" + lessons)

            custom_memory = self._read_custom_memory_sections()
            if custom_memory:
                parts.append("## Additional Memory Files\n" + custom_memory)

            # Today's notes
            today = self.read_today()
            if today:
                parts.append("## Today's Notes\n" + today)
        else:
            if query:
                relevant = self.get_relevant_memories(query)
                if relevant:
                    parts.append("## Relevant Memories\n" + relevant)

            recent = self._get_recent_activity()
            if recent:
                parts.append("## Recent Activity\n" + recent)

            recent_lessons = self._get_recent_lessons()
            if recent_lessons:
                parts.append("## Recent Lessons\n" + recent_lessons)

            recent_summaries = self._get_recent_summaries()
            if recent_summaries:
                parts.append("## Recent Session Summaries\n" + recent_summaries)

        return "\n\n".join(parts) if parts else ""
