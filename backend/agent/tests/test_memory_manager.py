"""Tests for the memory manager layer."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from g_agent.agent.context import ContextBuilder
from g_agent.agent.memory import MemoryStore
from g_agent.memory.context import fence_memory_context, sanitize_memory_context
from g_agent.memory.manager import MemoryManager


@dataclass
class FakeProvider:
    name: str
    builtin: bool = False
    text: str = "fake memory"
    fail: bool = False
    synced: bool = False

    def system_prompt_block(self) -> str:
        return ""

    def prefetch(
        self,
        *,
        query: str | None = None,
        session_id: str = "",
        include_full: bool = True,
    ) -> str:
        if self.fail:
            raise RuntimeError("provider failed")
        return self.text

    def sync_turn(
        self,
        *,
        user_content: str,
        assistant_content: str,
        session_id: str = "",
    ) -> None:
        self.synced = True

    def get_tool_schemas(self) -> list[dict[str, Any]]:
        return []

    async def handle_tool_call(self, name: str, arguments: dict[str, Any]) -> str | None:
        return None


def test_memory_context_fencing_strips_nested_tags():
    raw = '<memory-context provider="bad">remember this</memory-context>'

    assert sanitize_memory_context(raw) == "remember this"
    assert fence_memory_context("bad provider", raw) == (
        '<memory-context provider="bad-provider" role="reference-only">\n'
        "remember this\n"
        "</memory-context>"
    )


def test_memory_manager_registers_builtin_provider(tmp_path: Path):
    manager = MemoryManager(tmp_path)

    assert [provider.name for provider in manager.providers] == ["builtin"]


def test_memory_manager_rejects_multiple_external_providers(tmp_path: Path):
    with pytest.raises(ValueError, match="Only one external memory provider"):
        MemoryManager(
            tmp_path,
            providers=[
                FakeProvider("one"),
                FakeProvider("two"),
            ],
        )


def test_memory_manager_prefetch_fences_provider_output(tmp_path: Path):
    manager = MemoryManager(tmp_path, providers=[FakeProvider("external", text="owner likes tea")])

    context = manager.prefetch_all(query="tea", session_id="cli:default")

    assert '<memory-context provider="external" role="reference-only">' in context
    assert "owner likes tea" in context


def test_memory_manager_provider_failure_does_not_block_other_providers(tmp_path: Path):
    manager = MemoryManager(
        tmp_path,
        providers=[
            FakeProvider("broken", builtin=True, fail=True),
            FakeProvider("working", text="safe memory"),
        ],
    )

    context = manager.prefetch_all(query="anything")

    assert "safe memory" in context
    assert "broken" not in context


def test_context_builder_uses_fenced_memory_context(tmp_path: Path):
    store = MemoryStore(tmp_path)
    store.memory_file.write_text("Owner prefers concise updates.\n", encoding="utf-8")

    prompt = ContextBuilder(tmp_path).build_system_prompt()

    assert '<memory-context provider="builtin" role="reference-only">' in prompt
    assert "Owner prefers concise updates." in prompt
