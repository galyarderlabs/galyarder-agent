import shutil
import subprocess
from pathlib import Path
from typing import Any


class DockerEnvironment:
    """Transient Docker command execution environment.

    Each execute() call spawns a fresh, ephemeral container. No session state
    (environment variables, working directory) is preserved across calls.

    The class may track a default working directory (cwd), but this is only
    used as a default parameter for container execution. Containers themselves
    do not persist state between calls.

    For stateful execution with persistent session tracking, use LocalEnvironment.
    """

    def __init__(
        self,
        image: str = "python:3.12-slim",
        workspace_mount: Path | None = None,
        timeout: int = 60,
        network: str = "none",
        memory_limit: str = "512m",
    ):
        if timeout <= 0:
            raise ValueError(f"timeout must be > 0, got {timeout}")

        # Validate network mode with default-deny policy
        allowed_networks = {"none", "bridge"}
        if network not in allowed_networks:
            raise ValueError(
                f"Invalid network mode: {network!r}. Allowed: {', '.join(sorted(allowed_networks))}"
            )

        self.image = image
        self.workspace_mount = workspace_mount
        self.timeout = timeout
        self.network = network
        self.memory_limit = memory_limit
        self.cwd = "/workspace" if workspace_mount else "/tmp"

    def is_available(self) -> bool:
        """Check if docker CLI is available and daemon is responsive."""
        if shutil.which("docker") is None:
            return False

        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False

    def _unavailable_reason(self) -> str:
        """Return specific reason why Docker is unavailable."""
        if shutil.which("docker") is None:
            return "cli_missing"

        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            if result.returncode != 0:
                return "daemon_unavailable"
        except subprocess.TimeoutExpired:
            return "daemon_unavailable"
        except (FileNotFoundError, OSError):
            return "cli_missing"

        return "unknown"

    def execute(self, command: str, cwd: str | None = None, timeout: int | None = None) -> dict[str, Any]:
        """Execute a command in a transient Docker container.

        Each call spawns a fresh container. No session state is preserved.
        """
        if not self.is_available():
            reason = self._unavailable_reason()
            if reason == "cli_missing":
                return {
                    "output": "Error: Docker CLI not found. Install Docker and ensure 'docker' is in PATH.",
                    "returncode": 127,
                    "error_code": "cli_missing",
                }
            else:
                return {
                    "output": "Error: Docker daemon is not running or not accessible. Start Docker daemon.",
                    "returncode": 127,
                    "error_code": "daemon_unavailable",
                }

        target_cwd = cwd or self.cwd
        exec_timeout = timeout if timeout is not None else self.timeout

        if exec_timeout <= 0:
            raise ValueError(f"timeout must be > 0, got {exec_timeout}")

        docker_cmd = [
            "docker", "run", "--rm",
            "--network", self.network,
            "--memory", self.memory_limit,
        ]

        # Only set working directory if it's mounted or intentionally exists
        if self.workspace_mount:
            docker_cmd.extend(["-v", f"{self.workspace_mount}:/workspace"])
            docker_cmd.extend(["-w", target_cwd])
        else:
            # No mount: use the provided cwd directly (caller's responsibility to ensure it exists in container)
            docker_cmd.extend(["-w", target_cwd])

        docker_cmd.extend([self.image, "sh", "-c", command])

        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=exec_timeout,
            )
            return {
                "output": result.stdout + result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "output": f"Error: Command timed out after {exec_timeout}s",
                "returncode": 124,
                "error_code": "timeout",
            }
        except FileNotFoundError:
            return {
                "output": "Error: Docker CLI not found. Install Docker and ensure 'docker' is in PATH.",
                "returncode": 127,
                "error_code": "cli_missing",
            }
        except Exception as e:
            return {
                "output": f"Error: Docker execution failed: {str(e)}",
                "returncode": 1,
                "error_code": "execution_failed",
            }
