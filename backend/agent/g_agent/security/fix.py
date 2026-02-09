"""Automatic baseline security remediations for g-agent profiles."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from stat import S_IMODE
from typing import Any, Callable

from g_agent.security.audit import run_security_audit


def _action(name: str, status: str, detail: str, changed: bool = False) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "detail": detail,
        "changed": changed,
    }


def _path_mode(path: Path) -> int | None:
    try:
        if not path.exists():
            return None
        return S_IMODE(path.stat().st_mode)
    except OSError:
        return None


def _fmt_mode(mode_value: int | None) -> str:
    if mode_value is None:
        return "n/a"
    return f"{mode_value:03o}"


def _ensure_mode(path: Path, *, expected_mode: int, name: str, apply: bool) -> dict[str, Any]:
    mode_value = _path_mode(path)
    if mode_value is None:
        return _action(name, "skipped", f"{path} missing")
    if mode_value <= expected_mode:
        return _action(name, "unchanged", f"{path} already mode={_fmt_mode(mode_value)}")
    if not apply:
        return _action(
            name,
            "planned",
            f"{path} mode={_fmt_mode(mode_value)} -> {_fmt_mode(expected_mode)}",
        )
    try:
        os.chmod(path, expected_mode)
    except OSError as exc:
        return _action(name, "failed", f"{path}: chmod failed ({exc})")
    after_mode = _path_mode(path)
    return _action(
        name,
        "applied",
        f"{path} mode={_fmt_mode(mode_value)} -> {_fmt_mode(after_mode)}",
        changed=True,
    )


def _create_memory_template(memory_file: Path) -> None:
    template = """# Long-term Memory

This file stores important information that should persist across sessions.

## User Information

(Important facts about the user)

## Preferences

(User preferences learned over time)

## Important Notes

(Things to remember)
"""
    memory_file.write_text(template, encoding="utf-8")


def run_security_fix(
    *,
    config: Any,
    data_dir: Path,
    config_path: Path,
    workspace_path: Path,
    apply: bool,
    is_root: bool | None = None,
    save_config_func: Callable[[Any, Path], None] | None = None,
) -> dict[str, Any]:
    """Apply safe, local security baseline remediations."""
    before = run_security_audit(
        config=config,
        data_dir=data_dir,
        config_path=config_path,
        workspace_path=workspace_path,
        is_root=is_root,
    )

    actions: list[dict[str, Any]] = []
    changed_total = 0
    config_needs_write = False

    if config.tools.restrict_to_workspace:
        actions.append(_action("Enforce tools.restrictToWorkspace=true", "unchanged", "already enabled"))
    elif apply:
        config.tools.restrict_to_workspace = True
        config_needs_write = True
        changed_total += 1
        actions.append(_action("Enforce tools.restrictToWorkspace=true", "applied", "set to true", changed=True))
    else:
        config_needs_write = True
        actions.append(_action("Enforce tools.restrictToWorkspace=true", "planned", "will set to true"))

    if config.tools.approval_mode == "confirm":
        actions.append(_action("Enforce tools.approvalMode=confirm", "unchanged", "already confirm"))
    elif apply:
        before_mode = str(config.tools.approval_mode)
        config.tools.approval_mode = "confirm"
        config_needs_write = True
        changed_total += 1
        actions.append(
            _action(
                "Enforce tools.approvalMode=confirm",
                "applied",
                f"set {before_mode} -> confirm",
                changed=True,
            )
        )
    else:
        config_needs_write = True
        actions.append(
            _action(
                "Enforce tools.approvalMode=confirm",
                "planned",
                f"will set {config.tools.approval_mode} -> confirm",
            )
        )

    if config_needs_write:
        if not apply:
            actions.append(_action("Persist config changes", "planned", str(config_path)))
        else:
            save_fn = save_config_func
            if save_fn is None:
                from g_agent.config.loader import save_config

                save_fn = save_config
            try:
                save_fn(config, config_path)
                actions.append(_action("Persist config changes", "applied", str(config_path)))
            except Exception as exc:
                actions.append(_action("Persist config changes", "failed", f"{config_path}: {exc}"))
    else:
        actions.append(_action("Persist config changes", "unchanged", "no config changes required"))

    for item in (
        _ensure_mode(
            data_dir,
            expected_mode=0o700,
            name="Harden data directory permissions",
            apply=apply,
        ),
        _ensure_mode(
            config_path,
            expected_mode=0o600,
            name="Harden config file permissions",
            apply=apply,
        ),
    ):
        actions.append(item)
        if item.get("changed"):
            changed_total += 1

    wa_auth_dir = data_dir / "whatsapp-auth"
    if config.channels.whatsapp.enabled:
        wa_action = _ensure_mode(
            wa_auth_dir,
            expected_mode=0o700,
            name="Harden WhatsApp auth permissions",
            apply=apply,
        )
        if wa_action["status"] == "skipped":
            wa_action["detail"] = f"{wa_auth_dir} missing (pair WhatsApp first)"
        actions.append(wa_action)
        if wa_action.get("changed"):
            changed_total += 1
    else:
        actions.append(_action("Harden WhatsApp auth permissions", "skipped", "whatsapp channel disabled"))

    memory_dir = workspace_path / "memory"
    memory_file = memory_dir / "MEMORY.md"
    if memory_dir.exists():
        actions.append(_action("Ensure workspace memory directory", "unchanged", str(memory_dir)))
    elif not apply:
        actions.append(_action("Ensure workspace memory directory", "planned", str(memory_dir)))
    else:
        try:
            memory_dir.mkdir(parents=True, exist_ok=True)
            if not memory_file.exists():
                _create_memory_template(memory_file)
            actions.append(
                _action(
                    "Ensure workspace memory directory",
                    "applied",
                    f"created {memory_dir}",
                    changed=True,
                )
            )
            changed_total += 1
        except OSError as exc:
            actions.append(_action("Ensure workspace memory directory", "failed", f"{memory_dir}: {exc}"))

    after = run_security_audit(
        config=config,
        data_dir=data_dir,
        config_path=config_path,
        workspace_path=workspace_path,
        is_root=is_root,
    )
    status_counts = {"applied": 0, "planned": 0, "unchanged": 0, "skipped": 0, "failed": 0}
    for item in actions:
        status = str(item.get("status", "skipped"))
        if status in status_counts:
            status_counts[status] += 1
        else:
            status_counts["skipped"] += 1

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "apply": apply,
        "changed": changed_total,
        "actions": actions,
        "action_summary": status_counts,
        "before": before,
        "after": after,
    }
