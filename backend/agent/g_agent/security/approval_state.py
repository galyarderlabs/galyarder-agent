"""Persisted approval state for risky tool calls."""

import json
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


ApprovalStatus = Literal["pending", "approved", "denied", "executed"]


class ApprovalRecord(BaseModel):
    """One persisted approval decision record."""

    id: str
    session_key: str
    tool_name: str
    tool_args: dict[str, Any] = Field(default_factory=dict)
    status: ApprovalStatus = "pending"
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    decision: str = ""


class ApprovalStateStore:
    """Append-only approval state store under workspace/state."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.path = workspace / "state" / "approvals.jsonl"

    def create_pending(
        self,
        *,
        session_key: str,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> ApprovalRecord:
        """Create and persist a pending approval."""
        record = ApprovalRecord(
            id=f"appr_{uuid.uuid4().hex[:12]}",
            session_key=session_key,
            tool_name=tool_name,
            tool_args=tool_args,
            status="pending",
        )
        self._append(record)
        return record

    def list(
        self,
        *,
        session_key: str | None = None,
        status: ApprovalStatus | None = None,
    ) -> list[ApprovalRecord]:
        """List latest approval records, optionally filtered."""
        records = list(self._latest().values())
        if session_key is not None:
            records = [record for record in records if record.session_key == session_key]
        if status is not None:
            records = [record for record in records if record.status == status]
        return sorted(records, key=lambda record: record.created_at)

    def get(self, approval_id: str) -> ApprovalRecord | None:
        """Get a latest approval record by id."""
        return self._latest().get(approval_id)

    def update_status(
        self,
        approval_id: str,
        status: ApprovalStatus,
        *,
        decision: str = "",
    ) -> ApprovalRecord | None:
        """Append a status update for one approval."""
        current = self.get(approval_id)
        if current is None:
            return None
        updated = current.model_copy(
            update={
                "status": status,
                "decision": decision,
                "updated_at": time.time(),
            }
        )
        self._append(updated)
        return updated

    def _latest(self) -> dict[str, ApprovalRecord]:
        records: dict[str, ApprovalRecord] = {}
        if not self.path.exists():
            return records
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = ApprovalRecord.model_validate_json(line)
            except Exception:
                continue
            records[record.id] = record
        return records

    def _append(self, record: ApprovalRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.model_dump(), ensure_ascii=False) + "\n")
