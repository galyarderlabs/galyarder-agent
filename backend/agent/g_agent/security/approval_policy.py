"""Risk classifier for approval-gated tool calls."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ApprovalRisk:
    """Risk assessment for a tool call."""

    decision: str
    reason: str = ""

    @property
    def needs_approval(self) -> bool:
        """Return whether the call should pause for owner approval."""
        return self.decision == "ask"


_SHELL_RISK_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\brm\s+-(?:[^\s]*[rf]|[rf][^\s]*)\b", "recursive or forced remove"),
    (r"\bsudo\b", "privilege escalation"),
    (r"\b(?:shutdown|reboot|poweroff|halt)\b", "system power command"),
    (r"\b(?:mkfs|diskpart|fdisk|parted)\b", "disk partition or format command"),
    (r"\bdd\s+if=", "raw disk copy command"),
    (r">\s*/dev/(?:sd|nvme|mapper/)", "raw block device write"),
    (r":\(\)\s*\{.*\};\s*:", "fork bomb pattern"),
    (r"\bcurl\b.*\|\s*(?:sh|bash|zsh)\b", "downloaded script piped to shell"),
    (r"\bwget\b.*\|\s*(?:sh|bash|zsh)\b", "downloaded script piped to shell"),
    (r"\bchmod\s+(?:\+x\s+)?(?:777|a\+w)\b", "broad filesystem permission change"),
    (r"\bchown\s+-R\b", "recursive ownership change"),
)

_SENSITIVE_PATH_PARTS: tuple[str, ...] = (
    ".ssh",
    ".gnupg",
    ".aws",
    ".config/gcloud",
    ".docker/config.json",
)


def classify_tool_call(tool_name: str, tool_args: dict[str, Any]) -> ApprovalRisk:
    """Classify a tool call for owner approval."""
    name = (tool_name or "").strip().lower()
    if name == "exec":
        return classify_shell_command(str(tool_args.get("command") or ""))
    if name in {"write_file", "edit_file"}:
        return classify_filesystem_write(name, tool_args)
    return ApprovalRisk("allow")


def classify_shell_command(command: str) -> ApprovalRisk:
    """Classify shell command risk using deterministic examples."""
    normalized = re.sub(r"\s+", " ", command or "").strip()
    lowered = normalized.lower()
    if not lowered:
        return ApprovalRisk("allow")
    for pattern, reason in _SHELL_RISK_PATTERNS:
        if re.search(pattern, lowered):
            return ApprovalRisk("ask", reason)
    return ApprovalRisk("allow")


def classify_filesystem_write(tool_name: str, tool_args: dict[str, Any]) -> ApprovalRisk:
    """Classify write/edit calls that target sensitive filesystem locations."""
    raw_path = str(tool_args.get("path") or "").strip()
    if not raw_path:
        return ApprovalRisk("allow")
    normalized = raw_path.replace("\\", "/").lower()
    path = Path(raw_path).expanduser()

    if path.is_absolute() and not normalized.startswith(("/tmp/", "/home/")):
        return ApprovalRisk("ask", "write outside common user/temp roots")
    if any(part in normalized for part in _SENSITIVE_PATH_PARTS):
        return ApprovalRisk("ask", "write to sensitive credential/config path")
    if normalized.endswith((".bashrc", ".zshrc", ".profile", ".zprofile")):
        return ApprovalRisk("ask", "shell startup file modification")
    if tool_name == "edit_file" and str(tool_args.get("old_text") or "") == "":
        return ApprovalRisk("ask", "empty edit target")
    return ApprovalRisk("allow")
