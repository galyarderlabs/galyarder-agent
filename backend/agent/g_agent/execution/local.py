"""Local execution environment — spawn-per-call with session snapshot."""

import os
import platform
import shutil
import signal
import subprocess

from g_agent.execution.base import BaseEnvironment, _pipe_stdin, ProcessHandle

_IS_WINDOWS = platform.system() == "Windows"


def _find_bash() -> str:
    """Find bash for command execution."""
    if not _IS_WINDOWS:
        return (
            shutil.which("bash")
            or ("/usr/bin/bash" if os.path.isfile("/usr/bin/bash") else None)
            or ("/bin/bash" if os.path.isfile("/bin/bash") else None)
            or os.environ.get("SHELL")
            or "/bin/sh"
        )

    found = shutil.which("bash")
    if found:
        return found

    for candidate in (
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Git", "bin", "bash.exe"),
        os.path.join(
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Git", "bin", "bash.exe"
        ),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Git", "bin", "bash.exe"),
    ):
        if candidate and os.path.isfile(candidate):
            return candidate

    raise RuntimeError("Git Bash not found on Windows.")


class LocalEnvironment(BaseEnvironment):
    """Run commands directly on the host machine."""

    def __init__(self, cwd: str = "", timeout: int = 60, env: dict = None):
        super().__init__(cwd=cwd or os.getcwd(), timeout=timeout, env=env)
        self.init_session()

    def _run_bash(
        self,
        cmd_string: str,
        *,
        login: bool = False,
        timeout: int = 120,
        stdin_data: str | None = None,
    ) -> ProcessHandle:
        bash = _find_bash()
        args = [bash, "-l", "-c", cmd_string] if login else [bash, "-c", cmd_string]

        # In a real setup, we'd sanitize env vars here.
        run_env = dict(os.environ | self.env)

        proc = subprocess.Popen(
            args,
            text=True,
            env=run_env,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE if stdin_data is not None else subprocess.DEVNULL,
            preexec_fn=None if _IS_WINDOWS else os.setsid,
            cwd=self.cwd,
        )

        if stdin_data is not None:
            _pipe_stdin(proc, stdin_data)

        return proc

    def _kill_process(self, proc: ProcessHandle):
        """Kill the entire process group (all children)."""
        try:
            if _IS_WINDOWS:
                proc.terminate()
            else:
                pgid = os.getpgid(proc.pid)
                os.killpg(pgid, signal.SIGTERM)
                try:
                    proc.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    os.killpg(pgid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            try:
                proc.kill()
            except Exception:
                pass

    def _update_cwd(self, result: dict):
        """Read CWD from temp file (local-only, no round-trip needed)."""
        try:
            cwd_path = open(self._cwd_file).read().strip()
            if cwd_path:
                self.cwd = cwd_path
        except (OSError, FileNotFoundError):
            pass

        self._extract_cwd_from_output(result)

    def cleanup(self):
        """Clean up temp files."""
        for f in (self._snapshot_path, self._cwd_file):
            try:
                os.unlink(f)
            except OSError:
                pass
