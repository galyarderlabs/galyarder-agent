"""Tests for execution backend command wrapping."""

from g_agent.execution.base import BaseEnvironment


class DummyEnvironment(BaseEnvironment):
    """Minimal backend used to inspect wrapped shell commands."""

    def _run_bash(
        self,
        cmd_string: str,
        *,
        login: bool = False,
        timeout: int = 120,
        stdin_data: str | None = None,
    ):
        raise AssertionError("DummyEnvironment does not execute commands")

    def cleanup(self) -> None:
        pass


def test_execution_backend_quotes_snapshot_and_cwd_files() -> None:
    env = DummyEnvironment(cwd="/workspace", timeout=30, env={"TMPDIR": "/tmp/g agent;bad"})
    env._snapshot_ready = True

    wrapped = env._wrap_command("pwd", "/workspace")

    assert "source '/tmp/g agent;bad/g-agent-snap-" in wrapped
    assert "> '/tmp/g agent;bad/g-agent-snap-" in wrapped
    assert "> '/tmp/g agent;bad/g-agent-cwd-" in wrapped
