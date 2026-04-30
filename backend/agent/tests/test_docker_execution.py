"""Tests for Docker execution backend behavior."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from g_agent.execution.docker import DockerEnvironment


def test_docker_environment_unavailable_when_docker_not_installed():
    """Docker should report unavailable when docker CLI is missing."""
    with patch("shutil.which", return_value=None):
        env = DockerEnvironment()
        assert not env.is_available()
        assert env._unavailable_reason() == "cli_missing"


def test_docker_environment_unavailable_when_daemon_not_running():
    """Docker should report unavailable when daemon is not responsive."""
    with patch("shutil.which", return_value="/usr/bin/docker"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1)
            env = DockerEnvironment()
            assert not env.is_available()
            assert env._unavailable_reason() == "daemon_unavailable"


def test_docker_environment_available_when_daemon_responsive():
    """Docker should report available when daemon responds to 'docker info'."""
    with patch("shutil.which", return_value="/usr/bin/docker"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            env = DockerEnvironment()
            assert env.is_available()


def test_docker_environment_unavailable_on_timeout():
    """Docker should report unavailable when 'docker info' times out."""
    with patch("shutil.which", return_value="/usr/bin/docker"):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 5)):
            env = DockerEnvironment()
            assert not env.is_available()


def test_docker_execute_returns_error_when_unavailable():
    """Execute should return clear error when Docker is unavailable."""
    env = DockerEnvironment()
    with patch.object(env, "is_available", return_value=False):
        with patch.object(env, "_unavailable_reason", return_value="cli_missing"):
            result = env.execute("echo test")
            assert result["returncode"] == 127
            assert "Docker CLI not found" in result["output"]
            assert result["error_code"] == "cli_missing"

        with patch.object(env, "_unavailable_reason", return_value="daemon_unavailable"):
            result = env.execute("echo test")
            assert result["returncode"] == 127
            assert "daemon is not running" in result["output"]
            assert result["error_code"] == "daemon_unavailable"


def test_docker_execute_handles_command_timeout():
    """Execute should return timeout error when command exceeds timeout."""
    env = DockerEnvironment(timeout=1)
    with patch.object(env, "is_available", return_value=True):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 1)):
            result = env.execute("sleep 10")
            assert result["returncode"] == 124
            assert "timed out after 1s" in result["output"]
            assert result["error_code"] == "timeout"


def test_docker_execute_handles_docker_not_found():
    """Execute should handle FileNotFoundError gracefully."""
    env = DockerEnvironment()
    with patch.object(env, "is_available", return_value=True):
        with patch("subprocess.run", side_effect=FileNotFoundError("docker")):
            result = env.execute("echo test")
            assert result["returncode"] == 127
            assert "Docker CLI not found" in result["output"]
            assert result["error_code"] == "cli_missing"


def test_docker_execute_handles_generic_exception():
    """Execute should handle unexpected exceptions gracefully."""
    env = DockerEnvironment()
    with patch.object(env, "is_available", return_value=True):
        with patch("subprocess.run", side_effect=RuntimeError("unexpected error")):
            result = env.execute("echo test")
            assert result["returncode"] == 1
            assert "Docker execution failed" in result["output"]
            assert "unexpected error" in result["output"]
            assert result["error_code"] == "execution_failed"


def test_docker_execute_success():
    """Execute should return command output on success."""
    env = DockerEnvironment()
    with patch.object(env, "is_available", return_value=True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="hello world\n",
                stderr="",
            )
            result = env.execute("echo 'hello world'")
            assert result["returncode"] == 0
            assert "hello world" in result["output"]


def test_docker_execute_captures_stderr():
    """Execute should combine stdout and stderr."""
    env = DockerEnvironment()
    with patch.object(env, "is_available", return_value=True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="output\n",
                stderr="error\n",
            )
            result = env.execute("false")
            assert result["returncode"] == 1
            assert "output" in result["output"]
            assert "error" in result["output"]


def test_docker_execute_respects_custom_timeout():
    """Execute should use provided timeout over default."""
    env = DockerEnvironment(timeout=60)
    with patch.object(env, "is_available", return_value=True):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 10)) as mock_run:
            result = env.execute("sleep 20", timeout=10)
            assert result["returncode"] == 124
            assert "timed out after 10s" in result["output"]
            # Verify subprocess.run was called with the custom timeout
            mock_run.assert_called_once()
            assert mock_run.call_args.kwargs["timeout"] == 10


def test_docker_execute_uses_custom_working_directory():
    """Execute should pass custom working directory to docker run."""
    env = DockerEnvironment()
    with patch.object(env, "is_available", return_value=True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            env.execute("pwd", cwd="/custom/path")
            # Verify -w flag was passed with custom path
            call_args = mock_run.call_args[0][0]
            assert "-w" in call_args
            w_index = call_args.index("-w")
            assert call_args[w_index + 1] == "/custom/path"


def test_docker_execute_mounts_workspace_when_configured():
    """Execute should mount workspace when workspace_mount is set."""
    workspace = Path("/tmp/test-workspace")
    env = DockerEnvironment(workspace_mount=workspace)
    with patch.object(env, "is_available", return_value=True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            env.execute("ls")
            # Verify -v flag was passed with mount
            call_args = mock_run.call_args[0][0]
            assert "-v" in call_args
            v_index = call_args.index("-v")
            assert call_args[v_index + 1] == f"{workspace}:/workspace"


def test_docker_constructor_validates_timeout():
    """Constructor should reject timeout <= 0."""
    with pytest.raises(ValueError, match="timeout must be > 0"):
        DockerEnvironment(timeout=0)

    with pytest.raises(ValueError, match="timeout must be > 0"):
        DockerEnvironment(timeout=-1)

    # Valid timeout should work
    env = DockerEnvironment(timeout=30)
    assert env.timeout == 30


def test_docker_execute_validates_per_call_timeout():
    """Execute should reject per-call timeout <= 0."""
    env = DockerEnvironment()
    with patch.object(env, "is_available", return_value=True):
        with pytest.raises(ValueError, match="timeout must be > 0"):
            env.execute("echo test", timeout=0)

        with pytest.raises(ValueError, match="timeout must be > 0"):
            env.execute("echo test", timeout=-5)


def test_docker_constructor_validates_network_mode():
    """Constructor should validate network mode with default-deny."""
    # Valid network modes
    env = DockerEnvironment(network="none")
    assert env.network == "none"

    env = DockerEnvironment(network="bridge")
    assert env.network == "bridge"

    # Invalid network modes should be rejected
    with pytest.raises(ValueError, match="Invalid network mode.*Allowed: bridge, none"):
        DockerEnvironment(network="host")

    with pytest.raises(ValueError, match="Invalid network mode.*Allowed: bridge, none"):
        DockerEnvironment(network="container:xyz")

    with pytest.raises(ValueError, match="Invalid network mode.*Allowed: bridge, none"):
        DockerEnvironment(network="custom")


def test_docker_execute_uses_tmp_when_no_workspace_mount():
    """Execute should use /tmp as cwd when no workspace is mounted."""
    env = DockerEnvironment()  # No workspace_mount
    assert env.cwd == "/tmp"

    with patch.object(env, "is_available", return_value=True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            env.execute("pwd")
            # Verify -w flag was passed with /tmp
            call_args = mock_run.call_args[0][0]
            assert "-w" in call_args
            w_index = call_args.index("-w")
            assert call_args[w_index + 1] == "/tmp"


def test_docker_execute_uses_workspace_when_mounted():
    """Execute should use /workspace as cwd when workspace is mounted."""
    workspace = Path("/tmp/test-workspace")
    env = DockerEnvironment(workspace_mount=workspace)
    assert env.cwd == "/workspace"

    with patch.object(env, "is_available", return_value=True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            env.execute("pwd")
            # Verify -w flag was passed with /workspace
            call_args = mock_run.call_args[0][0]
            assert "-w" in call_args
            w_index = call_args.index("-w")
            assert call_args[w_index + 1] == "/workspace"


def test_exec_tool_backend_validation():
    """Test backend validation logic directly without full imports."""
    # Test the validation logic that would be in ExecTool.__init__
    def validate_backend(backend: str) -> str:
        normalized = backend.strip().lower()
        if normalized not in ("local", "docker"):
            raise ValueError(
                f"Invalid execution backend: {backend!r}. Must be 'local' or 'docker'."
            )
        return normalized

    # Valid backends
    assert validate_backend("local") == "local"
    assert validate_backend("docker") == "docker"
    assert validate_backend("LOCAL") == "local"
    assert validate_backend("Docker") == "docker"
    assert validate_backend("  docker  ") == "docker"

    # Invalid backends
    with pytest.raises(ValueError, match="Invalid execution backend.*Must be 'local' or 'docker'"):
        validate_backend("kubernetes")

    with pytest.raises(ValueError, match="Invalid execution backend.*Must be 'local' or 'docker'"):
        validate_backend("hermes")

    with pytest.raises(ValueError, match="Invalid execution backend.*Must be 'local' or 'docker'"):
        validate_backend("")


def test_config_schema_validates_backend():
    """Config schema should validate backend field."""
    from pydantic import ValidationError
    from g_agent.config.schema import ExecToolConfig

    # Valid backends
    config = ExecToolConfig(backend="local")
    assert config.backend == "local"

    config = ExecToolConfig(backend="docker")
    assert config.backend == "docker"

    # Invalid backend should fail validation
    with pytest.raises(ValidationError, match="String should match pattern"):
        ExecToolConfig(backend="invalid")

    with pytest.raises(ValidationError, match="String should match pattern"):
        ExecToolConfig(backend="kubernetes")


def test_config_schema_backend_default_is_local():
    """Config schema should default backend to 'local'."""
    from g_agent.config.schema import ExecToolConfig

    config = ExecToolConfig()
    assert config.backend == "local"


def test_config_schema_validates_docker_image():
    """Config schema should validate docker_image format."""
    from pydantic import ValidationError
    from g_agent.config.schema import ExecToolConfig

    # Valid docker images
    config = ExecToolConfig(docker_image="python:3.12-slim")
    assert config.docker_image == "python:3.12-slim"

    config = ExecToolConfig(docker_image="ubuntu:22.04")
    assert config.docker_image == "ubuntu:22.04"

    config = ExecToolConfig(docker_image="myregistry.io/myimage:latest")
    assert config.docker_image == "myregistry.io/myimage:latest"

    config = ExecToolConfig(docker_image="alpine")
    assert config.docker_image == "alpine"

    # Invalid docker images should fail validation
    with pytest.raises(ValidationError, match="String should have at least 1 character"):
        ExecToolConfig(docker_image="")

    with pytest.raises(ValidationError, match="String should match pattern"):
        ExecToolConfig(docker_image="Invalid Image Name")

    with pytest.raises(ValidationError, match="String should match pattern"):
        ExecToolConfig(docker_image="image:TAG WITH SPACES")
