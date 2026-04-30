"""Session management for conversation history."""

import json
import threading
import weakref
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from g_agent.session.sqlite_store import SessionSQLiteStore
from g_agent.utils.helpers import ensure_dir, get_data_path, safe_filename


@dataclass
class Session:
    """
    A conversation session.

    Stores messages in JSONL format for easy reading and persistence.
    """

    key: str  # channel:chat_id
    id: str | None = None  # SQLite session ID
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now().astimezone())
    updated_at: datetime = field(default_factory=lambda: datetime.now().astimezone())
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """Add a message to the session."""
        now = datetime.now().astimezone()
        msg = {
            "role": role,
            "content": content,
            "timestamp": now.isoformat(),
            "raw_timestamp": now.timestamp(),
            **kwargs,
        }
        self.messages.append(msg)
        self.updated_at = now

    def get_history(self, max_messages: int = 50) -> list[dict[str, Any]]:
        """
        Get message history for LLM context.

        Args:
            max_messages: Maximum messages to return.

        Returns:
            List of messages in LLM format.
        """
        # Get recent messages
        recent = (
            self.messages[-max_messages:] if len(self.messages) > max_messages else self.messages
        )

        # Convert to LLM format (just role and content)
        return [{"role": m["role"], "content": m["content"]} for m in recent]

    def clear(self) -> None:
        """Clear all messages in the session."""
        self.messages = []
        self.updated_at = datetime.now().astimezone()


