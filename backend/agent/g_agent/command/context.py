"""Command context for unified slash command handling."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CommandContext:
    """Context for a command execution."""

    workspace: Path
    channel: str
    chat_id: str
    session_key: str
    user_id: str = ""
    username: str = ""
    args: str = ""
    services: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
