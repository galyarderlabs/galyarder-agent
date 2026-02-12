from g_agent.agent.loop import AgentLoop
from g_agent.config.presets import apply_preset
from g_agent.config.schema import Config


def test_apply_guest_readonly_global_sets_deny_default():
    config = Config()
    result = apply_preset(config, "guest_readonly", replace_scope=True)

    assert result["preset"] == "guest_readonly"
    assert config.tools.policy["*"] == "deny"
    assert config.tools.policy["web_search"] == "allow"
    assert "exec" not in config.tools.policy
    assert config.tools.approval_mode == "confirm"
    assert config.tools.restrict_to_workspace is True


def test_apply_guest_limited_scoped_replaces_scope_only():
    config = Config()
    config.tools.policy = {
        "exec": "ask",
        "telegram:123456789:exec": "allow",
        "telegram:other:web_search": "allow",
    }

    apply_preset(
        config,
        "guest_limited",
        channel="telegram",
        sender="123456789",
        replace_scope=True,
    )

    assert config.tools.policy["exec"] == "ask"
    assert config.tools.policy["telegram:other:web_search"] == "allow"
    assert "telegram:123456789:exec" not in config.tools.policy
    assert config.tools.policy["telegram:123456789:*"] == "deny"
    assert config.tools.policy["telegram:123456789:web_search"] == "allow"
    assert config.tools.policy["telegram:123456789:browser_type"] == "allow"


def test_policy_resolver_supports_scoped_wildcards():
    loop = AgentLoop.__new__(AgentLoop)
    loop.approval_mode = "off"
    loop.risky_tools = []
    loop.tool_policy = {
        "telegram:123456789:*": "deny",
        "telegram:*:*": "ask",
        "*": "allow",
    }

    assert loop._resolve_tool_policy("web_search", "telegram", "123456789") == "deny"
    assert loop._resolve_tool_policy("web_search", "telegram", "somebody_else") == "ask"
    assert loop._resolve_tool_policy("web_search", "whatsapp", "123456789") == "allow"


def test_policy_resolver_matches_sender_identity_variants():
    loop = AgentLoop.__new__(AgentLoop)
    loop.approval_mode = "off"
    loop.risky_tools = []
    loop.tool_policy = {
        "telegram:123456789:web_search": "deny",
        "whatsapp:6281234567890:web_search": "ask",
        "*": "allow",
    }

    assert loop._resolve_tool_policy("web_search", "telegram", "123456789|galyarder") == "deny"
    assert (
        loop._resolve_tool_policy("web_search", "whatsapp", "081234567890@s.whatsapp.net")
        == "ask"
    )
