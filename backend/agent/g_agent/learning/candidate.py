"""Learning candidate model for G-Agent."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

CandidateKind = Literal["memory", "profile", "skill", "routine", "relationship", "tool_quirk"]
CandidateStatus = Literal["pending", "approved", "rejected", "applied", "rolled_back"]


class LearningCandidate(BaseModel):
    """
    A proposed improvement or addition to the agent's knowledge or behavior.
    """

    id: str
    kind: CandidateKind
    status: CandidateStatus = "pending"
    title: str
    rationale: str
    content: dict[str, Any]
    diff_preview: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    applied_at: datetime | None = None
    source_session: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
