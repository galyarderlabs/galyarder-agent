"""Approval state persistence tests."""

import asyncio
from pathlib import Path
from typing import Any

from g_agent.agent.loop import AgentLoop
from g_agent.bus.queue import MessageBus
from g_agent.channels.slash_commands import SlashCommandDispatcher
from g_agent.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from g_agent.security.approval_state import ApprovalStateStore
from g_agent.session.manager import SessionManager


class DummyProvider(LLMProvider):
    """Small provider that returns queued responses."""

    def __init__(self, responses: list[LLMResponse]):
        self.responses = list(responses)

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> LLMResponse:
        return self.responses.pop(0)

    def get_default_model(self) -> str:
        return "dummy-model"


def _patch_data_dir(monkeypatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr("g_agent.config.loader.get_data_path", lambda: data_dir)
    monkeypatch.setattr("g_agent.utils.helpers.get_data_path", lambda: data_dir)
    monkeypatch.setattr("g_agent.session.manager.get_data_path", lambda: data_dir)


def test_approval_state_store_persists_latest_status(tmp_path: Path) -> None:
    store = ApprovalStateStore(tmp_path)
    record = store.create_pending(
        session_key="cli:default",
        tool_name="exec",
        tool_args={"command": "uptime"},
    )

    reloaded = ApprovalStateStore(tmp_path)
    assert reloaded.get(record.id).status == "pending"

    reloaded.update_status(record.id, "denied", decision="deny")
    latest = ApprovalStateStore(tmp_path).get(record.id)
    assert latest is not None
    assert latest.status == "denied"
    assert latest.decision == "deny"


def test_agent_loop_stores_pending_approval_with_persisted_id(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _patch_data_dir(monkeypatch, tmp_path)
    provider = DummyProvider(
        [
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCallRequest(
                        id="tc1",
                        name="exec",
                        arguments={"command": "uptime"},
                    )
                ],
            ),
            LLMResponse(content="approval required"),
        ]
    )
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="dummy-model",
        max_iterations=2,
        enable_reflection=False,
        approval_mode="confirm",
        risky_tools=["exec"],
    )

    asyncio.run(
        loop.process_direct(
            content="run uptime",
            session_key="cli:default",
            channel="cli",
            chat_id="default",
        )
    )

    session = loop.sessions.get_or_create("cli:default")
    pending = session.metadata["pending_approvals"]
    approval_id = pending[0]["id"]
    record = ApprovalStateStore(tmp_path).get(approval_id)
    assert record is not None
    assert record.status == "pending"
    assert record.tool_name == "exec"
    assert record.tool_args == {"command": "uptime"}


def test_deny_command_updates_persisted_approval_state(tmp_path: Path, monkeypatch) -> None:
    _patch_data_dir(monkeypatch, tmp_path)
    store = ApprovalStateStore(tmp_path)
    record = store.create_pending(
        session_key="cli:default",
        tool_name="exec",
        tool_args={"command": "uptime"},
    )
    manager = SessionManager(tmp_path)
    session = manager.get_or_create("cli:default")
    session.metadata["pending_approvals"] = [
        {"id": record.id, "tool_name": "exec", "tool_args": {"command": "uptime"}}
    ]
    manager.save(session)

    dispatcher = SlashCommandDispatcher(tmp_path)
    result = asyncio.run(dispatcher.try_handle("/deny exec", "cli:default", "cli", "default"))

    assert "Denied pending approval" in result
    latest = ApprovalStateStore(tmp_path).get(record.id)
    assert latest is not None
    assert latest.status == "denied"


def test_approvals_command_lists_pending_ids(tmp_path: Path, monkeypatch) -> None:
    _patch_data_dir(monkeypatch, tmp_path)
    record = ApprovalStateStore(tmp_path).create_pending(
        session_key="cli:default",
        tool_name="exec",
        tool_args={"command": "uptime"},
    )

    dispatcher = SlashCommandDispatcher(tmp_path)
    result = asyncio.run(dispatcher.try_handle("/approvals", "cli:default", "cli", "default"))

    assert record.id in result
    assert "exec" in result
