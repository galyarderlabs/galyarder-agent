"""Runtime checkpoint storage for agent task execution."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from g_agent.utils.helpers import ensure_dir


def _now_iso() -> str:
    return datetime.now().isoformat()


def _compact_preview(text: str, limit: int = 1200) -> str:
    compact = " ".join((text or "").split())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "..."


class TaskCheckpointStore:
    """Store task execution checkpoints in workspace/state/tasks."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.tasks_dir = ensure_dir(workspace / "state" / "tasks")

    def _task_path(self, task_id: str) -> Path:
        return self.tasks_dir / f"{task_id}.json"

    def _safe_read(self, path: Path) -> dict[str, Any] | None:
        try:
            if not path.exists():
                return None
            raw = path.read_text(encoding="utf-8")
            return json.loads(raw)
        except (OSError, json.JSONDecodeError):
            return None

    def _safe_write(self, path: Path, payload: dict[str, Any]) -> bool:
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        try:
            tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp_path.replace(path)
            return True
        except OSError:
            return False

    def start(
        self,
        *,
        kind: str,
        session_key: str,
        channel: str,
        chat_id: str,
        sender_id: str,
        input_text: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a checkpoint file for a running task and return task_id."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        task_id = f"{timestamp}-{uuid.uuid4().hex[:8]}"
        now = _now_iso()
        payload = {
            "task_id": task_id,
            "kind": kind,
            "status": "running",
            "session_key": session_key,
            "channel": channel,
            "chat_id": chat_id,
            "sender_id": sender_id,
            "created_at": now,
            "updated_at": now,
            "finished_at": None,
            "input_preview": _compact_preview(input_text),
            "output_preview": "",
            "error": "",
            "metadata": metadata or {},
            "events": [
                {
                    "at": now,
                    "event": "start",
                    "detail": "",
                }
            ],
        }
        self._safe_write(self._task_path(task_id), payload)
        return task_id

    def get(self, task_id: str) -> dict[str, Any] | None:
        """Read a checkpoint payload by task_id."""
        return self._safe_read(self._task_path(task_id))

    def append_event(self, task_id: str, event: str, detail: str = "") -> bool:
        """Append a task event and update timestamp."""
        path = self._task_path(task_id)
        payload = self._safe_read(path)
        if payload is None:
            return False
        now = _now_iso()
        payload.setdefault("events", []).append(
            {
                "at": now,
                "event": (event or "").strip() or "event",
                "detail": _compact_preview(detail, limit=240),
            }
        )
        payload["updated_at"] = now
        return self._safe_write(path, payload)

    def complete(
        self,
        task_id: str,
        output_text: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark a task checkpoint as successful."""
        path = self._task_path(task_id)
        payload = self._safe_read(path)
        if payload is None:
            return False
        now = _now_iso()
        payload["status"] = "ok"
        payload["updated_at"] = now
        payload["finished_at"] = now
        payload["output_preview"] = _compact_preview(output_text)
        payload["error"] = ""
        if metadata:
            merged = dict(payload.get("metadata", {}))
            merged.update(metadata)
            payload["metadata"] = merged
        payload.setdefault("events", []).append(
            {
                "at": now,
                "event": "complete",
                "detail": "",
            }
        )
        return self._safe_write(path, payload)

    def fail(
        self,
        task_id: str,
        error: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Mark a task checkpoint as failed."""
        path = self._task_path(task_id)
        payload = self._safe_read(path)
        if payload is None:
            return False
        now = _now_iso()
        payload["status"] = "error"
        payload["updated_at"] = now
        payload["finished_at"] = now
        payload["error"] = _compact_preview(error, limit=600)
        if metadata:
            merged = dict(payload.get("metadata", {}))
            merged.update(metadata)
            payload["metadata"] = merged
        payload.setdefault("events", []).append(
            {
                "at": now,
                "event": "error",
                "detail": payload["error"],
            }
        )
        return self._safe_write(path, payload)

    def latest_running_for_session(self, session_key: str) -> dict[str, Any] | None:
        """Get the latest running task for a session_key, if any."""
        latest: dict[str, Any] | None = None
        for path in sorted(self.tasks_dir.glob("*.json"), reverse=True):
            payload = self._safe_read(path)
            if not payload:
                continue
            if payload.get("session_key") != session_key:
                continue
            if payload.get("status") != "running":
                continue
            latest = payload
            break
        return latest

    def mark_resumed(self, task_id: str) -> bool:
        """Mark a running task as resumed."""
        path = self._task_path(task_id)
        payload = self._safe_read(path)
        if payload is None:
            return False
        now = _now_iso()
        metadata = dict(payload.get("metadata", {}))
        metadata["resume_count"] = int(metadata.get("resume_count", 0) or 0) + 1
        payload["metadata"] = metadata
        payload["updated_at"] = now
        payload.setdefault("events", []).append(
            {
                "at": now,
                "event": "resume",
                "detail": "",
            }
        )
        return self._safe_write(path, payload)
