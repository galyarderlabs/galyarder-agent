import asyncio
import json
from pathlib import Path

import pytest

from g_agent.agent.loop import AgentLoop
from g_agent.agent.runtime import TaskCheckpointStore
from g_agent.bus.queue import MessageBus
from g_agent.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class DummyProvider(LLMProvider):
    def __init__(self, responses: list[LLMResponse] | None = None, error: Exception | None = None):
        super().__init__(api_key=None, api_base=None)
        self._responses = list(responses or [])
        self._error = error

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        if self._error is not None:
            raise self._error
        if self._responses:
            return self._responses.pop(0)
        return LLMResponse(content="ok")

    def get_default_model(self) -> str:
        return "dummy-model"


def _load_checkpoint_files(tasks_dir: Path) -> list[dict]:
    items = []
    for path in sorted(tasks_dir.glob("*.json")):
        items.append(json.loads(path.read_text(encoding="utf-8")))
    return items


def test_checkpoint_store_lifecycle(tmp_path: Path):
    store = TaskCheckpointStore(tmp_path)
    task_id = store.start(
        kind="test",
        session_key="cli:test",
        channel="cli",
        chat_id="test",
        sender_id="user",
        input_text="hello world",
    )
    assert task_id

    assert store.append_event(task_id, "step", "running step")
    assert store.complete(task_id, "done", metadata={"iterations": 1})

    payload = store.get(task_id)
    assert payload is not None
    assert payload["status"] == "ok"
    assert payload["metadata"]["iterations"] == 1
    assert payload["events"][-1]["event"] == "complete"


def test_agent_loop_writes_success_checkpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    provider = DummyProvider(responses=[LLMResponse(content="pong")])
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="dummy-model",
        max_iterations=3,
        enable_reflection=False,
    )

    result = asyncio.run(
        loop.process_direct(
            content="ping",
            session_key="cli:ok",
            channel="cli",
            chat_id="ok",
        )
    )
    assert result == "pong"

    checkpoints = _load_checkpoint_files(tmp_path / "state" / "tasks")
    assert len(checkpoints) == 1
    checkpoint = checkpoints[0]
    assert checkpoint["status"] == "ok"
    assert checkpoint["session_key"] == "cli:ok"
    assert checkpoint["metadata"]["iterations"] == 1


def test_agent_loop_writes_error_checkpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    provider = DummyProvider(error=RuntimeError("provider failed"))
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="dummy-model",
        max_iterations=2,
        enable_reflection=False,
    )

    with pytest.raises(RuntimeError, match="provider failed"):
        asyncio.run(
            loop.process_direct(
                content="trigger error",
                session_key="cli:err",
                channel="cli",
                chat_id="err",
            )
        )

    checkpoints = _load_checkpoint_files(tmp_path / "state" / "tasks")
    assert len(checkpoints) == 1
    checkpoint = checkpoints[0]
    assert checkpoint["status"] == "error"
    assert "provider failed" in checkpoint["error"]


def test_agent_loop_marks_previous_running_as_resumed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    store = TaskCheckpointStore(tmp_path)
    old_task_id = store.start(
        kind="inbound_message",
        session_key="cli:resume",
        channel="cli",
        chat_id="resume",
        sender_id="user",
        input_text="unfinished",
    )

    provider = DummyProvider(responses=[LLMResponse(content="done now")])
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
            content="continue",
            session_key="cli:resume",
            channel="cli",
            chat_id="resume",
        )
    )
    assert result == "done now"

    old_payload = store.get(old_task_id)
    assert old_payload is not None
    assert old_payload["metadata"]["resume_count"] == 1
    assert old_payload["events"][-1]["event"] == "resume"


