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
    channel: str = "cli"
    chat_id: str = "direct"
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
            self._routine_candidate(review),
            self._profile_candidate(review),
            self._relationship_candidate(review),
        ):
            if candidate:
                candidates.append(candidate)
        return candidates

    def _profile_candidate(self, review: LearningReviewInput) -> LearningCandidate | None:
        """Heuristic for identity/persona changes - requires explicit directive."""
        user_text = review.user_content.strip().lower()
        assistant_text = review.assistant_content.strip()

        # Require explicit user directive for profile changes
        explicit_triggers = (
            "change your name to",
            "call yourself",
            "your new name is",
            "rename yourself",
            "ganti nama kamu jadi",
            "namamu sekarang",
        )
        if not any(trigger in user_text for trigger in explicit_triggers):
            return None

        return self._candidate(
            review,
            kind="profile",
            title="Review explicit identity update",
            rationale="User explicitly requested agent name/identity change.",
            content={"text": review.user_content, "assistant_acknowledgment": assistant_text, "source": "background_reviewer"},
            diff_preview=f"User directive: {review.user_content}\nAgent acknowledgment: {assistant_text}",
        )

    def _relationship_candidate(self, review: LearningReviewInput) -> LearningCandidate | None:
        """Heuristic for relationship model updates - requires explicit definition."""
        text = review.user_content.strip()
        lowered = text.lower()

        # Require explicit relationship definition, not casual mentions
        explicit_triggers = (
            "you are my",
            "kamu adalah",
            "our relationship is",
            "hubungan kita adalah",
            "treat me as your",
            "perlakukan saya sebagai",
        )
        if not any(trigger in lowered for trigger in explicit_triggers):
            return None

        # Filter out casual greetings and short phrases
        if len(text.split()) < 4:
            return None

        return self._candidate(
            review,
            kind="relationship",
            title="Review explicit relationship definition",
            rationale="User explicitly defined their relationship with the agent.",
            content={"text": text, "source": "background_reviewer"},
            diff_preview=f"Proposed relationship definition:\n{text}",
        )

    def _routine_candidate(self, review: LearningReviewInput) -> LearningCandidate | None:
        """Heuristic for routine tasks - requires explicit schedule + action."""
        text = review.user_content.strip()
        lowered = text.lower()

        # Require explicit recurring schedule markers
        schedule_triggers = ("every day", "every week", "every month", "setiap hari", "setiap minggu", "daily", "weekly")
        has_schedule = any(trigger in lowered for trigger in schedule_triggers)

        # Require time specification for routines (explicit markers only, avoid URL false positives)
        time_markers = ("at ", "jam ", "pukul ", "o'clock", " am", " pm")
        has_time = any(marker in lowered for marker in time_markers)

        # Must have both schedule and time to be a routine candidate
        if not (has_schedule and has_time):
            return None

        # Filter out questions and short phrases
        if "?" in text or len(text.split()) < 5:
            return None

        return self._candidate(
            review,
            kind="routine",
            title="Review explicit routine with schedule",
            rationale="User specified recurring schedule with time for a task.",
            content={"text": text, "source": "background_reviewer"},
            diff_preview=f"Proposed routine:\n{text}",
        )

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
        """Heuristic for memory - requires explicit remember/preference directive."""
        text = review.user_content.strip()
        lowered = text.lower()

        # Require explicit memory directives, not casual mentions
        explicit_triggers = (
            "remember that",
            "remember this",
            "ingat bahwa",
            "ingat ini",
            "my preference is",
            "i prefer",
            "preferensi saya",
            "always use",
            "selalu gunakan",
            "never use",
            "jangan pernah",
        )
        if not text or not any(trigger in lowered for trigger in explicit_triggers):
            return None

        # Filter out questions and very short statements
        if "?" in text or len(text.split()) < 5:
            return None

        return self._candidate(
            review,
            kind="memory",
            title="Review explicit memory directive",
            rationale="User explicitly requested to remember a preference or fact.",
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
        # Ensure channel/chat_id are captured for routine scaffolding
        merged_content = {
            **content,
            "channel": review.channel,
            "chat_id": review.chat_id,
        }
        return LearningCandidate(
            id=f"review-{evidence_hash[:16]}",
            kind=kind,
            title=title,
            rationale=rationale,
            content=merged_content,
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
