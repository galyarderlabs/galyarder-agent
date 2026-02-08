"""Memory system for persistent agent memory."""

import re
from pathlib import Path
from datetime import datetime

from g_agent.utils.helpers import ensure_dir, today_date


class MemoryStore:
    """
    Memory system for the agent.
    
    Supports daily notes (memory/YYYY-MM-DD.md) and long-term memory (MEMORY.md).
    """
    STOPWORDS = {
        "the", "and", "for", "with", "that", "this", "from", "have", "your", "you",
        "are", "was", "were", "will", "can", "not", "just", "buat", "yang", "dan",
        "dari", "atau", "itu", "ini", "aja", "saya", "aku", "gua", "kamu", "nya",
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
    CORE_MEMORY_FILES = {
        "MEMORY.md",
        "LESSONS.md",
        "PROFILE.md",
        "RELATIONSHIPS.md",
        "PROJECTS.md",
        "SUMMARIES.md",
        "user_profile.md",
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
        self._ensure_scaffold()

    def _ensure_scaffold(self) -> None:
        """Create baseline memory files when missing."""
        templates = {
            self.memory_file: (
                "# Long-term Memory\n\n"
                "Durable facts to keep across sessions.\n"
            ),
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
            self.relationships_file: (
                "# Relationships\n\n"
                "- [name] role, context, preference\n"
            ),
            self.projects_file: (
                "# Projects\n\n"
                "## Active\n"
                "- [project] status: ; next: \n\n"
                "## Backlog\n"
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
            try:
                if self.profile_alias_file.is_symlink():
                    return
            except OSError:
                pass
            if profile_content and alias_content != profile_content:
                self._safe_write(self.profile_alias_file, profile_content)
            return

        try:
            self.profile_alias_file.symlink_to(self.profile_file.name)
            return
        except OSError:
            pass

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

    def append_long_term_fact(self, fact: str, category: str = "general") -> bool:
        """Append a durable fact to long-term memory, de-duplicated by exact text."""
        text = (fact or "").strip()
        if not text:
            return False
        current = self.read_long_term()
        if not current:
            current = "# Long-term Memory\n"

        normalized = self._normalize_for_dedup(text)
        if normalized and normalized in self._normalize_for_dedup(current):
            return False

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"- [{timestamp}] ({category}) {text}"
        updated = current.rstrip() + "\n" + entry + "\n"
        return self._safe_write(self.memory_file, updated)

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
                "# Lessons Learned\n\n"
                "Actionable feedback and mistakes to avoid repeating.\n\n"
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
        entry = (
            f"## {timestamp} ({session_key})\n"
            f"- {text}"
        )
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
        normalized = (text or "").lower().replace("_", " ")
        tokens = re.findall(r"[a-zA-Z0-9]{3,}", normalized)
        return {token for token in tokens if token not in self.STOPWORDS}

    def _iter_memory_candidates(
        self,
        lookback_days: int = 30,
        scopes: set[str] | None = None,
    ) -> list[tuple[str, str, int, str]]:
        """Collect memory candidates as (source_label, text, age_days, source_type)."""
        from datetime import timedelta

        candidates: list[tuple[str, str, int, str]] = []
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

        if "profile" in active_scopes:
            for line in self.read_profile().splitlines():
                text = line.strip().lstrip("-* ").strip()
                if text and not text.startswith("#"):
                    candidates.append(("profile", text, 0, "profile"))

        if "relationships" in active_scopes:
            for line in self.read_relationships().splitlines():
                text = line.strip().lstrip("-* ").strip()
                if text and not text.startswith("#"):
                    candidates.append(("relationships", text, 0, "relationships"))

        if "projects" in active_scopes:
            for line in self.read_projects().splitlines():
                text = line.strip().lstrip("-* ").strip()
                if text and not text.startswith("#"):
                    candidates.append(("projects", text, 0, "projects"))

        if "long-term" in active_scopes:
            long_term = self.read_long_term()
            if long_term:
                for line in long_term.splitlines():
                    text = line.strip().lstrip("-* ").strip()
                    if text and not text.startswith("#"):
                        candidates.append(("long-term", text, lookback_days, "long-term"))

        if "lessons" in active_scopes:
            lessons = self.read_lessons()
            if lessons:
                for line in lessons.splitlines():
                    text = line.strip().lstrip("-* ").strip()
                    if text and not text.startswith("#"):
                        candidates.append(("lessons", text, 0, "lessons"))

        if "summary" in active_scopes:
            summaries = self.read_summaries()
            if summaries:
                for line in summaries.splitlines():
                    text = line.strip().lstrip("-* ").strip()
                    if text and not text.startswith("#"):
                        candidates.append(("summary", text, 0, "summary"))

        if "custom" in active_scopes:
            for file_path in self.list_custom_memory_files():
                source_label = file_path.stem
                for line in self._safe_read(file_path).splitlines():
                    text = line.strip().lstrip("-* ").strip()
                    if text and not text.startswith("#"):
                        candidates.append((source_label, text, 0, "custom"))

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
                    if text and not text.startswith("#"):
                        candidates.append((date_str, text, i, "daily"))

        return candidates

    def recall(
        self,
        query: str,
        max_items: int = 12,
        lookback_days: int = 30,
        scopes: list[str] | None = None,
    ) -> list[dict[str, str | int]]:
        """Recall ranked memory snippets relevant to a query."""
        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        scope_set = {s.strip().lower() for s in (scopes or []) if s.strip()} if scopes else None
        scored: list[tuple[int, str, str, str]] = []
        seen: set[str] = set()

        for source_label, text, age_days, source_type in self._iter_memory_candidates(
            lookback_days=lookback_days,
            scopes=scope_set,
        ):
            normalized = self._normalize_for_dedup(text)
            if not normalized or normalized in seen:
                continue

            overlap = len(query_terms & self._tokenize(text))
            if overlap == 0:
                continue

            seen.add(normalized)
            source_bonus = self.SOURCE_WEIGHTS.get(source_type, 100)
            score = overlap * 100 + source_bonus - age_days * 3
            scored.append((score, source_label, source_type, text))

        scored.sort(reverse=True)
        return [
            {"source": source_label, "type": source_type, "score": score, "text": text}
            for score, source_label, source_type, text in scored[:max_items]
        ]

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