def test_agent_loop_rewrites_stale_voice_unavailable_reply_when_voice_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    provider = DummyProvider(
        responses=[
            LLMResponse(
                content=(
                    "Maaf bro, gua belum bisa kirim voice note. "
                    "Gua cuma bisa komunikasi lewat teks sekarang."
                )
            )
        ]
    )
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
            content="ngomong pake voice ke gua",
            session_key="cli:voice-fix",
            channel="cli",
            chat_id="voice-fix",
        )
    )

    assert "gue bisa kirim voice note" in result.lower()
    assert "belum bisa kirim voice note" not in result.lower()


def test_agent_loop_keeps_stale_text_when_voice_requested_and_message_tool_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    stale_text = "Maaf bro, gua cuma bisa komunikasi lewat teks sekarang."
    provider = DummyProvider(
        responses=[
            LLMResponse(
                content="",
                tool_calls=[
                    ToolCallRequest(
                        id="call_1",
                        name="message",
                        arguments={"content": "nih voice", "media_type": "voice"},
                    )
                ],
            ),
            LLMResponse(content=stale_text),
        ]
    )
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="dummy-model",
        max_iterations=3,
        enable_reflection=False,
        approval_mode="off",
    )

    result = asyncio.run(
        loop.process_direct(
            content="tolong kirim voice note",
            session_key="cli:voice-tool-ok",
            channel="cli",
            chat_id="voice-tool-ok",
        )
    )

    assert result == stale_text
    assert "gue bisa kirim voice note" not in result.lower()


def test_agent_loop_rewrites_stale_english_voice_denial_when_voice_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    provider = DummyProvider(
        responses=[
            LLMResponse(
                content=(
                    "I don't have the ability to generate or play voice/audio. "
                    "I'm a text-based coding assistant, and I can't produce speech or audio output."
                )
            )
        ]
    )
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
            content="say something about me use voice",
            session_key="cli:voice-fix-en",
            channel="cli",
            chat_id="voice-fix-en",
        )
    )

    assert "gue bisa kirim voice note" in result.lower()
    assert "text-based coding assistant" not in result.lower()


def test_agent_loop_rewrites_english_text_only_denial_when_voice_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    provider = DummyProvider(
        responses=[
            LLMResponse(
                content=(
                    "I appreciate the enthusiasm, but I'm a text-based AI assistant. "
                    "I can only communicate through text and I can't generate voice messages."
                )
            )
        ]
    )
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
            content="say something about me use voice",
            session_key="cli:voice-fix-en2",
            channel="cli",
            chat_id="voice-fix-en2",
        )
    )

    assert "gue bisa kirim voice note" in result.lower()
    assert "i can only communicate through text" not in result.lower()


def test_agent_loop_rewrites_approval_required_message_for_voice_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    provider = DummyProvider(
        responses=[
            LLMResponse(
                content=(
                    "Approval required for tool 'message'. "
                    "Resend your request with `approve message` (or `approve all`)."
                )
            )
        ]
    )
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
            content="say something about me use voice",
            session_key="cli:voice-fix-approval",
            channel="cli",
            chat_id="voice-fix-approval",
        )
    )

    assert "gue bisa kirim voice note" in result.lower()
    assert "approve message" not in result.lower()


def test_agent_loop_auto_sends_voice_on_telegram_without_message_tool(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    provider = DummyProvider(
        responses=[
            LLMResponse(
                content=(
                    "I don't have the ability to generate or play voice/audio. "
                    "I'm a text-based coding assistant, and I can't produce speech or audio output."
                )
            )
        ]
    )

    captured: list[object] = []

    async def _send(msg):
        captured.append(msg)

    bus = MessageBus()
    bus.publish_outbound = _send
    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        model="dummy-model",
        max_iterations=2,
        enable_reflection=False,
        approval_mode="off",
    )

    result = asyncio.run(
        loop.process_direct(
            content="say something about me use voice",
            session_key="telegram:auto-voice",
            channel="telegram",
            chat_id="12345",
            sender_id="6218572023|galyarderlabs",
        )
    )

    assert result == ""
    assert len(captured) == 1
    outbound = captured[0]
    assert outbound.channel == "telegram"
    assert outbound.chat_id == "12345"
    assert outbound.metadata.get("media_type") == "voice"


