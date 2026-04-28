"""Background learning reviewer heuristics."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from g_agent.learning.candidate import LearningCandidate
from g_agent.learning.queue import LearningQueue


@dataclass(frozen=True)
class LearningReviewInput:
    """Input captured after a completed turn."""

    session_key: str
    user_content: str
    assistant_content: str
    tool_calls: list[dict[str, str]] = field(default_factory=list)


class BackgroundLearningReviewer:
    """Deterministic first slice for owner-reviewed learning proposals."""

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.queue = LearningQueue(workspace)

    def review_turn(self, review: LearningReviewInput) -> list[LearningCandidate]:
        """Build learning candidates from a completed turn."""
        candidates: list[LearningCandidate] = []
        for candidate in (
            self._memory_candidate(review),
            self._tool_quirk_candidate(review),
            self._skill_candidate(review),
        ):
            if candidate:
                candidates.append(candidate)
        return candidates

    def enqueue_turn(self, review: LearningReviewInput) -> list[LearningCandidate]:
        """Review a turn and enqueue new candidates, deduped by evidence hash."""
        existing_hashes = {
            str(candidate.metadata.get("evidence_hash", ""))
            for candidate in self.queue.list()
            if candidate.metadata.get("evidence_hash")
        }
        added: list[LearningCandidate] = []
        for candidate in self.review_turn(review):
            evidence_hash = str(candidate.metadata.get("evidence_hash", ""))
            if evidence_hash in existing_hashes:
                continue
            if self.queue.add(candidate):
                existing_hashes.add(evidence_hash)
                added.append(candidate)
        return added

    def _memory_candidate(self, review: LearningReviewInput) -> LearningCandidate | None:
        text = review.user_content.strip()
        lowered = text.lower()
        triggers = ("remember ", "ingat ", "prefer ", "preference", "biasanya", "selalu")
        if not text or not any(trigger in lowered for trigger in triggers):
            return None
        return self._candidate(
            review,
            kind="memory",
            title="Review possible memory update",
            rationale="User phrasing suggests a durable preference or fact.",
            content={"text": text, "source": "background_reviewer"},
            diff_preview=f"Proposed memory note:\n{text}",
        )

    def _tool_quirk_candidate(self, review: LearningReviewInput) -> LearningCandidate | None:
        failures = [
            item for item in review.tool_calls if item.get("status") == "failure" and item.get("tool_name")
        ]
        if not failures:
            return None
        first = failures[0]
        tool_name = first.get("tool_name", "unknown")
        result = first.get("result_summary", "")
        return self._candidate(
            review,
            kind="tool_quirk",
            title=f"Review recurring tool quirk: {tool_name}",
            rationale="A tool call failed and may need a remembered workaround.",
            content={"tool": tool_name, "failure": result, "source": "background_reviewer"},
            diff_preview=f"Tool quirk candidate for {tool_name}:\n{result}",
        )

    def _skill_candidate(self, review: LearningReviewInput) -> LearningCandidate | None:
        successful_tools = [
            item for item in review.tool_calls if item.get("status") == "success" and item.get("tool_name")
        ]
        if len(successful_tools) < 3:
            return None
        names = [item["tool_name"] for item in successful_tools[:6]]
        slug = "-".join(dict.fromkeys(names))[:48] or "tool-workflow"
        skill_md = (
            "---\n"
            f"name: {slug}\n"
            "description: Draft workflow proposed from a tool-heavy completed turn.\n"
            "---\n"
            f"# {slug}\n\n"
            "Review this draft before activation.\n\n"
            "## Observed Tool Sequence\n"
            + "\n".join(f"- {name}" for name in names)
            + "\n"
        )
        return self._candidate(
            review,
            kind="skill",
            title=f"Review possible reusable skill: {slug}",
            rationale="A tool-heavy successful turn may be reusable as procedural memory.",
            content={"name": slug, "skill_md": skill_md, "source": "background_reviewer"},
            diff_preview=f"Draft skill proposed from tools: {', '.join(names)}",
        )

    def _candidate(
        self,
        review: LearningReviewInput,
        *,
        kind: str,
        title: str,
        rationale: str,
        content: dict[str, str],
        diff_preview: str,
    ) -> LearningCandidate:
        evidence_hash = self._evidence_hash(review, kind, diff_preview)
        return LearningCandidate(
            id=f"review-{evidence_hash[:16]}",
            kind=kind,
            title=title,
            rationale=rationale,
            content=content,
            diff_preview=diff_preview,
            source_session=review.session_key,
            metadata={"source": "background_reviewer", "evidence_hash": evidence_hash},
        )

    @staticmethod
    def _evidence_hash(review: LearningReviewInput, kind: str, text: str) -> str:
        payload = "\n".join(
            [
                kind,
                review.session_key,
                review.user_content.strip(),
                review.assistant_content.strip(),
                text.strip(),
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
