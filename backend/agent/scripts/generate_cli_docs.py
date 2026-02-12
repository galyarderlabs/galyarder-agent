#!/usr/bin/env python3
"""Generate docs/cli-commands.md from the current Typer command tree."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import click
from typer.main import get_command

SCRIPT_PATH = Path(__file__).resolve()
AGENT_DIR = SCRIPT_PATH.parents[1]
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from g_agent.cli.commands import app  # noqa: E402


def _find_repo_root(start: Path) -> Path:
    for path in (start, *start.parents):
        if (path / "mkdocs.yml").exists():
            return path
    raise RuntimeError("Could not find repository root (missing mkdocs.yml).")


def _normalize_sentence(text: str) -> str:
    value = text.strip()
    if not value:
        return value
    if not value.endswith("."):
        value += "."
    return value


def _option_flags(option: click.Option) -> str:
    flags = [*option.opts, *option.secondary_opts]
    return ", ".join(f"`{flag}`" for flag in flags)


def _option_help(option: click.Option) -> str:
    help_text = (option.help or "").strip()
    if not help_text and "--version" in option.opts:
        help_text = "Show version"
    return _normalize_sentence(help_text)


def _short_help(command: click.Command) -> str:
    return _normalize_sentence(command.get_short_help_str(limit=200))


def _table_cell(text: str) -> str:
    return text.replace("|", "\\|")


def render_markdown() -> str:
    root_command = get_command(app)
    top_level_commands = list(root_command.commands.items())

    lines: list[str] = [
        "# CLI Commands",
        "",
        "_This page is auto-generated from `g_agent.cli.commands`._",
        "",
        "Regenerate with:",
        "",
        "```bash",
        "python backend/agent/scripts/generate_cli_docs.py",
        "```",
        "",
        "## Global usage",
        "",
        "```bash",
        "g-agent [OPTIONS] COMMAND [ARGS]...",
        "```",
        "",
        "### Global options",
        "",
    ]

    for parameter in root_command.params:
        if not isinstance(parameter, click.Option) or parameter.hidden:
            continue
        flags = _option_flags(parameter)
        help_text = _option_help(parameter) or "No description."
        lines.append(f"- {flags}: {help_text}")

    lines.append("- `--help`: Show help and exit.")
    lines.extend(
        [
            "",
            "## Top-level commands",
            "",
            "| Command | Description |",
            "| --- | --- |",
        ]
    )

    for name, command in top_level_commands:
        description = _table_cell(_short_help(command))
        lines.append(f"| `{name}` | {description} |")

    for name, command in top_level_commands:
        if not isinstance(command, click.Group):
            continue
        lines.extend(
            [
                "",
                f"## `{name}` subcommands",
                "",
                "```bash",
                f"g-agent {name} [COMMAND] --help",
                "```",
                "",
            ]
        )
        for subcommand_name, subcommand in command.commands.items():
            lines.append(f"- `{subcommand_name}`: {_short_help(subcommand)}")

    lines.extend(
        [
            "",
            "## Quick examples",
            "",
            "```bash",
            "g-agent --help",
            "g-agent help",
            "g-agent version",
            "g-agent channels --help",
            "g-agent channels login",
            "g-agent google --help",
            "g-agent cron --help",
            "g-agent policy --help",
            "```",
            "",
        ]
    )

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate docs/cli-commands.md from Typer CLI.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/cli-commands.md"),
        help="Output path relative to repo root (default: docs/cli-commands.md).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = _find_repo_root(SCRIPT_PATH.parent)
    output_path = args.output
    if not output_path.is_absolute():
        output_path = repo_root / output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(), encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
