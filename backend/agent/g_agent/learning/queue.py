"""Learning queue management for G-Agent."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from g_agent.learning.candidate import CandidateStatus, LearningCandidate

VALID_STATUSES: set[str] = {"pending", "approved", "rejected", "applied", "rolled_back"}


def _to_iso(value: datetime | None) -> str | None:
    """Serialize an optional datetime."""
    return value.isoformat() if value else None


def _from_iso(value: str | None) -> datetime | None:
    """Parse an optional datetime."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


class LearningQueue:
    """Stores and manages learning candidates awaiting owner review."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.db_path = workspace / "state" / "learning.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize or migrate the learning queue schema."""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS candidates (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    title TEXT NOT NULL,
                    rationale TEXT,
                    content_json TEXT NOT NULL,
                    diff_preview TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    applied_at TEXT,
                    source_session TEXT,
                    metadata_json TEXT
                )
                """
            )
            self._ensure_columns(conn)

    def _ensure_columns(self, conn: sqlite3.Connection) -> None:
        """Add columns introduced after the first learning queue slice."""
        existing = {row[1] for row in conn.execute("PRAGMA table_info(candidates)")}
        columns = {
            "diff_preview": "TEXT",
            "applied_at": "TEXT",
            "metadata_json": "TEXT",
        }
        for name, definition in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE candidates ADD COLUMN {name} {definition}")

    def add(self, candidate: LearningCandidate) -> bool:
        """Add a candidate to the queue."""
        try:
            with self._lock, sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO candidates (
                           id, kind, status, title, rationale, content_json,
                           diff_preview, created_at, applied_at, source_session, metadata_json
                       )
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        candidate.id,
                        candidate.kind,
                        candidate.status,
                        candidate.title,
                        candidate.rationale,
                        json.dumps(candidate.content),
                        candidate.diff_preview,
                        _to_iso(candidate.created_at),
                        _to_iso(candidate.applied_at),
                        candidate.source_session,
                        json.dumps(candidate.metadata),
                    ),
                )
            return True
        except Exception as exc:
            logger.error("Failed to add learning candidate: {}", exc)
            return False

    def list(self, status: str | None = None) -> list[LearningCandidate]:
        """List candidates, optionally filtered by status."""
        candidates: list[LearningCandidate] = []
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if status:
                cursor = conn.execute(
                    "SELECT * FROM candidates WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                )
            else:
                cursor = conn.execute("SELECT * FROM candidates ORDER BY created_at DESC")
            for row in cursor:
                candidates.append(self._row_to_candidate(row))
        return candidates

    def list_pending(self) -> list[LearningCandidate]:
        """List all pending candidates."""
        return self.list(status="pending")

    def get(self, candidate_id: str) -> LearningCandidate | None:
        """Get a candidate by ID."""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,))
            row = cursor.fetchone()
            return self._row_to_candidate(row) if row else None

    def update_status(
        self,
        candidate_id: str,
        status: CandidateStatus,
        *,
        applied_at: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Update candidate status, applied timestamp, and optional metadata."""
        if status not in VALID_STATUSES:
            return False
        candidate = self.get(candidate_id)
        if not candidate:
            return False
        merged_metadata = dict(candidate.metadata)
        if metadata:
            merged_metadata.update(metadata)
        effective_applied_at = applied_at if status == "applied" else candidate.applied_at
        try:
            with self._lock, sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """UPDATE candidates
                       SET status = ?, applied_at = ?, metadata_json = ?
                       WHERE id = ?""",
                    (
                        status,
                        _to_iso(effective_applied_at),
                        json.dumps(merged_metadata),
                        candidate_id,
                    ),
                )
            return cursor.rowcount > 0
        except Exception as exc:
            logger.error("Failed to update learning candidate {}: {}", candidate_id, exc)
            return False

    def update_content(
        self,
        candidate_id: str,
        content: dict[str, Any],
        *,
        diff_preview: str | None = None,
    ) -> bool:
        """Replace a pending/approved candidate content payload."""
        candidate = self.get(candidate_id)
        if not candidate or candidate.status in {"applied", "rolled_back"}:
            return False
        try:
            with self._lock, sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """UPDATE candidates
                       SET content_json = ?, diff_preview = ?
                       WHERE id = ?""",
                    (json.dumps(content), diff_preview, candidate_id),
                )
            return cursor.rowcount > 0
        except Exception as exc:
            logger.error("Failed to edit learning candidate {}: {}", candidate_id, exc)
            return False

    def _row_to_candidate(self, row: sqlite3.Row) -> LearningCandidate:
        """Deserialize a SQLite row."""
        return LearningCandidate(
            id=row["id"],
            kind=row["kind"],
            status=row["status"],
            title=row["title"],
            rationale=row["rationale"] or "",
            content=json.loads(row["content_json"]),
            diff_preview=row["diff_preview"],
            created_at=_from_iso(row["created_at"]) or datetime.now(),
            applied_at=_from_iso(row["applied_at"]),
            source_session=row["source_session"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )
