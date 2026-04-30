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
    code: str  # applied, manual_review_required, unsupported, failed, not_found, invalid_status
    message: str
    candidate: LearningCandidate | None = None
    errors: list[str] = field(default_factory=list)


def apply_learning_candidate(workspace: Path, candidate_id: str) -> LearningApplyResult:
    """Apply a supported learning candidate to the workspace."""
    queue = LearningQueue(workspace)
    candidate = queue.get(candidate_id)
    if candidate is None:
        return LearningApplyResult(False, "not_found", "learning candidate not found")

    if candidate.status not in {"pending", "approved"}:
        return LearningApplyResult(
            False,
            "invalid_status",
            f"candidate cannot be applied from {candidate.status}",
            candidate=candidate,
        )

    if candidate.kind == "skill":
        return _apply_skill(workspace, candidate)
    elif candidate.kind == "memory":
        return _apply_memory(workspace, candidate)
    elif candidate.kind == "routine":
        return _apply_routine(workspace, candidate)
    elif candidate.kind == "tool_quirk":
        return _apply_tool_quirk(workspace, candidate)
    elif candidate.kind == "profile":
        return _apply_profile(workspace, candidate)
    elif candidate.kind == "relationship":
        return _apply_relationship(workspace, candidate)
    else:
        return LearningApplyResult(
            False,
            "unsupported_kind",
            f"applying {candidate.kind} candidates is not yet implemented",
            candidate=candidate,
        )


def _apply_skill(workspace: Path, candidate: LearningCandidate) -> LearningApplyResult:
    skill_name = candidate.content.get("name")
    if not isinstance(skill_name, str) or not skill_name.strip():
        return LearningApplyResult(
            False,
            "invalid_candidate",
            "skill candidate is missing name",
            candidate=candidate,
        )

    skills = SkillManager(workspace)
    queue = LearningQueue(workspace)
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
        activation_id=candidate.id,
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
        candidate.id,
        "applied",
        applied_at=datetime.now(),
        metadata={"skill_activation": metadata},
    )
    return LearningApplyResult(True, "applied", f"skill {skill_name} activated", candidate=queue.get(candidate.id))


def _apply_memory(workspace: Path, candidate: LearningCandidate) -> LearningApplyResult:
    """Apply memory candidate only if it contains explicit memory-like content."""
    queue = LearningQueue(workspace)
    text = str(candidate.content.get("text", ""))
    if not text:
        return LearningApplyResult(False, "invalid_content", "missing memory text")

    # Verify explicit memory directive is present
    lowered = text.lower()
    explicit_markers = (
        "remember that", "remember this", "ingat bahwa", "ingat ini",
        "my preference is", "i prefer", "preferensi saya",
        "always use", "selalu gunakan", "never use", "jangan pernah"
    )
    if not any(marker in lowered for marker in explicit_markers):
        return LearningApplyResult(
            False,
            "manual_review_required",
            "memory candidate lacks explicit directive, requires manual review",
            candidate=candidate,
        )

    # Import MemoryStore locally to avoid heavy module-level imports
    from g_agent.agent.memory import MemoryStore
    memory = MemoryStore(workspace)
    memory.append_today(text)
    queue.update_status(candidate.id, "applied", applied_at=datetime.now())
    return LearningApplyResult(True, "applied", "memory note appended to today", candidate=queue.get(candidate.id))


def _apply_routine(workspace: Path, candidate: LearningCandidate) -> LearningApplyResult:
    """Routine candidates require manual review - no auto-scaffolding."""
    return LearningApplyResult(
        False,
        "manual_review_required",
        "routine candidates require manual creation with validated schedule and action",
        candidate=candidate,
    )


def _apply_tool_quirk(workspace: Path, candidate: LearningCandidate) -> LearningApplyResult:
    """Tool quirks require manual review to determine proper workaround."""
    return LearningApplyResult(
        False,
        "manual_review_required",
        "tool quirk candidates require manual analysis to determine proper workaround strategy",
        candidate=candidate,
    )


def _apply_profile(workspace: Path, candidate: LearningCandidate) -> LearningApplyResult:
    """Profile changes require manual review - no auto-mutation of identity."""
    return LearningApplyResult(
        False,
        "manual_review_required",
        "profile candidates require manual review and explicit owner approval before identity mutation",
        candidate=candidate,
    )


def _apply_relationship(workspace: Path, candidate: LearningCandidate) -> LearningApplyResult:
    """Relationship changes require manual review - no auto-mutation of relationship model."""
    return LearningApplyResult(
        False,
        "manual_review_required",
        "relationship candidates require manual review and explicit owner approval before relationship model mutation",
        candidate=candidate,
    )