class SessionManager:
    """
    Manages conversation sessions.

    Sessions are stored as JSONL files in the sessions directory.
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.sessions_dir = ensure_dir(get_data_path() / "sessions")
        self.sqlite_store = SessionSQLiteStore(self.sessions_dir / "sessions.db")
        self._cache: weakref.WeakValueDictionary[str, Session] = weakref.WeakValueDictionary()
        self._session_locks: weakref.WeakValueDictionary[str, threading.Lock] = (
            weakref.WeakValueDictionary()
        )
        self._global_lock = threading.Lock()

    def _get_lock(self, key: str) -> threading.Lock:
        with self._global_lock:
            lock = self._session_locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._session_locks[key] = lock
            return lock

    def _get_session_path(self, key: str) -> Path:
        """Get the file path for a session."""
        safe_key = safe_filename(key.replace(":", "_"))
        return self.sessions_dir / f"{safe_key}.jsonl"

    def get_or_create(self, key: str) -> Session:
        """
        Get an existing session or create a new one.

        Args:
            key: Session key (usually channel:chat_id).

        Returns:
            The session.
        """
        with self._get_lock(key):
            # Check cache
            if key in self._cache:
                return self._cache[key]

            # Try to load from disk
            session = self._load(key)

            # Sync with SQLite
            sqlite_session = self.sqlite_store.get_or_create_session(key)

            if session is None:
                session = Session(
                    key=key,
                    id=sqlite_session["id"],
                    created_at=datetime.fromtimestamp(sqlite_session["created_at"]).astimezone(),
                )
            else:
                session.id = sqlite_session["id"]

            self._cache[key] = session
            return session

    def fork(self, parent_key: str, new_key: str, title: str | None = None) -> Session:
        """
        Create a new session forked from an existing one.

        Args:
            parent_key: Key of the parent session.
            new_key: Key for the new session.
            title: Optional title for the new session.

        Returns:
            The new session.
        """
        parent = self.get_or_create(parent_key)
        if not parent.id:
            # Ensure parent has an ID in SQLite
            self.save(parent)

        channel, chat_id = new_key.split(":", 1) if ":" in new_key else ("cli", new_key)

        with self._get_lock(new_key):
            sqlite_session = self.sqlite_store.fork_session(
                parent_id=parent.id,
                key=new_key,
                channel=channel,
                chat_id=chat_id,
                title=title,
                character_id=parent.metadata.get("current_profile_id"),
                metadata=parent.metadata.copy(),
            )

            # Create the session object
            session = Session(
                key=new_key,
                id=sqlite_session["id"],
                metadata=parent.metadata.copy(),
            )
            if title:
                session.metadata["title"] = title

            # Copy messages (deep copy to avoid shared references)
            session.messages = [m.copy() for m in parent.messages]

            # Save to disk as well
            self.save(session)
            self._cache[new_key] = session
            return session

    def _load(self, key: str) -> Session | None:
        """Load a session from disk."""
        path = self._get_session_path(key)

        if not path.exists():
            return None

        try:
            messages = []
            metadata = {}
            created_at = None

            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    data = json.loads(line)

                    if data.get("_type") == "metadata":
                        metadata = data.get("metadata", {})
                        created_at = (
                            datetime.fromisoformat(data["created_at"])
                            if data.get("created_at")
                            else None
                        )
                    else:
                        messages.append(data)

            return Session(
                key=key,
                messages=messages,
                created_at=created_at or datetime.now().astimezone(),
                metadata=metadata,
            )
        except Exception as e:
            logger.warning(f"Failed to load session {key}: {e}")
            return None

    def save(self, session: Session) -> None:
        """Save a session to disk."""
        path = self._get_session_path(session.key)

        with self._get_lock(session.key):
            with open(path, "w") as f:
                # Write metadata first
                metadata_line = {
                    "_type": "metadata",
                    "created_at": session.created_at.isoformat(),
                    "updated_at": session.updated_at.isoformat(),
                    "metadata": session.metadata,
                }
                f.write(json.dumps(metadata_line) + "\n")

                # Write messages
                for msg in session.messages:
                    f.write(json.dumps(msg) + "\n")

            sqlite_session = self.sqlite_store.get_or_create_session(session.key)
            session.id = sqlite_session["id"]
            self.sqlite_store.replace_messages(session.id, session.messages, metadata=session.metadata)

            self._cache[session.key] = session

    def delete(self, key: str) -> bool:
        """
        Delete a session.

        Args:
            key: Session key.

        Returns:
            True if deleted, False if not found.
        """
        with self._get_lock(key):
            # Remove from cache
            self._cache.pop(key, None)

            deleted = self.sqlite_store.delete_session_by_key(key)

            path = self._get_session_path(key)
            if path.exists():
                path.unlink()
                deleted = True
            return deleted

    def list_sessions(self) -> list[dict[str, Any]]:
        """
        List all sessions.

        Returns:
            List of session info dicts.
        """
        sessions = []

        for path in self.sessions_dir.glob("*.jsonl"):
            try:
                # Read just the metadata line
                with open(path) as f:
                    first_line = f.readline().strip()
                    if first_line:
                        data = json.loads(first_line)
                        if data.get("_type") == "metadata":
                            sessions.append(
                                {
                                    "key": path.stem.replace("_", ":"),
                                    "created_at": data.get("created_at"),
                                    "updated_at": data.get("updated_at"),
                                    "path": str(path),
                                }
                            )
            except (OSError, json.JSONDecodeError):
                continue

        return sorted(sessions, key=lambda x: x.get("updated_at", ""), reverse=True)

    def archive(self, key: str) -> bool:
        """Archive session (extract memory digest, copy to archive dir, then delete)."""
        import shutil

        path = self._get_session_path(key)
        if not path.exists():
            return False

        # Extract memory digest before wiping
        session = self.get_or_create(key)
        if session.messages:
            self._extract_and_save_digest(session)

        archive_dir = self.sessions_dir / "archive"
        archive_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_key = safe_filename(key.replace(":", "_"))
        archive_path = archive_dir / f"{safe_key}_{timestamp}.jsonl"
        shutil.copy2(path, archive_path)
        self.delete(key)
        return True

    def _extract_and_save_digest(self, session: Session) -> None:
        """Extract conversation highlights and append to memory/INBOX.md."""
        digest = self._build_digest(session)
        if not digest:
            return

        memory_dir = self.workspace / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        inbox_path = memory_dir / "INBOX.md"

        header = (
            f"\n---\n## Session: {session.key} "
            f"({session.created_at.strftime('%Y-%m-%d %H:%M')} → "
            f"{session.updated_at.strftime('%Y-%m-%d %H:%M')})\n\n"
        )

        try:
            with open(inbox_path, "a", encoding="utf-8") as f:
                f.write(header)
                f.write(digest)
                f.write("\n")
            logger.info(f"Memory digest saved for session '{session.key}'")
        except OSError as e:
            logger.warning(f"Failed to save memory digest for '{session.key}': {e}")

    @staticmethod
    def _build_digest(session: Session, max_chars: int = 2000) -> str:
        """Build a structured digest from session messages.

        Instead of dumping raw messages, extracts:
        - Key facts the user shared (names, timezone, preferences)
        - Topics discussed
        - Recent context (last few exchanges for continuity)
        """
        user_messages: list[str] = []
        assistant_messages: list[str] = []

        for msg in session.messages:
            role = msg.get("role", "")
            content = (msg.get("content") or "").strip()
            if not content or content.startswith("[silent"):
                continue
            if role == "user":
                user_messages.append(content)
            elif role == "assistant":
                assistant_messages.append(content)

        if not user_messages:
            return ""

        parts: list[str] = []

        # Section 1: Stats
        parts.append(f"**Messages**: {len(user_messages)} user, {len(assistant_messages)} AI")

        # Section 2: All user messages (compact, truncated per-message)
        parts.append("\n### User said")
        for msg in user_messages:
            line = msg.replace("\n", " ").strip()
            if len(line) > 150:
                line = line[:147] + "..."
            parts.append(f"- {line}")

        # Section 3: Last 5 exchanges for recent context
        pairs: list[str] = []
        tail = list(zip(user_messages[-5:], assistant_messages[-5:]))
        if tail:
            parts.append("\n### Recent exchanges")
            for u, a in tail:
                u_short = u[:120] + "..." if len(u) > 120 else u
                a_short = a[:200] + "..." if len(a) > 200 else a
                pairs.append(f"- **U**: {u_short}\n  **A**: {a_short}")
            parts.extend(pairs)

        result = "\n".join(parts)

        # Hard cap
        if len(result) > max_chars:
            result = result[:max_chars].rsplit("\n", 1)[0]
            result += "\n- *(truncated)*"

        return result

    def archive_all(self) -> int:
        """Archive all sessions. Returns count archived."""
        count = 0
        for info in self.list_sessions():
            if self.archive(info.get("key", "")):
                count += 1
        return count