def test_agent_loop_auto_sends_voice_for_natural_voice_phrase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    provider = DummyProvider(
        responses=[
            LLMResponse(
                content=(
                    "Gue bisa kirim voice note. Coba ulangi request dengan format eksplisit: "
                    "/pack daily_brief --voice --silent atau minta gue kirim pakai tool message dengan media_type=voice."
                )
            )
        ]
    )

    captured: list[object] = []

    async def _send(msg):
        captured.append(msg)

    bus = MessageBus()
    bus.publish_outbound = _send
    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        model="dummy-model",
        max_iterations=2,
        enable_reflection=False,
        approval_mode="off",
    )

    result = asyncio.run(
        loop.process_direct(
            content=(
                "now, tell me about urself use a voice tool, "
                "when I say use voice just use a tool for voice don't ask again"
            ),
            session_key="telegram:auto-voice-natural",
            channel="telegram",
            chat_id="12345",
            sender_id="6218572023|galyarderlabs",
        )
    )

    assert result == ""
    assert len(captured) == 1
    outbound = captured[0]
    assert outbound.channel == "telegram"
    assert outbound.chat_id == "12345"
    assert outbound.metadata.get("media_type") == "voice"


def test_agent_loop_rewrites_voice_tool_denial_phrase_when_voice_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    provider = DummyProvider(
        responses=[
            LLMResponse(
                content=(
                    "I don't have a voice tool or text-to-speech capability. "
                    "I'm a text-based AI coding assistant — I can only communicate through written text."
                )
            )
        ]
    )
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
            content="say something about me use voice",
            session_key="cli:voice-tool-denial",
            channel="cli",
            chat_id="voice-tool-denial",
        )
    )

    assert "gue bisa kirim voice note" in result.lower()
    assert "don't have a voice tool" not in result.lower()


def test_agent_loop_auto_voice_does_not_echo_denial_text_as_caption(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(
        "g_agent.agent.tools.message.MessageTool._synthesize_speech",
        lambda self, text, media_type: "/tmp/synth.ogg",
    )
    provider = DummyProvider(
        responses=[
            LLMResponse(
                content=(
                    "I don't have a voice tool or text-to-speech capability. "
                    "I'm a text-based AI coding assistant — I can only communicate through written text."
                )
            )
        ]
    )

    captured: list[object] = []

    async def _send(msg):
        captured.append(msg)

    bus = MessageBus()
    bus.publish_outbound = _send
    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        model="dummy-model",
        max_iterations=2,
        enable_reflection=False,
        approval_mode="off",
    )

    result = asyncio.run(
        loop.process_direct(
            content=(
                "now, tell me about urself use a voice tool, "
                "when I say use voice just use a tool for voice don't ask again"
            ),
            session_key="telegram:auto-voice-no-denial-caption",
            channel="telegram",
            chat_id="12345",
            sender_id="6218572023|galyarderlabs",
        )
    )

    assert result == ""
    assert len(captured) == 1
    outbound = captured[0]
    assert outbound.metadata.get("media_type") == "voice"
    assert "don't have a voice tool" not in outbound.content.lower()
    assert "don't have a voice tool" not in str(outbound.metadata.get("caption", "")).lower()


