"""Learning candidate model for G-Agent."""

from datetime import datetime
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field


CandidateKind = Literal["memory", "profile", "skill", "routine", "relationship", "tool_quirk"]


class LearningCandidate(BaseModel):
    """
    A proposed improvement or addition to the agent's knowledge or behavior.
    """

    id: str
    kind: CandidateKind
    status: Literal["pending", "approved", "rejected", "applied"] = "pending"
    title: str
    rationale: str
    content: Dict[str, Any]  # The actual data to be updated/added
    diff_preview: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    applied_at: Optional[datetime] = None
    source_session: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
