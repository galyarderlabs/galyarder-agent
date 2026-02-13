import asyncio
from typing import Any

from g_agent.agent.loop import AgentLoop
from g_agent.agent.workflow_packs import (
    build_workflow_pack_prompt,
    list_workflow_packs,
    resolve_workflow_pack_request,
)
from g_agent.bus.queue import MessageBus
from g_agent.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class CaptureProvider(LLMProvider):
    def __init__(self):
        super().__init__(api_key=None, api_base=None)
        self.last_user_message = ""

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        for item in reversed(messages):
            if item.get("role") == "user":
                self.last_user_message = str(item.get("content", ""))
                break
        return LLMResponse(content="ok")

    def get_default_model(self) -> str:
        return "dummy-model"


class SilentPackProvider(LLMProvider):
    def __init__(self):
        super().__init__(api_key=None, api_base=None)
        self.calls = 0

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(
                content="Sending media payload...",
                tool_calls=[
                    ToolCallRequest(
                        id="tool-msg-1",
                        name="message",
                        arguments={"content": "daily pack delivered"},
                    )
                ],
            )
        return LLMResponse(content="This should be suppressed in silent mode.")

    def get_default_model(self) -> str:
        return "dummy-model"


class ApprovalAwareSilentPackProvider(LLMProvider):
    def __init__(self):
        super().__init__(api_key=None, api_base=None)
        self.calls = 0

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        self.calls += 1
        if self.calls == 1:
            return LLMResponse(
                content="Sending media payload...",
                tool_calls=[
                    ToolCallRequest(
                        id="tool-msg-1",
                        name="message",
                        arguments={"content": "daily pack delivered"},
                    )
                ],
            )

        approval_denied = False
        for item in reversed(messages):
            if item.get("role") != "tool":
                continue
            content = str(item.get("content", ""))
            if "Approval required for tool 'message'" in content:
                approval_denied = True
                break

        if approval_denied:
            return LLMResponse(content="Approval required for tool 'message'. Resend with approve message.")
        return LLMResponse(content="This should be suppressed in silent mode.")

    def get_default_model(self) -> str:
        return "dummy-model"


def test_workflow_pack_resolver_and_prompt():
    packs = list_workflow_packs()
    assert "daily_brief" in packs
    assert "meeting_prep" in packs
    assert "inbox_zero_batch" in packs

    resolved = resolve_workflow_pack_request("/pack daily")
    assert resolved == ("daily_brief", "")

    resolved_with_context = resolve_workflow_pack_request(
        "run workflow pack meeting_prep investor sync"
    )
    assert resolved_with_context == ("meeting_prep", "investor sync")

    prompt = build_workflow_pack_prompt("inbox", "focus on urgent clients")
    assert "Workflow Pack: inbox_zero_batch" in prompt
    assert "focus on urgent clients" in prompt

    voice_prompt = build_workflow_pack_prompt("daily", "owner updates --voice")
    assert "Voice mode (`--voice`) requested." in voice_prompt
    assert "`media_type`: `voice`" in voice_prompt
    assert "User context: owner updates --voice" not in voice_prompt
    assert "User context: owner updates" in voice_prompt
    assert "owner updates" in voice_prompt

    image_prompt = build_workflow_pack_prompt("daily", "owner updates --image")
    assert "Image mode (`--image`) requested." in image_prompt
    assert "`media_type`: `image`" in image_prompt
    assert "User context: owner updates --image" not in image_prompt
    assert "User context: owner updates" in image_prompt

    both_prompt = build_workflow_pack_prompt("daily", "owner updates --voice --image")
    assert "Multi mode requested" in both_prompt
    assert "`media_type`: `image`" in both_prompt
    assert "`media_type`: `voice`" in both_prompt

    sticker_prompt = build_workflow_pack_prompt("daily", "owner updates --sticker")
    assert "Sticker mode (`--sticker`) requested." in sticker_prompt
    assert "`media_type`: `sticker`" in sticker_prompt

    triple_prompt = build_workflow_pack_prompt("daily", "owner updates --sticker --voice --image")
    assert "Multi mode requested" in triple_prompt
    assert "`media_type`: `sticker`" in triple_prompt
    assert "`media_type`: `image`" in triple_prompt
    assert "`media_type`: `voice`" in triple_prompt

    silent_prompt = build_workflow_pack_prompt("daily", "owner updates --image --silent")
    assert "Silent mode requested (`--silent`)" in silent_prompt

    silent_only_prompt = build_workflow_pack_prompt("daily", "owner updates --silent")
    assert "`--silent` was requested without media mode" in silent_only_prompt


def test_agent_loop_transforms_pack_message(tmp_path, monkeypatch):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    provider = CaptureProvider()
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="dummy-model",
        max_iterations=2,
        enable_reflection=False,
    )

    result = asyncio.run(
        loop.process_direct(
            content="/pack daily_brief top priority revenue today",
            session_key="cli:pack",
            channel="cli",
            chat_id="pack",
        )
    )
    assert result == "ok"
    assert "Workflow Pack: daily_brief" in provider.last_user_message
    assert "top priority revenue today" in provider.last_user_message


def test_agent_loop_silent_pack_suppresses_text_outbound(tmp_path, monkeypatch):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    provider = SilentPackProvider()
    bus = MessageBus()
    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        model="dummy-model",
        max_iterations=3,
        enable_reflection=False,
        approval_mode="confirm",
        tool_policy={"message": "allow"},
    )

    result = asyncio.run(
        loop.process_direct(
            content="/pack daily_brief focus revenue --image --silent",
            session_key="cli:silent-pack",
            channel="cli",
            chat_id="pack",
        )
    )

    assert result == ""
    assert bus.outbound_size == 1
    outbound = asyncio.run(bus.consume_outbound())
    assert outbound.content == "daily pack delivered"


def test_agent_loop_silent_without_media_flags_keeps_text(tmp_path, monkeypatch):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    provider = SilentPackProvider()
    bus = MessageBus()
    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        model="dummy-model",
        max_iterations=3,
        enable_reflection=False,
    )

    result = asyncio.run(
        loop.process_direct(
            content="/pack daily_brief focus revenue --silent",
            session_key="cli:not-silent-pack",
            channel="cli",
            chat_id="pack",
        )
    )

    assert "suppressed" in result.lower()
    assert bus.outbound_size == 1


def test_agent_loop_pack_voice_silent_returns_approval_hint_when_message_not_approved(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    provider = ApprovalAwareSilentPackProvider()
    bus = MessageBus()
    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        model="dummy-model",
        max_iterations=3,
        enable_reflection=False,
        approval_mode="confirm",
        tool_policy={"message": "ask"},
    )

    result = asyncio.run(
        loop.process_direct(
            content="/pack daily_brief focus revenue --voice --silent",
            session_key="cli:pack-approval-required",
            channel="telegram",
            chat_id="pack",
            sender_id="6218572023|galyarderlabs",
        )
    )

    assert "approval required" in result.lower()
    assert "approve message" in result.lower()