def test_agent_loop_auto_voice_uses_contextual_reply_instead_of_static_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(
        "g_agent.agent.tools.message.MessageTool._synthesize_speech",
        lambda self, text, media_type: "/tmp/synth.ogg",
    )
    provider = DummyProvider(
        responses=[
            LLMResponse(content="Lo orangnya direct, tegas, dan fokus hasil.")
        ]
    )

    captured: list[object] = []

    async def _send(msg):
        captured.append(msg)

    bus = MessageBus()
    bus.publish_outbound = _send
    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        model="dummy-model",
        max_iterations=3,
        enable_reflection=False,
        approval_mode="off",
    )

    result = asyncio.run(
        loop.process_direct(
            content=(
                "now, tell me about urself use a voice tool, "
                "when I say use voice just use a tool for voice don't ask again dude"
            ),
            session_key="telegram:auto-voice-contextual",
            channel="telegram",
            chat_id="12345",
            sender_id="6218572023|galyarderlabs",
        )
    )

    assert result == ""
    assert len(captured) == 1
    outbound = captured[0]
    assert outbound.metadata.get("media_type") == "voice"
    assert outbound.content == "Lo orangnya direct, tegas, dan fokus hasil."
    assert "halo, ini voice note" not in outbound.content.lower()


def test_agent_loop_auto_voice_handles_pake_suara_phrase_with_about_me_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(
        "g_agent.agent.tools.message.MessageTool._synthesize_speech",
        lambda self, text, media_type: "/tmp/synth.ogg",
    )
    provider = DummyProvider(
        responses=[
            LLMResponse(
                content=(
                    "I appreciate the enthusiasm, but I don't have a voice tool. "
                    "I'm text-based and can only communicate through written text."
                )
            )
        ]
    )

    captured: list[object] = []

    async def _send(msg):
        captured.append(msg)

    bus = MessageBus()
    bus.publish_outbound = _send
    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        model="dummy-model",
        max_iterations=2,
        enable_reflection=False,
        approval_mode="off",
    )

    result = asyncio.run(
        loop.process_direct(
            content="jelasin tentang gua pake suara dong",
            session_key="telegram:auto-voice-pake-suara",
            channel="telegram",
            chat_id="12345",
            sender_id="6218572023|galyarderlabs",
        )
    )

    assert result == ""
    assert len(captured) == 1
    outbound = captured[0]
    assert outbound.metadata.get("media_type") == "voice"
    assert "voice note" not in outbound.content.lower()
    assert "can't" not in outbound.content.lower()
    assert "text-based" not in outbound.content.lower()


def test_agent_loop_auto_voice_handles_indonesian_text_only_denial_phrase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(
        "g_agent.agent.tools.message.MessageTool._synthesize_speech",
        lambda self, text, media_type: "/tmp/synth.ogg",
    )
    provider = DummyProvider(
        responses=[
            LLMResponse(
                content=(
                    "Maaf, saya tidak bisa melakukan analisis menggunakan suara. "
                    "Saya adalah asisten coding berbasis teks — saya tidak bisa menghasilkan atau memproses audio/suara."
                )
            )
        ]
    )

    captured: list[object] = []

    async def _send(msg):
        captured.append(msg)

    bus = MessageBus()
    bus.publish_outbound = _send
    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        model="dummy-model",
        max_iterations=2,
        enable_reflection=False,
        approval_mode="off",
    )

    result = asyncio.run(
        loop.process_direct(
            content="analisis pake suara",
            session_key="telegram:auto-voice-id-denial",
            channel="telegram",
            chat_id="12345",
            sender_id="6218572023|galyarderlabs",
        )
    )

    assert result == ""
    assert len(captured) == 1
    outbound = captured[0]
    assert outbound.metadata.get("media_type") == "voice"
    assert "tidak bisa melakukan analisis menggunakan suara" not in outbound.content.lower()
    assert "berbasis teks" not in outbound.content.lower()


