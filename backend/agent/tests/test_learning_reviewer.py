"""Tests for background learning reviewer heuristics."""

from pathlib import Path
from typing import Any

import asyncio

from g_agent.agent.loop import AgentLoop
from g_agent.bus.queue import MessageBus
from g_agent.learning.queue import LearningQueue
from g_agent.learning.reviewer import BackgroundLearningReviewer, LearningReviewInput
from g_agent.providers.base import LLMProvider, LLMResponse


class DummyProvider(LLMProvider):
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> LLMResponse:
        return LLMResponse(content="ok")

    def get_default_model(self) -> str:
        return "dummy"


def test_learning_reviewer_proposes_memory_candidate(tmp_path: Path):
    reviewer = BackgroundLearningReviewer(tmp_path)
    review = LearningReviewInput(
        session_key="cli:default",
        user_content="remember I prefer short updates",
        assistant_content="noted",
    )

    candidates = reviewer.review_turn(review)

    assert len(candidates) == 1
    assert candidates[0].kind == "memory"
    assert candidates[0].source_session == "cli:default"
    assert candidates[0].metadata["source"] == "background_reviewer"


def test_learning_reviewer_proposes_tool_quirk_candidate(tmp_path: Path):
    reviewer = BackgroundLearningReviewer(tmp_path)
    review = LearningReviewInput(
        session_key="cli:default",
        user_content="run it",
        assistant_content="failed",
        tool_calls=[
            {
                "tool_name": "exec",
                "result_summary": "Error: command timed out",
                "status": "failure",
            }
        ],
    )

    candidates = reviewer.review_turn(review)

    assert candidates[0].kind == "tool_quirk"
    assert candidates[0].content["tool"] == "exec"


def test_learning_reviewer_proposes_skill_candidate_for_tool_heavy_turn(tmp_path: Path):
    reviewer = BackgroundLearningReviewer(tmp_path)
    review = LearningReviewInput(
        session_key="cli:default",
        user_content="ship this",
        assistant_content="done",
        tool_calls=[
            {"tool_name": "read_file", "result_summary": "ok", "status": "success"},
            {"tool_name": "apply_patch", "result_summary": "ok", "status": "success"},
            {"tool_name": "pytest", "result_summary": "ok", "status": "success"},
        ],
    )

    candidates = reviewer.review_turn(review)

    assert candidates[0].kind == "skill"
    assert "skill_md" in candidates[0].content
    assert "read_file" in candidates[0].content["skill_md"]


def test_learning_reviewer_dedupes_existing_evidence(tmp_path: Path):
    reviewer = BackgroundLearningReviewer(tmp_path)
    review = LearningReviewInput(
        session_key="cli:default",
        user_content="remember I prefer short updates",
        assistant_content="noted",
    )

    first = reviewer.enqueue_turn(review)
    second = reviewer.enqueue_turn(review)

    assert len(first) == 1
    assert second == []
    assert len(LearningQueue(tmp_path).list_pending()) == 1


def test_agent_loop_schedules_learning_review_when_enabled(tmp_path: Path):
    async def run_case() -> None:
        loop = AgentLoop(
            bus=MessageBus(),
            provider=DummyProvider(),
            workspace=tmp_path,
            enable_learning_review=True,
        )
        loop._schedule_learning_review(
            session_key="cli:default",
            user_content="remember I prefer short updates",
            assistant_content="noted",
            tool_calls=[],
        )
        await asyncio.sleep(0)
        await loop.shutdown()

    asyncio.run(run_case())

    pending = LearningQueue(tmp_path).list_pending()
    assert len(pending) == 1
    assert pending[0].kind == "memory"
