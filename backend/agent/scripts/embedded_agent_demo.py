#!/usr/bin/env python3
"""Runnable demo for the embeddable g_agent Agent API."""

from __future__ import annotations

import argparse
import asyncio
import sys

from g_agent.agent import Agent

DEFAULT_PROMPT = "Summarize my top priorities today"
DEFAULT_SESSION_KEY = "embed:demo"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run embeddable Agent API demo.")
    parser.add_argument(
        "--mode",
        choices=("sync", "async"),
        default="sync",
        help="Execution mode for the demo.",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Prompt to send to the embedded Agent.",
    )
    parser.add_argument(
        "--session-key",
        default=DEFAULT_SESSION_KEY,
        help="Session key passed to Agent.ask_sync()/Agent.ask().",
    )
    return parser.parse_args()


def run_sync(prompt: str, session_key: str) -> str:
    agent = Agent()
    try:
        return agent.ask_sync(prompt, session_key=session_key)
    finally:
        agent.close()


async def run_async(prompt: str, session_key: str) -> str:
    async with Agent() as agent:
        return await agent.ask(prompt, session_key=session_key)


def main() -> int:
    args = parse_args()

    try:
        if args.mode == "sync":
            result = run_sync(args.prompt, args.session_key)
        else:
            result = asyncio.run(run_async(args.prompt, args.session_key))
    except Exception as exc:
        print(f"Embedded Agent demo failed: {exc}", file=sys.stderr)
        print(
            "Hint: verify provider configuration in ~/.g-agent/config.json "
            "or pass a custom provider when embedding.",
            file=sys.stderr,
        )
        return 1

    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
