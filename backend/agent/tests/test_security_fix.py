import json
from pathlib import Path
from stat import S_IMODE
from types import SimpleNamespace

from g_agent.security.fix import run_security_fix


def _touch(path: Path, content: str = "{}") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _mode(path: Path) -> int:
    return S_IMODE(path.stat().st_mode)


def _build_config(
    *,
    restrict_to_workspace: bool,
    approval_mode: str,
    telegram_enabled: bool,
    telegram_allow: list[str],
    whatsapp_enabled: bool,
    whatsapp_allow: list[str],
) -> SimpleNamespace:
    def channel(enabled: bool, allow: list[str]) -> SimpleNamespace:
        return SimpleNamespace(enabled=enabled, allow_from=list(allow))

    return SimpleNamespace(
        tools=SimpleNamespace(
            restrict_to_workspace=restrict_to_workspace,
            approval_mode=approval_mode,
        ),
        channels=SimpleNamespace(
            telegram=channel(telegram_enabled, telegram_allow),
            whatsapp=channel(whatsapp_enabled, whatsapp_allow),
            discord=channel(False, []),
            feishu=channel(False, []),
        ),
    )


def test_security_fix_dry_run_only_plans(tmp_path: Path):
    data_dir = tmp_path / ".g-agent-test"
    workspace = data_dir / "workspace"
    config_path = data_dir / "config.json"
    _touch(config_path)
    workspace.mkdir(parents=True, exist_ok=True)
    data_dir.chmod(0o755)
    config_path.chmod(0o644)

    config = _build_config(
        restrict_to_workspace=False,
        approval_mode="off",
        telegram_enabled=True,
        telegram_allow=["6218572023"],
        whatsapp_enabled=True,
        whatsapp_allow=["628111111111"],
    )
    save_calls: list[str] = []

    def _save_stub(cfg: object, path: Path) -> None:
        save_calls.append(str(path))
        path.write_text(json.dumps({"saved": True}), encoding="utf-8")

    report = run_security_fix(
        config=config,
        data_dir=data_dir,
        config_path=config_path,
        workspace_path=workspace,
        apply=False,
        is_root=False,
        save_config_func=_save_stub,
    )

    assert save_calls == []
    assert config.tools.restrict_to_workspace is False
    assert config.tools.approval_mode == "off"
    assert _mode(data_dir) == 0o755
    assert _mode(config_path) == 0o644
    assert not (workspace / "memory").exists()

    action_map = {item["name"]: item for item in report["actions"]}
    assert action_map["Enforce tools.restrictToWorkspace=true"]["status"] == "planned"
    assert action_map["Enforce tools.approvalMode=confirm"]["status"] == "planned"
    assert action_map["Persist config changes"]["status"] == "planned"
    assert action_map["Harden data directory permissions"]["status"] == "planned"
    assert action_map["Harden config file permissions"]["status"] == "planned"
    assert action_map["Ensure workspace memory directory"]["status"] == "planned"
    assert report["changed"] == 0


def test_security_fix_apply_changes_config_permissions_and_memory(tmp_path: Path):
    data_dir = tmp_path / ".g-agent-secure"
    workspace = data_dir / "workspace"
    config_path = data_dir / "config.json"
    wa_auth = data_dir / "whatsapp-auth"
    _touch(config_path)
    wa_auth.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)

    data_dir.chmod(0o755)
    config_path.chmod(0o644)
    wa_auth.chmod(0o755)

    config = _build_config(
        restrict_to_workspace=False,
        approval_mode="off",
        telegram_enabled=True,
        telegram_allow=["6218572023"],
        whatsapp_enabled=True,
        whatsapp_allow=["628111111111"],
    )
    save_calls: list[str] = []

    def _save_stub(cfg: object, path: Path) -> None:
        save_calls.append(str(path))
        path.write_text(json.dumps({"saved": True}), encoding="utf-8")

    report = run_security_fix(
        config=config,
        data_dir=data_dir,
        config_path=config_path,
        workspace_path=workspace,
        apply=True,
        is_root=False,
        save_config_func=_save_stub,
    )

    assert save_calls == [str(config_path)]
    assert config.tools.restrict_to_workspace is True
    assert config.tools.approval_mode == "confirm"
    assert _mode(data_dir) == 0o700
    assert _mode(config_path) == 0o600
    assert _mode(wa_auth) == 0o700
    assert (workspace / "memory").exists()
    assert (workspace / "memory" / "MEMORY.md").exists()
    assert report["changed"] >= 5
    assert report["after"]["summary"]["fail"] == 0
