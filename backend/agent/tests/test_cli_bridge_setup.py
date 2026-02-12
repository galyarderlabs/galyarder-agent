from __future__ import annotations

import subprocess
from pathlib import Path

from g_agent.cli.commands import (
    _bridge_build_id_path,
    _bridge_needs_rebuild,
    _bridge_source_signature,
    _get_bridge_dir,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _create_bridge_source(path: Path) -> None:
    _write(path / "package.json", '{"name":"bridge","scripts":{"build":"tsc","start":"node dist/index.js"}}')
    _write(path / "package-lock.json", '{"name":"bridge","lockfileVersion":3}')
    _write(path / "tsconfig.json", '{"compilerOptions":{"target":"es2022"}}')
    _write(path / "src" / "index.ts", "console.log('bridge');")
    _write(path / "src" / "server.ts", "export const server = true;")


def test_bridge_source_signature_changes_when_source_changes(tmp_path: Path):
    source = tmp_path / "bridge-src"
    _create_bridge_source(source)

    before = _bridge_source_signature(source)
    _write(source / "src" / "server.ts", "export const server = false;")
    after = _bridge_source_signature(source)

    assert before != after


def test_bridge_needs_rebuild_decision_logic(tmp_path: Path):
    bridge_dir = tmp_path / "bridge"
    expected = "abc123"

    assert _bridge_needs_rebuild(bridge_dir, expected_build_id=expected, force_rebuild=False) is True

    _write(bridge_dir / "dist" / "index.js", "console.log('ok');")
    _bridge_build_id_path(bridge_dir).write_text(expected, encoding="utf-8")
    assert _bridge_needs_rebuild(bridge_dir, expected_build_id=expected, force_rebuild=False) is False

    _bridge_build_id_path(bridge_dir).write_text("other", encoding="utf-8")
    assert _bridge_needs_rebuild(bridge_dir, expected_build_id=expected, force_rebuild=False) is True
    assert _bridge_needs_rebuild(bridge_dir, expected_build_id=expected, force_rebuild=True) is True


def test_get_bridge_dir_rebuilds_when_source_signature_changes(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(data_dir))

    fake_repo = tmp_path / "fake-repo"
    fake_cmd_path = fake_repo / "g_agent" / "cli" / "commands.py"
    _write(fake_cmd_path, "# fake commands path")
    source = fake_repo / "g_agent" / "bridge"
    _create_bridge_source(source)

    monkeypatch.setattr("g_agent.cli.commands.__file__", str(fake_cmd_path))
    monkeypatch.setattr("shutil.which", lambda tool: "/usr/bin/npm" if tool == "npm" else None)

    calls: list[tuple[str, ...]] = []

    def fake_run(
        cmd: list[str],
        cwd: Path | None = None,
        check: bool = False,
        capture_output: bool = False,
        text: bool = False,
    ) -> subprocess.CompletedProcess:
        del check, capture_output, text
        calls.append(tuple(cmd))
        if cmd == ["npm", "run", "build"] and cwd is not None:
            _write(Path(cwd) / "dist" / "index.js", "console.log('built');")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("subprocess.run", fake_run)

    first = _get_bridge_dir()
    assert first == data_dir / "bridge"
    assert calls == [("npm", "install"), ("npm", "run", "build")]

    calls.clear()
    second = _get_bridge_dir()
    assert second == first
    assert calls == []

    _write(source / "src" / "server.ts", "export const server = 'changed';")
    third = _get_bridge_dir()
    assert third == first
    assert calls == [("npm", "install"), ("npm", "run", "build")]
