"""Shell execution tool using LocalEnvironment."""

import asyncio
import os
import re
from pathlib import Path
from typing import Any

from g_agent.agent.tools.base import Tool
from g_agent.execution.local import LocalEnvironment
from g_agent.execution.docker import DockerEnvironment


class ExecTool(Tool):
    """Tool to execute shell commands using local or transient Docker execution.

    Backend modes:
    - local: Stateful session with persistent env vars and cwd tracking
    - docker: Transient container execution (experimental, no session state)
    """

    def __init__(
        self,
        timeout: int = 60,
        working_dir: str | None = None,
        deny_patterns: list[str] | None = None,
        allow_patterns: list[str] | None = None,
        restrict_to_workspace: bool = False,
        path_append: list[str] | None = None,
        allowed_dirs: list[str | Path] | None = None,
        backend: str = "local",
        docker_image: str = "python:3.12-slim",
    ):
        self.timeout = timeout
        self.working_dir = working_dir or os.getcwd()
        self.deny_patterns = deny_patterns or [
            r"\brm\s+-[rf]{1,2}\b",  # rm -r, rm -rf, rm -fr
            r"\bdel\s+/[fq]\b",  # del /f, del /q
            r"\brmdir\s+/s\b",  # rmdir /s
            r"(?:^|[;&|]\s*)format\b",  # format (standalone command only)
            r"\b(mkfs|diskpart)\b",  # disk operations
            r"\bdd\s+if=",  # dd
            r">\s*/dev/sd",  # write to disk
            r"\b(shutdown|reboot|poweroff)\b",  # system power
            r":\(\)\s*\{.*\};\s*:",  # fork bomb
        ]
        self.allow_patterns = allow_patterns or []
        self.restrict_to_workspace = restrict_to_workspace
        self.path_append = path_append or []
        self.allowed_dirs = [Path(path).expanduser().resolve() for path in allowed_dirs or []]

        # Normalize and validate backend
        normalized_backend = backend.strip().lower()
        if normalized_backend not in ("local", "docker"):
            raise ValueError(
                f"Invalid execution backend: {backend!r}. Must be 'local' or 'docker'."
            )
        self.backend = normalized_backend

        if self.backend == "docker":
            self.env = DockerEnvironment(
                image=docker_image,
                workspace_mount=Path(self.working_dir) if restrict_to_workspace else None,
                timeout=timeout,
            )
        else:
            # Initialize the stateful environment
            env = os.environ.copy()
            if self.path_append:
                custom_paths = os.pathsep.join(self.path_append)
                old_path = env.get("PATH", "")
                env["PATH"] = f"{old_path}{os.pathsep}{custom_paths}" if old_path else custom_paths

            self.env = LocalEnvironment(cwd=self.working_dir, timeout=self.timeout, env=env)

    @property
    def name(self) -> str:
        return "exec"

    @property
    def description(self) -> str:
        if self.backend == "docker":
            return (
                "Execute a shell command in an ephemeral Docker container. "
                "Each call spawns a fresh container with no persistent state. "
                "Environment variables and working directory are NOT preserved across calls."
            )
        return "Execute a shell command and return its output. Session state (env vars, cwd) is preserved across calls."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to execute"},
                "working_dir": {
                    "type": "string",
                    "description": "Optional working directory for the command",
                },
            },
            "required": ["command"],
        }

    async def execute(
        self, command: str | None = None, working_dir: str | None = None, **kwargs: Any
    ) -> str:
        command_text = (command or "").strip()
        if not command_text:
            return "Error: command is required"

        # Use provided working_dir or let the environment track it natively
        cwd = working_dir or self.env.cwd

        guard_error = self._guard_command(command_text, cwd)
        if guard_error:
            return guard_error

        try:
            # We run the blocking execute in a thread to keep the async loop responsive
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, lambda: self.env.execute(command_text, cwd=cwd, timeout=self.timeout)
            )

            output = result.get("output", "")
            returncode = result.get("returncode")

            output_parts = []
            if output:
                output_parts.append(output)

            if returncode != 0:
                output_parts.append(f"\nExit code: {returncode}")

            final_result = "\n".join(output_parts).strip()
            if not final_result:
                return "(no output)"

            # Truncate very long output
            max_len = 10000
            if len(final_result) > max_len:
                final_result = (
                    final_result[:max_len]
                    + f"\n... (truncated, {len(final_result) - max_len} more chars)"
                )

            return final_result

        except Exception as e:
            return f"Error executing command: {str(e)}"

    def _guard_command(self, command: str, cwd: str) -> str | None:
        """Best-effort safety guard for potentially destructive commands."""
        cmd = re.sub(r"\s+", " ", command.strip())
        lower = cmd.lower()

        for pattern in self.deny_patterns:
            if re.search(pattern, lower):
                return f"Error: Command blocked by safety guard (dangerous pattern detected: {pattern})"

        if self.allow_patterns:
            if not any(re.search(p, lower) for p in self.allow_patterns):
                return "Error: Command blocked by safety guard (not in allowlist)"

        if self.restrict_to_workspace:
            if "..\\" in cmd or "../" in cmd:
                return "Error: Command blocked by safety guard (path traversal detected)"

            cwd_path = Path(cwd).resolve()
            allowed_roots = [cwd_path]
            for root in self.allowed_dirs:
                if root not in allowed_roots:
                    allowed_roots.append(root)

            win_paths = re.findall(r"[A-Za-z]:\\[^\\\"']+", cmd)
            posix_paths = re.findall(r"(?:^|[\s|>])(/[^\s\"'>]+)", cmd)

            for raw in win_paths + posix_paths:
                try:
                    p = Path(raw.strip()).resolve()
                except Exception:
                    continue
                if p.is_absolute() and not any(
                    p == root or root in p.parents for root in allowed_roots
                ):
                    allowed = ", ".join(str(root) for root in allowed_roots)
                    return (
                        "Error: Command blocked by safety guard "
                        f"(path outside allowed directories: {allowed})"
                    )

        return None
