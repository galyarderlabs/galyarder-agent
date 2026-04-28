"""Tests for owner-reviewed learning and skill lifecycle commands."""

import asyncio
import json
from pathlib import Path

from g_agent.command.builtin import cmd_learn
from g_agent.command.context import CommandContext
from g_agent.learning.candidate import LearningCandidate
from g_agent.learning.queue import LearningQueue
from g_agent.skills.manager import SkillManager


def _ctx(tmp_path: Path, args: str) -> CommandContext:
    return CommandContext(
        workspace=tmp_path,
        channel="cli",
        chat_id="default",
        session_key="cli:default",
        args=args,
    )


def _skill_md(name: str, body: str) -> str:
    return f"""---
name: {name}
description: Test skill for lifecycle coverage.
---
# {name}

{body}
"""


def test_learning_queue_preserves_edit_metadata_and_status(tmp_path: Path):
    queue = LearningQueue(tmp_path)
    candidate = LearningCandidate(
        id="cand-edit",
        kind="skill",
        title="Draft a skill",
        rationale="Repeated workflow",
        content={"name": "release", "content": _skill_md("release", "v1")},
        diff_preview="initial",
    )

    assert queue.add(candidate)
    updated = {"name": "release", "content": _skill_md("release", "v2")}
    assert queue.update_content("cand-edit", updated, diff_preview="owner edit")
    assert queue.update_status("cand-edit", "approved")

    reloaded = queue.get("cand-edit")
    assert reloaded is not None
    assert reloaded.content == updated
    assert reloaded.diff_preview == "owner edit"
    assert reloaded.status == "approved"


def test_learn_apply_and_rollback_new_skill(tmp_path: Path):
    queue = LearningQueue(tmp_path)
    queue.add(
        LearningCandidate(
            id="cand-new",
            kind="skill",
            title="Add release skill",
            rationale="Owner asked for release checklist reuse",
            content={"name": "release", "content": _skill_md("release", "new body")},
        )
    )

    apply_result = asyncio.run(cmd_learn(_ctx(tmp_path, "apply cand-new")))

    assert "applied" in apply_result
    active_skill = tmp_path / "skills" / "release" / "SKILL.md"
    assert active_skill.exists()
    assert "new body" in active_skill.read_text(encoding="utf-8")
    applied = queue.get("cand-new")
    assert applied is not None
    assert applied.status == "applied"
    assert applied.applied_at is not None
    assert applied.metadata["skill_activation"]["had_previous"] is False

    rollback_result = asyncio.run(cmd_learn(_ctx(tmp_path, "rollback cand-new")))

    assert "rolled back" in rollback_result
    assert not active_skill.exists()
    rolled_back = queue.get("cand-new")
    assert rolled_back is not None
    assert rolled_back.status == "rolled_back"


def test_learn_apply_and_rollback_existing_skill(tmp_path: Path):
    active_dir = tmp_path / "skills" / "release"
    active_dir.mkdir(parents=True)
    (active_dir / "SKILL.md").write_text(_skill_md("release", "old body"), encoding="utf-8")

    queue = LearningQueue(tmp_path)
    queue.add(
        LearningCandidate(
            id="cand-replace",
            kind="skill",
            title="Replace release skill",
            rationale="Owner edited procedure",
            content={"name": "release", "content": _skill_md("release", "new body")},
        )
    )

    apply_result = asyncio.run(cmd_learn(_ctx(tmp_path, "apply cand-replace")))

    assert "applied" in apply_result
    skill_md = active_dir / "SKILL.md"
    assert "new body" in skill_md.read_text(encoding="utf-8")
    applied = queue.get("cand-replace")
    assert applied is not None
    assert applied.metadata["skill_activation"]["had_previous"] is True

    rollback_result = asyncio.run(cmd_learn(_ctx(tmp_path, "rollback cand-replace")))

    assert "rolled back" in rollback_result
    assert "old body" in skill_md.read_text(encoding="utf-8")


def test_learn_edit_command_replaces_candidate_content(tmp_path: Path):
    queue = LearningQueue(tmp_path)
    queue.add(
        LearningCandidate(
            id="cand-json",
            kind="skill",
            title="Skill edit",
            rationale="Owner edit",
            content={"name": "release", "content": _skill_md("release", "old")},
        )
    )
    payload = {"name": "release", "content": _skill_md("release", "edited")}

    result = asyncio.run(cmd_learn(_ctx(tmp_path, f"edit cand-json {json.dumps(payload)}")))

    assert "updated" in result
    reloaded = queue.get("cand-json")
    assert reloaded is not None
    assert reloaded.content == payload


def test_skill_manager_patches_draft_atomically(tmp_path: Path):
    manager = SkillManager(tmp_path)
    ok, errors = manager.create_draft("release", _skill_md("release", "old body"))
    assert ok, errors

    ok, errors = manager.patch_draft("release", "old body", "new body")

    assert ok, errors
    skill_md = tmp_path / "state" / "skills" / "drafts" / "release" / "SKILL.md"
    assert "new body" in skill_md.read_text(encoding="utf-8")


def test_skill_manager_restores_draft_when_patch_breaks_validation(tmp_path: Path):
    manager = SkillManager(tmp_path)
    original = _skill_md("release", "old body")
    ok, errors = manager.create_draft("release", original)
    assert ok, errors

    ok, errors = manager.patch_draft(
        "release",
        "description: Test skill for lifecycle coverage.",
        "summary: missing required description.",
    )

    assert not ok
    assert any("description" in error for error in errors)
    skill_md = tmp_path / "state" / "skills" / "drafts" / "release" / "SKILL.md"
    assert skill_md.read_text(encoding="utf-8") == original
