"""Tests for trusted path roots outside the workspace."""

import asyncio
from pathlib import Path

from g_agent.agent.tools.filesystem import ReadFileTool
from g_agent.agent.tools.shell import ExecTool
from g_agent.config.loader import convert_to_camel
from g_agent.config.schema import Config


def test_config_accepts_allowed_paths() -> None:
    config = Config.model_validate(
        {
            "tools": {
                "restrict_to_workspace": True,
                "allowed_paths": ["/home/galyarder/Documents/Keiya"],
            }
        }
    )

    assert config.tools.allowed_paths == ["/home/galyarder/Documents/Keiya"]
    assert convert_to_camel(config.model_dump())["tools"]["allowedPaths"] == [
        "/home/galyarder/Documents/Keiya"
    ]


def test_read_file_allows_configured_external_root(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    trusted = tmp_path / "Keiya"
    outside = tmp_path / "outside"
    workspace.mkdir()
    trusted.mkdir()
    outside.mkdir()
    (trusted / "note.txt").write_text("trusted", encoding="utf-8")
    (outside / "secret.txt").write_text("outside", encoding="utf-8")

    tool = ReadFileTool(workspace=workspace, allowed_dirs=[workspace, trusted])

    assert asyncio.run(tool.execute(path=str(trusted / "note.txt"))) == "trusted"
    result = asyncio.run(tool.execute(path=str(outside / "secret.txt")))
    assert "outside allowed directories" in result


def test_exec_guard_allows_configured_external_root(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    trusted = tmp_path / "Keiya"
    outside = tmp_path / "outside"
    workspace.mkdir()
    trusted.mkdir()
    outside.mkdir()
    tool = ExecTool(
        working_dir=str(workspace),
        restrict_to_workspace=True,
        allowed_dirs=[workspace, trusted],
    )

    assert tool._guard_command(f"ls {trusted}", str(workspace)) is None
    result = tool._guard_command(f"ls {outside}", str(workspace))
    assert result is not None
    assert "path outside allowed directories" in result
