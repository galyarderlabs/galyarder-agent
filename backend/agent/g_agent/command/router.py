"""Command router for unified slash command handling."""

import shlex
from collections.abc import Callable, Coroutine
from typing import Any

from loguru import logger

from g_agent.command.context import CommandContext

# Result can be a string, a dict (for buttons), or None
CommandResult = str | dict[str, Any] | None
CommandHandler = Callable[
    [CommandContext],
    CommandResult | Coroutine[Any, Any, CommandResult],
]

class CommandRouter:
    """Routes slash commands to their respective handlers."""

    def __init__(self):
        self._handlers: dict[str, CommandHandler] = {}
        self._aliases: dict[str, str] = {}
        self._descriptions: dict[str, str] = {}
        self._usage: dict[str, str] = {}

    def register(
        self,
        name: str,
        handler: CommandHandler,
        aliases: list[str] | None = None,
        description: str = "",
        usage: str = ""
    ) -> None:
        """Register a command handler."""
        name = name.lower()
        self._handlers[name] = handler
        self._descriptions[name] = description
        self._usage[name] = usage

        if aliases:
            for alias in aliases:
                self._aliases[alias.lower()] = name

    async def handle(self, text: str, context: CommandContext) -> CommandResult:
        """Parse and route a command."""
        stripped = text.strip()
        if not stripped.startswith("/"):
            return None

        raw_cmd, args = self.parse(stripped)
        context.args = args

        canonical = self._aliases.get(raw_cmd, raw_cmd)
        handler = self._handlers.get(canonical)

        if not handler:
            return None

        try:
            result = handler(context)
            if hasattr(result, "__await__"):
                result = await result
            return result
        except Exception as e:
            logger.error(f"Command /{raw_cmd} failed: {e}")
            return f"⚠️ Error executing /{raw_cmd}: {e}"

    def parse(self, text: str) -> tuple[str, str]:
        """Parse a slash command while preserving quoted arguments."""
        stripped = text.strip()
        if not stripped.startswith("/"):
            return "", ""
        parts = stripped.split(maxsplit=1)
        raw_cmd = parts[0][1:].lower()
        raw_args = parts[1].strip() if len(parts) > 1 else ""
        if not raw_args:
            return raw_cmd, ""
        try:
            args = shlex.split(raw_args)
        except ValueError:
            return raw_cmd, raw_args
        return raw_cmd, " ".join(args)

    def list_commands(self) -> list[tuple[str, str, str]]:
        """List all registered commands with their description and usage."""
        cmds = []
        for name in sorted(self._handlers.keys()):
            cmds.append((name, self._descriptions.get(name, ""), self._usage.get(name, "")))
        return cmds