def test_agent_loop_auto_voice_recovers_from_approve_all_meta_reply(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(
        "g_agent.agent.tools.message.MessageTool._synthesize_speech",
        lambda self, text, media_type: "/tmp/synth.ogg",
    )
    provider = DummyProvider(
        responses=[
            LLMResponse(
                content=(
                    "Revised Answer: Mohon ketik approve all agar saya bisa membuat file suara "
                    "untuk jawaban ini."
                )
            ),
            LLMResponse(
                content=(
                    "Intinya, versi satu kalimatnya: lo tipe yang direct, cepat eksekusi, "
                    "dan fokus ke hasil nyata."
                )
            ),
        ]
    )

    captured: list[object] = []

    async def _send(msg):
        captured.append(msg)

    bus = MessageBus()
    bus.publish_outbound = _send
    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        model="dummy-model",
        max_iterations=3,
        enable_reflection=False,
        approval_mode="off",
    )

    result = asyncio.run(
        loop.process_direct(
            content="jelaskan ulang dalam 1 kalimat dengan suara",
            session_key="telegram:auto-voice-approve-all-meta",
            channel="telegram",
            chat_id="12345",
            sender_id="6218572023|galyarderlabs",
        )
    )

    assert result == ""
    assert len(captured) == 1
    outbound = captured[0]
    assert outbound.metadata.get("media_type") == "voice"
    assert "approve all" not in outbound.content.lower()
    assert "mohon ketik" not in outbound.content.lower()
    assert outbound.content == (
        "Intinya, versi satu kalimatnya: lo tipe yang direct, cepat eksekusi, "
        "dan fokus ke hasil nyata."
    )


def test_agent_loop_does_not_auto_send_voice_for_non_delivery_voice_topic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(
        "g_agent.agent.tools.message.MessageTool._synthesize_speech",
        lambda self, text, media_type: "/tmp/synth.ogg",
    )
    provider = DummyProvider(responses=[LLMResponse(content="Kemungkinan suara kamu lagi serak karena capek.")])

    captured: list[object] = []

    async def _send(msg):
        captured.append(msg)

    bus = MessageBus()
    bus.publish_outbound = _send
    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        model="dummy-model",
        max_iterations=2,
        enable_reflection=False,
        approval_mode="off",
    )

    result = asyncio.run(
        loop.process_direct(
            content="my voice is raspy today, what should I do?",
            session_key="telegram:no-auto-voice-topic",
            channel="telegram",
            chat_id="12345",
            sender_id="6218572023|galyarderlabs",
        )
    )

    assert result == "Kemungkinan suara kamu lagi serak karena capek."
    assert captured == []


def test_agent_loop_rewrites_indonesian_cross_conversation_memory_denial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    provider = DummyProvider(
        responses=[
            LLMResponse(
                content=(
                    "Saya sebenarnya tidak memiliki memori lintas percakapan. "
                    "Setiap conversation dimulai dari nol."
                )
            )
        ]
    )
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
            content="lu ingat apa aja tentang gua? di semua conversation?",
            session_key="telegram:memory-denial-id",
            channel="telegram",
            chat_id="12345",
            sender_id="6218572023|galyarderlabs",
        )
    )

    assert "tidak memiliki memori lintas percakapan" not in result.lower()
    assert "memori persisten lintas sesi" in result.lower()


def test_agent_loop_does_not_auto_send_voice_when_user_negates_voice_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(
        "g_agent.agent.tools.message.MessageTool._synthesize_speech",
        lambda self, text, media_type: "/tmp/synth.ogg",
    )
    provider = DummyProvider(
        responses=[LLMResponse(content="Siap, gue jawab via teks tanpa voice note.")]
    )

    captured: list[object] = []

    async def _send(msg):
        captured.append(msg)

    bus = MessageBus()
    bus.publish_outbound = _send
    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        model="dummy-model",
        max_iterations=2,
        enable_reflection=False,
        approval_mode="off",
    )

    result = asyncio.run(
        loop.process_direct(
            content="do not use voice, jawab teks aja",
            session_key="telegram:no-auto-voice-negated",
            channel="telegram",
            chat_id="12345",
            sender_id="6218572023|galyarderlabs",
        )
    )

    assert result == "Siap, gue jawab via teks tanpa voice note."
    assert captured == []
