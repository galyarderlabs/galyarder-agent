"""Tests for owner-facing skill commands."""

import asyncio
import json
from pathlib import Path

from g_agent.channels.slash_commands import SlashCommandDispatcher
from g_agent.command.builtin import cmd_skills
from g_agent.command.context import CommandContext
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
description: Test skill command coverage.
---
# {name}

{body}
"""


def test_skills_command_lists_and_views_drafts(tmp_path: Path):
    manager = SkillManager(tmp_path)
    ok, errors = manager.create_draft("release", _skill_md("release", "draft body"))
    assert ok, errors

    listed = asyncio.run(cmd_skills(_ctx(tmp_path, "list drafts")))
    viewed = asyncio.run(cmd_skills(_ctx(tmp_path, "view release draft")))

    assert "release" in listed
    assert "draft body" in viewed


def test_skills_command_patches_draft_with_validation_rollback(tmp_path: Path):
    manager = SkillManager(tmp_path)
    original = _skill_md("release", "old body")
    ok, errors = manager.create_draft("release", original)
    assert ok, errors

    valid_payload = {
        "find": "old body",
        "replace": "new body",
    }

    valid_result = asyncio.run(
        cmd_skills(_ctx(tmp_path, f"patch-draft release {json.dumps(valid_payload)}"))
    )

    assert "patched and validated" in valid_result
    skill_md = tmp_path / "state" / "skills" / "drafts" / "release" / "SKILL.md"
    assert "new body" in skill_md.read_text(encoding="utf-8")

    payload = {
        "find": "description: Test skill command coverage.",
        "replace": "summary: invalid skill.",
    }

    result = asyncio.run(cmd_skills(_ctx(tmp_path, f"patch-draft release {json.dumps(payload)}")))

    assert "rolled back" in result
    assert "new body" in skill_md.read_text(encoding="utf-8")


def test_slash_dispatcher_routes_skills_command(tmp_path: Path):
    manager = SkillManager(tmp_path)
    ok, errors = manager.create_draft("release", _skill_md("release", "draft body"))
    assert ok, errors

    dispatcher = SlashCommandDispatcher(tmp_path)
    result = asyncio.run(dispatcher.try_handle("/skills list drafts", "cli:default", "cli", "default"))

    assert "release" in result
