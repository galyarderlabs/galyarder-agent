"""Security baseline audit routines for g-agent profiles."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from stat import S_IMODE
from typing import Any


def _make_check(name: str, level: str, detail: str, remediation: str = "") -> dict[str, str]:
    return {
        "name": name,
        "level": level,
        "detail": detail,
        "remediation": remediation,
    }


def _format_mode(mode_value: int | None) -> str:
    if mode_value is None:
        return "n/a"
    return f"{mode_value:03o}"


def _path_mode(path: Path) -> int | None:
    try:
        if not path.exists():
            return None
        return S_IMODE(path.stat().st_mode)
    except OSError:
        return None


def _permission_level(
    path: Path, expected_max_mode: int, missing_level: str = "warn"
) -> tuple[str, str]:
    mode_value = _path_mode(path)
    if mode_value is None:
        return missing_level, f"{path} (missing)"
    if mode_value <= expected_max_mode:
        return "pass", f"{path} (mode={_format_mode(mode_value)})"
    return "warn", f"{path} (mode={_format_mode(mode_value)})"


def _channel_allowlist_checks(config: Any) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []

    display_names = {
        "telegram": "Telegram",
        "whatsapp": "WhatsApp",
        "discord": "Discord",
        "feishu": "Feishu",
    }
    channels = {
        "telegram": config.channels.telegram,
        "whatsapp": config.channels.whatsapp,
        "discord": config.channels.discord,
        "feishu": config.channels.feishu,
    }
    for name, channel_cfg in channels.items():
        channel_label = display_names.get(name, name.capitalize())
        enabled = bool(getattr(channel_cfg, "enabled", False))
        allow_list = list(getattr(channel_cfg, "allow_from", []))
        if not enabled:
            checks.append(
                _make_check(
                    f"{channel_label} allowlist",
                    "pass",
                    "channel disabled",
                )
            )
            continue
        if allow_list:
            checks.append(
                _make_check(
                    f"{channel_label} allowlist",
                    "pass",
                    f"{len(allow_list)} sender(s)",
                )
            )
            continue
        checks.append(
            _make_check(
                f"{channel_label} allowlist",
                "fail",
                "enabled but allowFrom empty",
                f"Set channels.{name}.allowFrom with approved sender IDs",
            )
        )

    return checks


def _policy_guardrail_checks(config: Any) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    valid_decisions = {"allow", "ask", "deny"}
    tools_cfg = getattr(config, "tools", None)

    raw_policy = getattr(tools_cfg, "policy", {}) if tools_cfg else {}
    policy: dict[str, str] = {}
    if isinstance(raw_policy, dict):
        for raw_key, raw_value in raw_policy.items():
            key = str(raw_key or "").strip().lower()
            if not key:
                continue
            policy[key] = str(raw_value or "").strip().lower()

    invalid_rules = sorted(key for key, value in policy.items() if value not in valid_decisions)
    if invalid_rules:
        listed = ", ".join(invalid_rules[:3])
        if len(invalid_rules) > 3:
            listed = f"{listed} (+{len(invalid_rules) - 3} more)"
        checks.append(
            _make_check(
                "Tool policy decisions",
                "fail",
                f"{len(invalid_rules)} invalid rule(s): {listed}",
                "Use only allow|ask|deny for tools.policy values",
            )
        )
    else:
        checks.append(
            _make_check(
                "Tool policy decisions",
                "pass",
                f"{len(policy)} rule(s) use allow|ask|deny",
            )
        )

    wildcard = policy.get("*")
    if wildcard == "deny":
        checks.append(
            _make_check(
                "Policy default guardrail",
                "pass",
                "tools.policy[*]=deny",
            )
        )
    elif wildcard == "allow":
        checks.append(
            _make_check(
                "Policy default guardrail",
                "fail",
                "tools.policy[*]=allow",
                'Set tools.policy["*"] to "deny" then explicitly allow safe tools',
            )
        )
    elif wildcard == "ask":
        checks.append(
            _make_check(
                "Policy default guardrail",
                "warn",
                "tools.policy[*]=ask",
                'Prefer tools.policy["*"]="deny" for stricter baseline',
            )
        )
    elif wildcard:
        checks.append(
            _make_check(
                "Policy default guardrail",
                "fail",
                f"tools.policy[*]={wildcard}",
                "Use allow|ask|deny decisions only",
            )
        )
    else:
        checks.append(
            _make_check(
                "Policy default guardrail",
                "warn",
                "tools.policy missing '*' fallback",
                'Set tools.policy["*"] to "deny"',
            )
        )

    channels_cfg = getattr(config, "channels", None)
    candidate_channels = ("telegram", "whatsapp", "discord", "feishu", "email", "slack_channel")
    enabled_channels: list[str] = []
    if channels_cfg:
        for name in candidate_channels:
            channel_cfg = getattr(channels_cfg, name, None)
            if bool(getattr(channel_cfg, "enabled", False)):
                enabled_channels.append(name)

    if enabled_channels:
        missing = sorted(
            name
            for name in enabled_channels
            if not any(rule_key.startswith(f"{name}:") for rule_key in policy)
        )
        if missing:
            checks.append(
                _make_check(
                    "Scoped policy guardrails",
                    "warn",
                    f"missing scoped rules for: {', '.join(missing)}",
                    "Add channel-scoped tools.policy rules (channel:*:tool or channel:sender:tool)",
                )
            )
        else:
            checks.append(
                _make_check(
                    "Scoped policy guardrails",
                    "pass",
                    f"scoped rules found for {len(enabled_channels)} enabled channel(s)",
                )
            )
    else:
        checks.append(
            _make_check(
                "Scoped policy guardrails",
                "pass",
                "no external channels enabled",
            )
        )

    raw_risky = getattr(tools_cfg, "risky_tools", []) if tools_cfg else []
    risky_tools = {str(item or "").strip().lower() for item in raw_risky if str(item or "").strip()}
    risky_allow = sorted(tool for tool in risky_tools if policy.get(tool) == "allow")
    if risky_allow:
        listed = ", ".join(risky_allow[:3])
        if len(risky_allow) > 3:
            listed = f"{listed} (+{len(risky_allow) - 3} more)"
        checks.append(
            _make_check(
                "Risky tool overrides",
                "warn",
                f"global allow on risky tools: {listed}",
                "Prefer ask/deny for risky tools, then scope exceptions by channel/sender",
            )
        )
    else:
        checks.append(
            _make_check(
                "Risky tool overrides",
                "pass",
                "no global allow on risky tools",
            )
        )

    return checks


def run_security_audit(
    *,
    config: Any,
    data_dir: Path,
    config_path: Path,
    workspace_path: Path,
    is_root: bool | None = None,
) -> dict[str, Any]:
    """Run practical baseline security checks."""
    checks: list[dict[str, str]] = []
    root_mode = (
        bool(is_root) if is_root is not None else hasattr(os, "geteuid") and os.geteuid() == 0
    )

    if config.tools.restrict_to_workspace:
        checks.append(
            _make_check(
                "Workspace restriction",
                "pass",
                "restrictToWorkspace=true",
            )
        )
    else:
        checks.append(
            _make_check(
                "Workspace restriction",
                "fail",
                "restrictToWorkspace=false",
                "Set tools.restrictToWorkspace=true",
            )
        )

    if config.tools.approval_mode == "confirm":
        checks.append(
            _make_check(
                "Approval mode",
                "pass",
                "approvalMode=confirm",
            )
        )
    else:
        checks.append(
            _make_check(
                "Approval mode",
                "fail",
                f"approvalMode={config.tools.approval_mode}",
                'Set tools.approvalMode to "confirm" (or stricter)',
            )
        )

    checks.extend(_policy_guardrail_checks(config))

    checks.extend(_channel_allowlist_checks(config))

    checks.append(
        _make_check(
            "Runtime user",
            "fail" if root_mode else "pass",
            "running as root" if root_mode else "non-root user",
            "Run g-agent as normal user (never root)" if root_mode else "",
        )
    )

    data_level, data_detail = _permission_level(
        data_dir, expected_max_mode=0o700, missing_level="fail"
    )
    checks.append(
        _make_check(
            "Data directory permissions",
            data_level,
            data_detail,
            f"Run: chmod 700 {data_dir}" if data_level != "pass" else "",
        )
    )

    config_level, config_detail = _permission_level(
        config_path, expected_max_mode=0o600, missing_level="fail"
    )
    checks.append(
        _make_check(
            "Config file permissions",
            config_level,
            config_detail,
            f"Run: chmod 600 {config_path}" if config_level != "pass" else "",
        )
    )

    wa_auth_dir = data_dir / "whatsapp-auth"
    wa_level, wa_detail = _permission_level(
        wa_auth_dir, expected_max_mode=0o700, missing_level="warn"
    )
    if config.channels.whatsapp.enabled and not wa_auth_dir.exists():
        wa_level = "warn"
        wa_detail = f"{wa_auth_dir} (missing)"
    checks.append(
        _make_check(
            "WhatsApp auth permissions",
            wa_level,
            wa_detail,
            f"Run: chmod 700 {wa_auth_dir}" if wa_level != "pass" and wa_auth_dir.exists() else "",
        )
    )

    profile_name = data_dir.name
    if profile_name == ".g-agent":
        profile_level = "warn"
        profile_detail = f"{data_dir} (default profile)"
        profile_fix = "Use dedicated data dirs for personal and guest profiles (G_AGENT_DATA_DIR)"
    else:
        profile_level = "pass"
        profile_detail = f"{data_dir} (custom profile)"
        profile_fix = ""
    checks.append(
        _make_check(
            "Profile separation",
            profile_level,
            profile_detail,
            profile_fix,
        )
    )

    memory_dir = workspace_path / "memory"
    checks.append(
        _make_check(
            "Workspace memory path",
            "pass" if memory_dir.exists() else "warn",
            str(memory_dir),
            "" if memory_dir.exists() else "Create with: g-agent onboard",
        )
    )

    counts = {"pass": 0, "warn": 0, "fail": 0}
    for item in checks:
        level = item.get("level", "warn")
        if level not in counts:
            level = "warn"
        counts[level] += 1

    if counts["fail"] > 0:
        overall = "fail"
    elif counts["warn"] > 0:
        overall = "warn"
    else:
        overall = "pass"

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "overall": overall,
        "summary": counts,
        "checks": checks,
    }
