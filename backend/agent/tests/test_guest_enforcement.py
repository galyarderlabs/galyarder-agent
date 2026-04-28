"""Tests for guest profile tool enforcement."""

from g_agent.agent.loop import AgentLoop
from g_agent.character.profile import CharacterProfile


def test_guest_enforcement_blocks_dangerous_tools():
    """Guest profile blocks unsafe tools before scoped policy can allow them."""
    loop = AgentLoop.__new__(AgentLoop)
    loop.risky_tools = ["exec", "write_file"]
    loop.approval_mode = "off"
    loop.tool_policy = {}
    loop.active_profile = CharacterProfile(
        id="owner",
        name="Owner",
        role="Admin",
        is_guest=False,
    )

    assert loop._resolve_tool_policy("web_search", "telegram", "user1") == "allow"
    assert loop._resolve_tool_policy("exec", "telegram", "user1") == "allow"
    loop.active_profile = CharacterProfile(
        id="guest",
        name="Guest",
        role="Visitor",
        is_guest=True,
    )

    assert loop._resolve_tool_policy("web_search", "telegram", "user1") == "allow"
    assert loop._resolve_tool_policy("exec", "telegram", "user1") == "deny"
    assert loop._resolve_tool_policy("write_file", "telegram", "user1") == "deny"

    loop.tool_policy = {"telegram:user1:exec": "allow"}
    assert loop._resolve_tool_policy("exec", "telegram", "user1") == "deny"
