"""Base class for all G-Agent execution environment backends."""

import codecs
import logging
import os
import select
import shlex
import subprocess
import threading
import time
import uuid
from abc import ABC, abstractmethod
from typing import IO, Protocol


logger = logging.getLogger(__name__)


def _cwd_marker(session_id: str) -> str:
    return f"__G_AGENT_CWD_{session_id}__"


def _pipe_stdin(proc: subprocess.Popen, data: str) -> None:
    """Write *data* to proc.stdin on a daemon thread to avoid pipe-buffer deadlocks."""

    def _write():
        try:
            proc.stdin.write(data)
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    threading.Thread(target=_write, daemon=True).start()


class ProcessHandle(Protocol):
    """Duck type that every backend's _run_bash() must return."""

    def poll(self) -> int | None: ...
    def kill(self) -> None: ...
    def wait(self, timeout: float | None = None) -> int: ...

    @property
    def stdout(self) -> IO[str] | None: ...

    @property
    def returncode(self) -> int | None: ...


class BaseEnvironment(ABC):
    """Common interface and unified execution flow for all backends."""

    _stdin_mode: str = "pipe"
    _snapshot_timeout: int = 30

    def get_temp_dir(self) -> str:
        for env_var in ("TMPDIR", "TMP", "TEMP"):
            candidate = self.env.get(env_var) or os.environ.get(env_var)
            if candidate and candidate.startswith("/"):
                return candidate.rstrip("/") or "/"

        if os.path.isdir("/tmp") and os.access("/tmp", os.W_OK | os.X_OK):
            return "/tmp"

        import tempfile

        candidate = tempfile.gettempdir()
        if candidate.startswith("/"):
            return candidate.rstrip("/") or "/"

        return "/tmp"

    def __init__(self, cwd: str, timeout: int, env: dict = None):
        self.cwd = cwd
        self.timeout = timeout
        self.env = env or {}

        self._session_id = uuid.uuid4().hex[:12]
        temp_dir = self.get_temp_dir().rstrip("/") or "/"
        self._snapshot_path = f"{temp_dir}/g-agent-snap-{self._session_id}.sh"
        self._cwd_file = f"{temp_dir}/g-agent-cwd-{self._session_id}.txt"
        self._cwd_marker = _cwd_marker(self._session_id)
        self._snapshot_ready = False

    @abstractmethod
    def _run_bash(
        self,
        cmd_string: str,
        *,
        login: bool = False,
        timeout: int = 120,
        stdin_data: str | None = None,
    ) -> ProcessHandle:
        raise NotImplementedError

    @abstractmethod
    def cleanup(self): ...

    def init_session(self):
        """Capture login shell environment into a snapshot file."""
        bootstrap = (
            f"export -p > {self._snapshot_path}\n"
            f"declare -f | grep -vE '^_[^_]' >> {self._snapshot_path}\n"
            f"alias -p >> {self._snapshot_path}\n"
            f"echo 'shopt -s expand_aliases' >> {self._snapshot_path}\n"
            f"echo 'set +e' >> {self._snapshot_path}\n"
            f"echo 'set +u' >> {self._snapshot_path}\n"
            f"pwd -P > {self._cwd_file} 2>/dev/null || true\n"
            f"printf '\\n{self._cwd_marker}%s{self._cwd_marker}\\n' \"$(pwd -P)\"\n"
        )
        try:
            proc = self._run_bash(bootstrap, login=True, timeout=self._snapshot_timeout)
            result = self._wait_for_process(proc, timeout=self._snapshot_timeout)
            self._snapshot_ready = True
            self._update_cwd(result)
            logger.debug(f"Session snapshot created: {self._session_id} at {self.cwd}")
        except Exception as exc:
            logger.warning(f"init_session failed ({self._session_id}): {exc}")
            self._snapshot_ready = False

    @staticmethod
    def _quote_cwd_for_cd(cwd: str) -> str:
        if cwd == "~":
            return cwd
        if cwd == "~/":
            return "$HOME"
        if cwd.startswith("~/"):
            return f"$HOME/{shlex.quote(cwd[2:])}"
        return shlex.quote(cwd)

    def _wrap_command(self, command: str, cwd: str) -> str:
        escaped = command.replace("'", "'\\''")
        parts = []

        if self._snapshot_ready:
            parts.append(f"source {self._snapshot_path} 2>/dev/null || true")

        quoted_cwd = self._quote_cwd_for_cd(cwd)
        parts.append(f"builtin cd {quoted_cwd} || exit 126")

        parts.append(f"eval '{escaped}'")
        parts.append("__g_agent_ec=$?")

        if self._snapshot_ready:
            parts.append(f"export -p > {self._snapshot_path} 2>/dev/null || true")

        parts.append(f"pwd -P > {self._cwd_file} 2>/dev/null || true")
        parts.append(f"printf '\\n{self._cwd_marker}%s{self._cwd_marker}\\n' \"$(pwd -P)\"")
        parts.append("exit $__g_agent_ec")

        return "\n".join(parts)

    def _wait_for_process(self, proc: ProcessHandle, timeout: int = 120) -> dict:
        output_chunks: list[str] = []
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        def _drain():
            fd = proc.stdout.fileno()
            idle_after_exit = 0
            try:
                while True:
                    try:
                        ready, _, _ = select.select([fd], [], [], 0.1)
                    except (ValueError, OSError):
                        break
                    if ready:
                        try:
                            chunk = os.read(fd, 4096)
                        except (ValueError, OSError):
                            break
                        if not chunk:
                            break
                        output_chunks.append(decoder.decode(chunk))
                        idle_after_exit = 0
                    elif proc.poll() is not None:
                        idle_after_exit += 1
                        if idle_after_exit >= 3:
                            break
            finally:
                try:
                    tail = decoder.decode(b"", final=True)
                    if tail:
                        output_chunks.append(tail)
                except Exception:
                    pass

        drain_thread = threading.Thread(target=_drain, daemon=True)
        drain_thread.start()
        deadline = time.monotonic() + timeout

        try:
            while proc.poll() is None:
                if time.monotonic() > deadline:
                    self._kill_process(proc)
                    drain_thread.join(timeout=2)
                    partial = "".join(output_chunks)
                    timeout_msg = f"\n[Command timed out after {timeout}s]"
                    return {
                        "output": partial + timeout_msg if partial else timeout_msg.lstrip(),
                        "returncode": 124,
                    }
                time.sleep(0.2)
        except (KeyboardInterrupt, SystemExit):
            try:
                self._kill_process(proc)
                drain_thread.join(timeout=2)
            except Exception:
                pass
            raise

        drain_thread.join(timeout=2)
        try:
            proc.stdout.close()
        except Exception:
            pass

        return {"output": "".join(output_chunks), "returncode": proc.returncode}

    def _kill_process(self, proc: ProcessHandle):
        try:
            proc.kill()
        except (ProcessLookupError, PermissionError, OSError):
            pass

    def _update_cwd(self, result: dict):
        self._extract_cwd_from_output(result)

    def _extract_cwd_from_output(self, result: dict):
        output = result.get("output", "")
        marker = self._cwd_marker
        last = output.rfind(marker)
        if last == -1:
            return

        search_start = max(0, last - 4096)
        first = output.rfind(marker, search_start, last)
        if first == -1 or first == last:
            return

        cwd_path = output[first + len(marker) : last].strip()
        if cwd_path:
            self.cwd = cwd_path

        line_start = output.rfind("\n", 0, first)
        if line_start == -1:
            line_start = first
        line_end = output.find("\n", last + len(marker))
        line_end = line_end + 1 if line_end != -1 else len(output)

        result["output"] = output[:line_start] + output[line_end:]

    def _before_execute(self) -> None:
        pass

    def execute(
        self,
        command: str,
        cwd: str = "",
        *,
        timeout: int | None = None,
        stdin_data: str | None = None,
    ) -> dict:
        self._before_execute()

        # Guard against subshell wait traps
        if "&&" in command and command.strip().endswith("&"):
            command = command.rsplit("&", 1)[0] + "{ " + command.rsplit("&", 1)[1] + " & }"

        effective_timeout = timeout or self.timeout
        effective_cwd = cwd or self.cwd

        wrapped = self._wrap_command(command, effective_cwd)
        login = not self._snapshot_ready

        proc = self._run_bash(
            wrapped, login=login, timeout=effective_timeout, stdin_data=stdin_data
        )
        result = self._wait_for_process(proc, timeout=effective_timeout)
        self._update_cwd(result)

        return result

    def stop(self):
        self.cleanup()

    def __del__(self):
        try:
            self.cleanup()
        except Exception:
            pass
