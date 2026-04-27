"""SQLite storage for G-Agent sessions."""

import json
import hashlib
import random
import re
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

from loguru import logger

T = TypeVar("T")

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    key TEXT UNIQUE, -- channel:chat_id
    channel TEXT,
    chat_id TEXT,
    user_id TEXT,
    title TEXT,
    character_id TEXT,
    parent_session_id TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    message_count INTEGER DEFAULT 0,
    tool_call_count INTEGER DEFAULT 0,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    input_cost REAL DEFAULT 0,
    output_cost REAL DEFAULT 0,
    total_cost REAL DEFAULT 0,
    metadata_json TEXT,
    FOREIGN KEY (parent_session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL,
    content TEXT,
    content_type TEXT, -- text, media, etc
    provider TEXT,
    model TEXT,
    created_at REAL NOT NULL,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    input_cost REAL DEFAULT 0,
    output_cost REAL DEFAULT 0,
    total_cost REAL DEFAULT 0,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    message_id INTEGER NOT NULL REFERENCES messages(id),
    tool_name TEXT NOT NULL,
    arguments_json TEXT,
    result_summary TEXT,
    status TEXT, -- success, failure, pending
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS media_refs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    message_id INTEGER REFERENCES messages(id),
    kind TEXT, -- image, audio, etc
    path TEXT,
    mime_type TEXT,
    sha256 TEXT,
    metadata_json TEXT,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_key ON sessions(key);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON tool_calls(session_id);
"""


def _sha256_file(path: Path) -> str | None:
    """Return sha256 for a local file path, or None when unavailable."""
    try:
        if not path.is_file():
            return None
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None

FTS_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content,
    content=messages,
    content_rowid=id
);

CREATE TRIGGER IF NOT EXISTS messages_fts_insert AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_delete AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
END;

CREATE TRIGGER IF NOT EXISTS messages_fts_update AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.id, old.content);
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;
"""

class SessionSQLiteStore:
    """
    SQLite-backed session storage with FTS5 search and JSONL migration support.
    """

    _WRITE_MAX_RETRIES = 15
    _WRITE_RETRY_MIN_S = 0.020
    _WRITE_RETRY_MAX_S = 0.150
    _CHECKPOINT_EVERY_N_WRITES = 50

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._write_count = 0
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            timeout=1.0,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize the database schema."""
        with self._lock:
            # Check current version
            cursor = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
            )
            if not cursor.fetchone():
                self._conn.execute("BEGIN IMMEDIATE")
                try:
                    self._conn.executescript(SCHEMA_SQL)
                    self._ensure_fts(self._conn)
                    self._conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
                    self._conn.commit()
                except Exception:
                    self._conn.rollback()
                    raise
            else:
                self._conn.execute("BEGIN IMMEDIATE")
                try:
                    self._ensure_columns(self._conn)
                    self._ensure_fts(self._conn)
                    existing = self._conn.execute("SELECT version FROM schema_version").fetchone()
                    if not existing:
                        self._conn.execute(
                            "INSERT INTO schema_version (version) VALUES (?)",
                            (SCHEMA_VERSION,),
                        )
                    self._conn.commit()
                except Exception:
                    self._conn.rollback()
                    raise

    def _ensure_columns(self, conn: sqlite3.Connection) -> None:
        """Add columns introduced after the first SQLite store release."""
        self._ensure_table_columns(
            conn,
            "sessions",
            {
                "character_id": "TEXT",
                "input_cost": "REAL DEFAULT 0",
                "output_cost": "REAL DEFAULT 0",
                "total_cost": "REAL DEFAULT 0",
            },
        )
        self._ensure_table_columns(
            conn,
            "messages",
            {
                "input_cost": "REAL DEFAULT 0",
                "output_cost": "REAL DEFAULT 0",
                "total_cost": "REAL DEFAULT 0",
            },
        )

    def _ensure_table_columns(
        self,
        conn: sqlite3.Connection,
        table: str,
        columns: dict[str, str],
    ) -> None:
        """Add missing columns to an existing table."""
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, definition in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    def _ensure_fts(self, conn: sqlite3.Connection) -> None:
        """Create FTS5 objects or fail clearly if SQLite lacks FTS support."""
        try:
            conn.executescript(FTS_SQL)
        except sqlite3.OperationalError as exc:
            logger.error("SQLite FTS5 is required for session search: {}", exc)
            raise RuntimeError("SQLite FTS5 is required for session search") from exc

    def _execute_write(self, fn: Callable[[sqlite3.Connection], T]) -> T:
        """Execute a write transaction with BEGIN IMMEDIATE and jitter retry."""
        last_err: Exception | None = None
        for attempt in range(self._WRITE_MAX_RETRIES):
            try:
                with self._lock:
                    self._conn.execute("BEGIN IMMEDIATE")
                    try:
                        result = fn(self._conn)
                        self._conn.commit()
                    except BaseException:
                        try:
                            self._conn.rollback()
                        except Exception:
                            pass
                        raise

                self._write_count += 1
                if self._write_count % self._CHECKPOINT_EVERY_N_WRITES == 0:
                    try:
                        self._conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
                    except Exception:
                        pass
                return result
            except sqlite3.OperationalError as exc:
                err_msg = str(exc).lower()
                if "locked" in err_msg or "busy" in err_msg:
                    last_err = exc
                    if attempt < self._WRITE_MAX_RETRIES - 1:
                        time.sleep(random.uniform(self._WRITE_RETRY_MIN_S, self._WRITE_RETRY_MAX_S))
                        continue
                raise
        raise last_err or sqlite3.OperationalError("Database is locked after max retries")

    def get_or_create_session(self, key: str) -> dict[str, Any]:
        """Get or create a session by its key (channel:chat_id)."""
        def _do(conn):
            cursor = conn.execute("SELECT * FROM sessions WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return dict(row)

            # Create new session
            import uuid
            session_id = str(uuid.uuid4())
            channel, chat_id = key.split(":", 1) if ":" in key else (key, "")
            now = time.time()

            conn.execute(
                """INSERT INTO sessions (id, key, channel, chat_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, key, channel, chat_id, now, now)
            )
            return {
                "id": session_id,
                "key": key,
                "channel": channel,
                "chat_id": chat_id,
                "created_at": now,
                "updated_at": now,
                "message_count": 0,
                "tool_call_count": 0,
            }

        return self._execute_write(_do)

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        content_type: str = "text",
        provider: str | None = None,
        model: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        metadata: dict[str, Any] | None = None
    ) -> int:
        """Append a message to a session and update session counters."""
        metadata_json = json.dumps(metadata) if metadata else None
        now = time.time()

        def _do(conn):
            cursor = conn.execute(
                """INSERT INTO messages (session_id, role, content, content_type, provider, model,
                                        created_at, input_tokens, output_tokens, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, role, content, content_type, provider, model, now, input_tokens, output_tokens, metadata_json)
            )
            msg_id = cursor.lastrowid

            # Update session
            conn.execute(
                """UPDATE sessions SET
                   message_count = message_count + 1,
                   input_tokens = input_tokens + ?,
                   output_tokens = output_tokens + ?,
                   updated_at = ?
                   WHERE id = ?""",
                (input_tokens, output_tokens, now, session_id)
            )
            return msg_id

        return self._execute_write(_do)

    def replace_messages(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        """Replace all messages for a session with the provided history."""
        now = time.time()

        def _do(conn: sqlite3.Connection) -> None:
            conn.execute("DELETE FROM media_refs WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM tool_calls WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))

            input_tokens = 0
            output_tokens = 0
            for msg in messages:
                msg_input_tokens = int(msg.get("input_tokens") or 0)
                msg_output_tokens = int(msg.get("output_tokens") or 0)
                input_tokens += msg_input_tokens
                output_tokens += msg_output_tokens
                metadata = msg.get("metadata")
                metadata_json = json.dumps(metadata) if metadata else None
                created_at = float(msg.get("raw_timestamp") or now)
                cursor = conn.execute(
                    """INSERT INTO messages (
                           session_id, role, content, content_type, provider, model,
                           created_at, input_tokens, output_tokens, metadata_json
                       )
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        session_id,
                        msg.get("role", "user"),
                        msg.get("content", ""),
                        msg.get("content_type", "text"),
                        msg.get("provider"),
                        msg.get("model"),
                        created_at,
                        msg_input_tokens,
                        msg_output_tokens,
                        metadata_json,
                    ),
                )
                message_id = int(cursor.lastrowid)

                msg_media = msg.get("media")
                if isinstance(msg_media, list):
                    for item in msg_media:
                        if not item:
                            continue
                        path = str(item)
                        sha256 = _sha256_file(Path(path))
                        conn.execute(
                            """INSERT INTO media_refs (
                                   session_id, message_id, kind, path, sha256, created_at
                               )
                               VALUES (?, ?, ?, ?, ?, ?)""",
                            (session_id, message_id, "media", path, sha256, created_at),
                        )

                msg_metadata = msg.get("metadata")
                tool_calls = (
                    msg_metadata.get("tool_calls")
                    if isinstance(msg_metadata, dict)
                    else None
                )
                if isinstance(tool_calls, list):
                    for call in tool_calls:
                        if not isinstance(call, dict):
                            continue
                        conn.execute(
                            """INSERT INTO tool_calls (
                                   session_id, message_id, tool_name, arguments_json,
                                   result_summary, status, created_at
                               )
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (
                                session_id,
                                message_id,
                                str(call.get("tool_name") or "unknown"),
                                json.dumps(call.get("arguments") or {}),
                                str(call.get("result_summary") or "")[:1000],
                                str(call.get("status") or "success"),
                                created_at,
                            ),
                        )

            title = ""
            for msg in messages:
                if msg.get("role") == "user" and str(msg.get("content") or "").strip():
                    title = " ".join(str(msg.get("content")).split())[:80]
                    break

            conn.execute(
                """UPDATE sessions SET
                       message_count = ?,
                       tool_call_count = (SELECT COUNT(*) FROM tool_calls WHERE session_id = ?),
                       input_tokens = ?,
                       output_tokens = ?,
                       title = COALESCE(NULLIF(title, ''), ?),
                       updated_at = ?
                   WHERE id = ?""",
                (len(messages), session_id, input_tokens, output_tokens, title, now, session_id),
            )

        self._execute_write(_do)

    def get_history(self, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Get message history for a session."""
        with self._lock:
            cursor = self._conn.execute(
                "SELECT role, content, content_type FROM messages WHERE session_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
                (session_id, limit)
            )
            rows = cursor.fetchall()
            # Return in chronological order
            return [dict(row) for row in reversed(rows)]

    def search_messages(
        self,
        query: str,
        limit: int = 20,
        *,
        channel: str | None = None,
        session_key: str | None = None,
        exclude_session_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """Full-text search across messages."""
        if not query or not query.strip():
            return []

        # FTS5 handles normal terms well, but punctuation-heavy URLs/paths need a
        # safe LIKE fallback so recall preserves exact operational artifacts.
        sanitized = re.sub(r'[+{}()\"^]', " ", query).strip()
        if not sanitized:
            return []

        filters = ["messages_fts MATCH ?"]
        params: list[Any] = [sanitized]
        if channel:
            filters.append("s.channel = ?")
            params.append(channel)
        if session_key:
            filters.append("s.key = ?")
            params.append(session_key)
        if exclude_session_key:
            filters.append("s.key != ?")
            params.append(exclude_session_key)
        params.append(limit)

        sql = f"""
            SELECT m.role, m.content, m.created_at, s.key as session_key, s.channel
            FROM messages_fts f
            JOIN messages m ON m.id = f.rowid
            JOIN sessions s ON s.id = m.session_id
            WHERE {" AND ".join(filters)}
            ORDER BY rank
            LIMIT ?
        """
        with self._lock:
            try:
                cursor = self._conn.execute(sql, params)
                rows = [dict(row) for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                rows = []
            if rows:
                return rows
            return self._search_messages_like(
                query,
                limit,
                channel=channel,
                session_key=session_key,
                exclude_session_key=exclude_session_key,
            )

    def _search_messages_like(
        self,
        query: str,
        limit: int,
        *,
        channel: str | None = None,
        session_key: str | None = None,
        exclude_session_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fallback search for punctuation-heavy commands, URLs, and paths."""
        terms = [term for term in re.split(r"\s+", query.strip()) if term]
        if not terms:
            return []

        filters = ["m.content LIKE ?" for _ in terms]
        params: list[Any] = [f"%{term}%" for term in terms]
        if channel:
            filters.append("s.channel = ?")
            params.append(channel)
        if session_key:
            filters.append("s.key = ?")
            params.append(session_key)
        if exclude_session_key:
            filters.append("s.key != ?")
            params.append(exclude_session_key)
        params.append(limit)

        cursor = self._conn.execute(
            f"""
            SELECT m.role, m.content, m.created_at, s.key as session_key, s.channel
            FROM messages m
            JOIN sessions s ON s.id = m.session_id
            WHERE {" AND ".join(filters)}
            ORDER BY m.created_at DESC, m.id DESC
            LIMIT ?
            """,
            params,
        )
        return [dict(row) for row in cursor.fetchall()]

    def list_sessions(self, limit: int = 50) -> list[dict[str, Any]]:
        """List recent sessions."""
        with self._lock:
            cursor = self._conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its associated data."""
        def _do(conn):
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM tool_calls WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM media_refs WHERE session_id = ?", (session_id,))
            cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return cursor.rowcount > 0

        return self._execute_write(_do)

    def delete_session_by_key(self, key: str) -> bool:
        """Delete a session and associated data by its public key."""
        def _do(conn: sqlite3.Connection) -> bool:
            cursor = conn.execute("SELECT id FROM sessions WHERE key = ?", (key,))
            row = cursor.fetchone()
            if not row:
                return False

            session_id = row["id"]
            conn.execute("DELETE FROM media_refs WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM tool_calls WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return True

        return self._execute_write(_do)
