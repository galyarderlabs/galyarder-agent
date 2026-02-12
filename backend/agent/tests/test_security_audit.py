from pathlib import Path
from types import SimpleNamespace

from g_agent.security.audit import run_security_audit


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")


def _build_config(
    *,
    restrict_to_workspace: bool,
    approval_mode: str,
    telegram_enabled: bool,
    telegram_allow: list[str],
    whatsapp_enabled: bool,
    whatsapp_allow: list[str],
    policy: dict[str, str] | None = None,
    risky_tools: list[str] | None = None,
) -> SimpleNamespace:
    def channel(enabled: bool, allow: list[str]) -> SimpleNamespace:
        return SimpleNamespace(enabled=enabled, allow_from=list(allow))

    return SimpleNamespace(
        tools=SimpleNamespace(
            restrict_to_workspace=restrict_to_workspace,
            approval_mode=approval_mode,
            policy=dict(policy or {}),
            risky_tools=list(risky_tools or []),
        ),
        channels=SimpleNamespace(
            telegram=channel(telegram_enabled, telegram_allow),
            whatsapp=channel(whatsapp_enabled, whatsapp_allow),
            discord=channel(False, []),
            feishu=channel(False, []),
        ),
    )


def test_security_audit_secure_baseline(tmp_path: Path):
    data_dir = tmp_path / ".g-agent-secure"
    workspace = data_dir / "workspace"
    memory_dir = workspace / "memory"
    config_path = data_dir / "config.json"
    wa_auth = data_dir / "whatsapp-auth"

    memory_dir.mkdir(parents=True, exist_ok=True)
    wa_auth.mkdir(parents=True, exist_ok=True)
    _touch(config_path)

    data_dir.chmod(0o700)
    config_path.chmod(0o600)
    wa_auth.chmod(0o700)

    config = _build_config(
        restrict_to_workspace=True,
        approval_mode="confirm",
        telegram_enabled=True,
        telegram_allow=["123456789"],
        whatsapp_enabled=True,
        whatsapp_allow=["6281234567890"],
    )

    report = run_security_audit(
        config=config,
        data_dir=data_dir,
        config_path=config_path,
        workspace_path=workspace,
        is_root=False,
    )

    assert report["overall"] in {"pass", "warn"}
    assert report["summary"]["fail"] == 0
    check_by_name = {item["name"]: item for item in report["checks"]}
    assert check_by_name["Workspace restriction"]["level"] == "pass"
    assert check_by_name["Approval mode"]["level"] == "pass"
    assert check_by_name["Telegram allowlist"]["level"] == "pass"
    assert check_by_name["WhatsApp allowlist"]["level"] == "pass"
    assert check_by_name["Runtime user"]["level"] == "pass"
    assert check_by_name["Data directory permissions"]["level"] == "pass"
    assert check_by_name["Config file permissions"]["level"] == "pass"
    assert check_by_name["WhatsApp auth permissions"]["level"] == "pass"


def test_security_audit_flags_unsafe_baseline(tmp_path: Path):
    data_dir = tmp_path / ".g-agent"
    workspace = data_dir / "workspace"
    config_path = data_dir / "config.json"

    workspace.mkdir(parents=True, exist_ok=True)
    _touch(config_path)
    data_dir.chmod(0o755)
    config_path.chmod(0o644)

    config = _build_config(
        restrict_to_workspace=False,
        approval_mode="off",
        telegram_enabled=True,
        telegram_allow=[],
        whatsapp_enabled=True,
        whatsapp_allow=[],
    )

    report = run_security_audit(
        config=config,
        data_dir=data_dir,
        config_path=config_path,
        workspace_path=workspace,
        is_root=True,
    )

    assert report["overall"] == "fail"
    assert report["summary"]["fail"] >= 4
    check_by_name = {item["name"]: item for item in report["checks"]}
    assert check_by_name["Workspace restriction"]["level"] == "fail"
    assert check_by_name["Approval mode"]["level"] == "fail"
    assert check_by_name["Telegram allowlist"]["level"] == "fail"
    assert check_by_name["WhatsApp allowlist"]["level"] == "fail"
    assert check_by_name["Runtime user"]["level"] == "fail"
    assert check_by_name["Data directory permissions"]["level"] == "warn"
    assert check_by_name["Config file permissions"]["level"] == "warn"


def test_security_audit_flags_policy_guardrail_issues(tmp_path: Path):
    data_dir = tmp_path / ".g-agent-policy"
    workspace = data_dir / "workspace"
    config_path = data_dir / "config.json"

    workspace.mkdir(parents=True, exist_ok=True)
    _touch(config_path)
    data_dir.chmod(0o700)
    config_path.chmod(0o600)

    config = _build_config(
        restrict_to_workspace=True,
        approval_mode="confirm",
        telegram_enabled=True,
        telegram_allow=["123456789"],
        whatsapp_enabled=False,
        whatsapp_allow=[],
        policy={
            "*": "allow",
            "exec": "allow",
            "telegram:123456789:web_search": "allow",
            "telegram:123456789:message": "sometimes",
        },
        risky_tools=["exec", "message"],
    )

    report = run_security_audit(
        config=config,
        data_dir=data_dir,
        config_path=config_path,
        workspace_path=workspace,
        is_root=False,
    )

    check_by_name = {item["name"]: item for item in report["checks"]}
    assert check_by_name["Tool policy decisions"]["level"] == "fail"
    assert check_by_name["Policy default guardrail"]["level"] == "fail"
    assert check_by_name["Scoped policy guardrails"]["level"] == "pass"
    assert check_by_name["Risky tool overrides"]["level"] == "warn"
