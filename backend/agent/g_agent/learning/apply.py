"""Apply owner-reviewed learning candidates."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from g_agent.learning.candidate import LearningCandidate
from g_agent.learning.queue import LearningQueue
from g_agent.skills.manager import SkillManager


@dataclass
class LearningApplyResult:
    """Result from applying a learning candidate."""

    ok: bool
    code: str
    message: str
    candidate: LearningCandidate | None = None
    errors: list[str] = field(default_factory=list)


def apply_learning_candidate(workspace: Path, candidate_id: str) -> LearningApplyResult:
    """Apply a supported learning candidate to the workspace."""
    queue = LearningQueue(workspace)
    candidate = queue.get(candidate_id)
    if candidate is None:
        return LearningApplyResult(False, "not_found", "learning candidate not found")
    if candidate.kind != "skill":
        return LearningApplyResult(
            False,
            "unsupported_kind",
            "applying learning candidates currently supports skill candidates only",
            candidate=candidate,
        )
    if candidate.status not in {"pending", "approved"}:
        return LearningApplyResult(
            False,
            "invalid_status",
            f"candidate cannot be applied from {candidate.status}",
            candidate=candidate,
        )

    skill_name = candidate.content.get("name")
    if not isinstance(skill_name, str) or not skill_name.strip():
        return LearningApplyResult(
            False,
            "invalid_candidate",
            "skill candidate is missing name",
            candidate=candidate,
        )

    skills = SkillManager(workspace)
    draft_content = candidate.content.get("content") or candidate.content.get("skill_md")
    if isinstance(draft_content, str) and not skills.store.get_skill_path(
        skill_name, location="draft"
    ):
        ok, errors = skills.create_draft(skill_name, draft_content)
        if not ok:
            return LearningApplyResult(
                False,
                "draft_validation_failed",
                "skill draft validation failed",
                candidate=candidate,
                errors=errors,
            )

    ok, errors, metadata = skills.activate_skill_with_metadata(
        skill_name,
        activation_id=candidate_id,
    )
    if not ok:
        return LearningApplyResult(
            False,
            "activation_failed",
            "skill activation failed",
            candidate=candidate,
            errors=errors,
        )

    queue.update_status(
        candidate_id,
        "applied",
        applied_at=datetime.now(),
        metadata={"skill_activation": metadata},
    )
    updated = queue.get(candidate_id)
    return LearningApplyResult(
        True,
        "applied",
        f"candidate {candidate_id} applied and skill {skill_name} activated",
        candidate=updated,
    )
