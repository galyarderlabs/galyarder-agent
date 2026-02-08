"""Policy preset helpers for personal/guest safety boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from g_agent.config.schema import Config


GUEST_SAFE_TOOLS = {
    "recall",
    "web_search",
    "web_fetch",
    "browser_open",
    "browser_snapshot",
    "browser_extract",
    "browser_screenshot",
    "read_file",
    "list_dir",
    "gmail_list_threads",
    "gmail_read_thread",
    "calendar_list_events",
    "drive_list_files",
    "drive_read_text",
    "docs_get_document",
    "sheets_get_values",
    "contacts_list",
    "contacts_get",
}


GUEST_LIMITED_EXTRA_TOOLS = {
    "browser_click",
    "browser_type",
    "remember",
    "log_feedback",
    "gmail_draft",
    "message",
}


PERSONAL_ASK_TOOLS = {
    "exec",
    "write_file",
    "edit_file",
    "send_email",
    "gmail_send",
    "calendar_create_event",
    "calendar_update_event",
    "docs_append_text",
    "sheets_append_values",
    "slack_webhook_send",
    "message",
}


@dataclass(frozen=True)
class PolicyPreset:
    """Preset definition."""

    name: str
    description: str
    rules: dict[str, str]
    approval_mode: str | None = None
    restrict_to_workspace: bool | None = None


def _build_guest_rules(extra_allowed: Iterable[str] | None = None) -> dict[str, str]:
    allowed = set(GUEST_SAFE_TOOLS)
    if extra_allowed:
        allowed.update(extra_allowed)
    rules = {"*": "deny"}
    for tool in sorted(allowed):
        rules[tool] = "allow"
    return rules


PRESETS: dict[str, PolicyPreset] = {
    "personal_full": PolicyPreset(
        name="personal_full",
        description="Personal owner mode: full capabilities with explicit approval on risky writes/sends.",
        rules={tool: "ask" for tool in sorted(PERSONAL_ASK_TOOLS)},
        approval_mode="confirm",
        restrict_to_workspace=True,
    ),
    "guest_limited": PolicyPreset(
        name="guest_limited",
        description="Guest mode: read-mostly with limited drafting/browser interaction; no sending/destructive tools.",
        rules=_build_guest_rules(extra_allowed=GUEST_LIMITED_EXTRA_TOOLS),
        approval_mode="confirm",
        restrict_to_workspace=True,
    ),
    "guest_readonly": PolicyPreset(
        name="guest_readonly",
        description="Guest mode: strict read-only access.",
        rules=_build_guest_rules(),
        approval_mode="confirm",
        restrict_to_workspace=True,
    ),
}


def list_presets() -> list[PolicyPreset]:
    """Return available policy presets."""
    return [PRESETS[name] for name in sorted(PRESETS)]


def get_preset(name: str) -> PolicyPreset:
    """Resolve preset by name."""
    key = (name or "").strip().lower()
    if key not in PRESETS:
        valid = ", ".join(sorted(PRESETS))
        raise ValueError(f"Unknown preset '{name}'. Valid: {valid}")
    return PRESETS[key]


def _scope_rule_key(base_key: str, channel: str | None, sender: str | None) -> str:
    if not channel:
        return base_key
    if base_key == "*":
        return f"{channel}:{sender or '*'}:*"
    if sender:
        return f"{channel}:{sender}:{base_key}"
    return f"{channel}:*:{base_key}"


def scoped_rules(
    rules: dict[str, str],
    channel: str | None = None,
    sender: str | None = None,
) -> dict[str, str]:
    """Apply optional channel/sender scope to policy rules."""
    channel_text = (channel or "").strip()
    sender_text = (sender or "").strip()
    out: dict[str, str] = {}
    for key, value in rules.items():
        out[_scope_rule_key(key, channel_text or None, sender_text or None)] = value
    return out


def _matching_scope_prefixes(channel: str | None, sender: str | None) -> tuple[str, ...]:
    channel_text = (channel or "").strip()
    sender_text = (sender or "").strip()
    if not channel_text:
        return tuple()
    if sender_text:
        return (f"{channel_text}:{sender_text}:",)
    return (f"{channel_text}:*:", f"{channel_text}:")


def apply_preset(
    config: Config,
    preset_name: str,
    *,
    channel: str | None = None,
    sender: str | None = None,
    replace_scope: bool = False,
    set_defaults: bool = True,
) -> dict[str, object]:
    """Apply a policy preset into config.tools.policy."""
    preset = get_preset(preset_name)
    scoped = scoped_rules(preset.rules, channel=channel, sender=sender)

    before = dict(config.tools.policy)
    if replace_scope:
        if channel:
            prefixes = _matching_scope_prefixes(channel, sender)
            config.tools.policy = {
                key: value
                for key, value in config.tools.policy.items()
                if not any(key.startswith(prefix) for prefix in prefixes)
            }
        else:
            config.tools.policy = {}

    config.tools.policy.update(scoped)

    if set_defaults:
        if preset.approval_mode:
            config.tools.approval_mode = preset.approval_mode
        if preset.restrict_to_workspace is not None:
            config.tools.restrict_to_workspace = bool(preset.restrict_to_workspace)
        current_risky = set(config.tools.risky_tools)
        current_risky.update(PERSONAL_ASK_TOOLS)
        config.tools.risky_tools = sorted(current_risky)

    changed = sum(1 for key, value in scoped.items() if before.get(key) != value)
    return {
        "preset": preset.name,
        "description": preset.description,
        "applied_rules": len(scoped),
        "changed_rules": changed,
        "channel": (channel or "").strip() or None,
        "sender": (sender or "").strip() or None,
    }
