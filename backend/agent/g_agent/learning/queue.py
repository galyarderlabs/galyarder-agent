"""Learning queue management for G-Agent."""

import json
import sqlite3
import threading
from pathlib import Path
from typing import List, Optional

from loguru import logger
from g_agent.learning.candidate import LearningCandidate


class LearningQueue:
    """Stores and manages learning candidates awaiting owner review."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.db_path = workspace / "state" / "learning.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS candidates (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    title TEXT NOT NULL,
                    rationale TEXT,
                    content_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    source_session TEXT
                )
            """)

    def add(self, candidate: LearningCandidate) -> bool:
        """Add a candidate to the queue."""
        try:
            with self._lock, sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO candidates (id, kind, status, title, rationale, content_json, source_session) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        candidate.id,
                        candidate.kind,
                        candidate.status,
                        candidate.title,
                        candidate.rationale,
                        json.dumps(candidate.content),
                        candidate.source_session,
                    ),
                )
            return True
        except Exception as e:
            logger.error(f"Failed to add learning candidate: {e}")
            return False

    def list_pending(self) -> List[LearningCandidate]:
        """List all pending candidates."""
        candidates = []
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM candidates WHERE status = 'pending' ORDER BY created_at DESC"
            )
            for row in cursor:
                candidates.append(self._row_to_candidate(row))
        return candidates

    def get(self, candidate_id: str) -> Optional[LearningCandidate]:
        """Get a candidate by ID."""
        with self._lock, sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,))
            row = cursor.fetchone()
            return self._row_to_candidate(row) if row else None

    def update_status(self, candidate_id: str, status: str) -> bool:
        """Update the status of a candidate."""
        try:
            with self._lock, sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE candidates SET status = ? WHERE id = ?", (status, candidate_id)
                )
            return True
        except Exception:
            return False

    def _row_to_candidate(self, row: sqlite3.Row) -> LearningCandidate:
        return LearningCandidate(
            id=row["id"],
            kind=row["kind"],
            status=row["status"],
            title=row["title"],
            rationale=row["rationale"],
            content=json.loads(row["content_json"]),
            source_session=row["source_session"],
        )
