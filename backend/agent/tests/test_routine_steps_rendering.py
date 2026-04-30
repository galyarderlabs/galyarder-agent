"""Test routine step metadata rendering in context builder."""

import pytest
from pathlib import Path
from g_agent.agent.context import ContextBuilder


@pytest.mark.asyncio
async def test_routine_steps_render_from_canonical_fields(tmp_path: Path):
    """Routine steps should render from name/content_prompt, not missing 'description'."""
    builder = ContextBuilder(tmp_path)

    metadata = {
        "routine_steps": [
            {
                "id": "step-1",
                "name": "Check inbox",
                "content_prompt": "List unread emails",
                "allowed_tools": ["gmail_list_threads"],
                "timeout_seconds": 30.0,
            },
            {
                "id": "step-2",
                "name": "Summarize",
                "content_prompt": "Summarize the inbox status",
                "completed": True,
            },
        ]
    }

    prompt = await builder.build_system_prompt(metadata=metadata)

    assert "Active Routine Workflow" in prompt
    assert "1. Check inbox" in prompt
    assert "2. Summarize [DONE]" in prompt
    assert "Prompt: List unread emails" in prompt
    assert "Tools: gmail_list_threads" in prompt
    assert "Timeout: 30.0s" in prompt
    # Should NOT render None or missing fields
    assert "None" not in prompt


@pytest.mark.asyncio
async def test_routine_steps_empty_list_no_section(tmp_path: Path):
    """Empty routine steps should not render a section."""
    builder = ContextBuilder(tmp_path)

    metadata = {"routine_steps": []}
    prompt = await builder.build_system_prompt(metadata=metadata)

    assert "Active Routine Workflow" not in prompt


@pytest.mark.asyncio
async def test_routine_steps_completed_metadata_optional(tmp_path: Path):
    """Steps without 'completed' field should render without [DONE]."""
    builder = ContextBuilder(tmp_path)

    metadata = {
        "routine_steps": [
            {"id": "s1", "name": "Task A", "content_prompt": "Do A"},
            {"id": "s2", "name": "Task B", "content_prompt": "Do B", "completed": False},
        ]
    }

    prompt = await builder.build_system_prompt(metadata=metadata)

    assert "1. Task A\n" in prompt  # No [DONE]
    assert "2. Task B\n" in prompt  # No [DONE] when False


@pytest.mark.asyncio
async def test_routine_steps_fallback_to_step_number(tmp_path: Path):
    """Steps without name or content_prompt should use fallback."""
    builder = ContextBuilder(tmp_path)

    metadata = {
        "routine_steps": [
            {"id": "s1"},  # No name or content_prompt
        ]
    }

    prompt = await builder.build_system_prompt(metadata=metadata)

    assert "1. Step 1" in prompt
