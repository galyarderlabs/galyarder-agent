"""Product API server tests."""

from io import BytesIO
from pathlib import Path
from typing import Any

from aiohttp import FormData
from aiohttp.test_utils import TestClient, TestServer

from g_agent.api.server import APPROVALS_KEY, LEARNING_KEY, SESSIONS_KEY, create_app
from g_agent.config.schema import Config
from g_agent.learning.candidate import LearningCandidate
from g_agent.learning.queue import LearningQueue
from g_agent.security.approval_state import ApprovalStateStore
from g_agent.session.manager import SessionManager


class FakeAgent:
    """Minimal agent double for OpenAI-compatible chat tests."""

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def ask(
        self,
        content: str,
        *,
        session_key: str = "embed:default",
        channel: str = "embed",
        chat_id: str = "embed",
    ) -> str:
        self.calls.append(
            {
                "content": content,
                "session_key": session_key,
                "channel": channel,
                "chat_id": chat_id,
            }
        )
        return "api-ok"


async def _client(
    tmp_path: Path,
    monkeypatch,
    *,
    agent: Any | None = None,
    token: str = "",
) -> TestClient:
    monkeypatch.setenv("G_AGENT_DATA_DIR", str(tmp_path / "data"))
    config = Config()
    config.agents.defaults.workspace = str(tmp_path)
    config.agents.defaults.model = "test-model"
    config.agents.defaults.routing.fallback_models = ["fallback-model"]
    config.gateway.api_token = token
    manager = SessionManager(config.workspace_path)
    app = create_app(config=config, agent=agent, session_manager=manager)
    client = TestClient(TestServer(app))
    await client.start_server()
    return client


def _skill_md(name: str, body: str) -> str:
    return f"""---
name: {name}
description: Test skill for API learning apply coverage.
---
# {name}

{body}
"""


async def test_api_health_status_and_models(tmp_path: Path, monkeypatch) -> None:
    client = await _client(tmp_path, monkeypatch)
    try:
        health = await client.get("/health")
        assert health.status == 200
        assert await health.json() == {"status": "ok"}

        status = await client.get("/status")
        assert status.status == 200
        status_payload = await status.json()
        assert status_payload["status"] == "ok"
        assert status_payload["model"] == "test-model"

        models = await client.get("/v1/models")
        assert models.status == 200
        model_payload = await models.json()
        assert [item["id"] for item in model_payload["data"]] == [
            "test-model",
            "fallback-model",
        ]
    finally:
        await client.close()


async def test_api_lists_sessions_and_fetches_history(tmp_path: Path, monkeypatch) -> None:
    client = await _client(tmp_path, monkeypatch)
    try:
        manager: SessionManager = client.app[SESSIONS_KEY]
        session = manager.sqlite_store.get_or_create_session("api:chat-1")
        manager.sqlite_store.append_message(session["id"], "user", "hello")
        manager.sqlite_store.append_message(session["id"], "assistant", "world")

        listed = await client.get("/sessions?limit=5")
        assert listed.status == 200
        listed_payload = await listed.json()
        assert listed_payload["data"][0]["key"] == "api:chat-1"

        detail = await client.get(f"/sessions/{session['id']}")
        assert detail.status == 200
        detail_payload = await detail.json()
        assert detail_payload["session"]["id"] == session["id"]
        assert [msg["content"] for msg in detail_payload["messages"]] == ["hello", "world"]
    finally:
        await client.close()


async def test_api_media_upload_stores_file_and_session_ref(tmp_path: Path, monkeypatch) -> None:
    client = await _client(tmp_path, monkeypatch)
    try:
        data = FormData()
        data.add_field("session_key", "api:media-room")
        data.add_field("kind", "image")
        data.add_field("caption", "uploaded image")
        data.add_field(
            "file",
            BytesIO(b"fake image bytes"),
            filename="../photo.png",
            content_type="image/png",
        )

        response = await client.post("/media", data=data)

        assert response.status == 201
        payload = await response.json()
        media = payload["data"]
        assert media["session_key"] == "api:media-room"
        assert media["kind"] == "image"
        assert media["filename"] == "photo.png"
        path = Path(media["path"])
        assert path.is_file()
        assert path.read_bytes() == b"fake image bytes"

        manager: SessionManager = client.app[SESSIONS_KEY]
        session = manager.sqlite_store.get_session("api:media-room")
        assert session is not None
        history = manager.sqlite_store.get_history(session["id"], limit=1)
        assert history == [
            {
                "role": "user",
                "content": "uploaded image",
                "content_type": "media",
            }
        ]
        row = manager.sqlite_store._conn.execute(
            "SELECT kind, path, mime_type, sha256 FROM media_refs WHERE id = ?",
            (media["id"],),
        ).fetchone()
        assert row["kind"] == "image"
        assert row["path"] == media["path"]
        assert row["mime_type"] == "image/png"
        assert row["sha256"]
    finally:
        await client.close()


async def test_api_media_upload_requires_multipart_file(tmp_path: Path, monkeypatch) -> None:
    client = await _client(tmp_path, monkeypatch)
    try:
        response = await client.post("/media", json={"session_key": "api:media-room"})

        assert response.status == 400
        payload = await response.json()
        assert payload["error"]["code"] == "invalid_request"
    finally:
        await client.close()


async def test_api_auth_token_protects_non_health_routes(tmp_path: Path, monkeypatch) -> None:
    client = await _client(tmp_path, monkeypatch, token="secret")
    try:
        health = await client.get("/health")
        assert health.status == 200

        unauthorized = await client.get("/status")
        assert unauthorized.status == 401

        authorized = await client.get("/status", headers={"Authorization": "Bearer secret"})
        assert authorized.status == 200
    finally:
        await client.close()


async def test_openai_chat_completion_uses_agent(tmp_path: Path, monkeypatch) -> None:
    fake_agent = FakeAgent()
    client = await _client(tmp_path, monkeypatch, agent=fake_agent)
    try:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "test-model",
                "session_key": "api:room-1",
                "messages": [
                    {"role": "system", "content": "ignore"},
                    {"role": "user", "content": [{"type": "text", "text": "hello api"}]},
                ],
            },
        )
        assert response.status == 200
        payload = await response.json()
        assert payload["object"] == "chat.completion"
        assert payload["choices"][0]["message"] == {"role": "assistant", "content": "api-ok"}
        assert fake_agent.calls == [
            {
                "content": "hello api",
                "session_key": "api:room-1",
                "channel": "api",
                "chat_id": "room-1",
            }
        ]
    finally:
        await client.close()


async def test_openai_chat_completion_streams_sse(tmp_path: Path, monkeypatch) -> None:
    fake_agent = FakeAgent()
    client = await _client(tmp_path, monkeypatch, agent=fake_agent)
    try:
        response = await client.post(
            "/v1/chat/completions",
            json={
                "model": "test-model",
                "stream": True,
                "session_key": "api:stream-room",
                "messages": [{"role": "user", "content": "hello stream"}],
            },
        )

        assert response.status == 200
        assert response.headers["Content-Type"].startswith("text/event-stream")
        body = await response.text()
        assert '"object":"chat.completion.chunk"' in body
        assert '"role":"assistant"' in body
        assert '"content":"api-ok"' in body
        assert "data: [DONE]" in body
        assert fake_agent.calls[0]["content"] == "hello stream"
    finally:
        await client.close()


async def test_api_lists_and_denies_approvals(tmp_path: Path, monkeypatch) -> None:
    client = await _client(tmp_path, monkeypatch)
    try:
        approvals: ApprovalStateStore = client.app[APPROVALS_KEY]
        record = approvals.create_pending(
            session_key="api:room-1",
            tool_name="exec",
            tool_args={"command": "uptime"},
        )

        listed = await client.get("/approvals?session_key=api:room-1")
        assert listed.status == 200
        listed_payload = await listed.json()
        assert listed_payload["data"][0]["id"] == record.id

        denied = await client.post(f"/approvals/{record.id}/deny")
        assert denied.status == 200
        denied_payload = await denied.json()
        assert denied_payload["data"]["status"] == "denied"
    finally:
        await client.close()


async def test_api_approves_approval_as_session_allowlist(tmp_path: Path, monkeypatch) -> None:
    client = await _client(tmp_path, monkeypatch)
    try:
        approvals: ApprovalStateStore = client.app[APPROVALS_KEY]
        record = approvals.create_pending(
            session_key="api:room-1",
            tool_name="exec",
            tool_args={"command": "uptime"},
        )

        approved = await client.post(f"/approvals/{record.id}/approve", json={"scope": "session"})

        assert approved.status == 200
        payload = await approved.json()
        assert payload["data"]["status"] == "allowlisted"
        assert payload["data"]["scope"] == "session"
        assert approvals.get(record.id).status == "approved"
        assert approvals.is_tool_allowed(session_key="api:room-1", tool_name="exec")
    finally:
        await client.close()


async def test_api_learning_list_detail_and_status_update(tmp_path: Path, monkeypatch) -> None:
    client = await _client(tmp_path, monkeypatch)
    try:
        queue: LearningQueue = client.app[LEARNING_KEY]
        candidate = LearningCandidate(
            id="cand-1",
            kind="memory",
            title="Remember preference",
            rationale="Owner stated a durable preference.",
            content={"text": "Owner prefers concise updates."},
        )
        assert queue.add(candidate)

        listed = await client.get("/learning")
        assert listed.status == 200
        listed_payload = await listed.json()
        assert listed_payload["data"][0]["id"] == "cand-1"

        detail = await client.get("/learning/cand-1")
        assert detail.status == 200
        detail_payload = await detail.json()
        assert detail_payload["data"]["content"]["text"] == "Owner prefers concise updates."

        approved = await client.post("/learning/cand-1/approve")
        assert approved.status == 200
        approved_payload = await approved.json()
        assert approved_payload["data"]["status"] == "approved"
    finally:
        await client.close()


async def test_api_learning_edit_candidate(tmp_path: Path, monkeypatch) -> None:
    client = await _client(tmp_path, monkeypatch)
    try:
        queue: LearningQueue = client.app[LEARNING_KEY]
        assert queue.add(
            LearningCandidate(
                id="cand-edit",
                kind="tool_quirk",
                title="Tool quirk",
                rationale="Repeated failure",
                content={"tool": "exec", "note": "old"},
            )
        )

        edited = await client.post(
            "/learning/cand-edit/edit",
            json={"content": {"tool": "exec", "note": "new"}, "diff_preview": "old -> new"},
        )

        assert edited.status == 200
        payload = await edited.json()
        assert payload["data"]["content"]["note"] == "new"
        assert payload["data"]["diff_preview"] == "old -> new"
    finally:
        await client.close()


async def test_api_learning_apply_skill_candidate(tmp_path: Path, monkeypatch) -> None:
    client = await _client(tmp_path, monkeypatch)
    try:
        queue: LearningQueue = client.app[LEARNING_KEY]
        assert queue.add(
            LearningCandidate(
                id="cand-apply",
                kind="skill",
                title="Apply skill",
                rationale="Owner approved reusable workflow.",
                content={"name": "release", "content": _skill_md("release", "api body")},
            )
        )

        applied = await client.post("/learning/cand-apply/apply")

        assert applied.status == 200
        payload = await applied.json()
        assert payload["data"]["status"] == "applied"
        assert payload["result"]["code"] == "applied"
        skill_md = tmp_path / "skills" / "release" / "SKILL.md"
        assert "api body" in skill_md.read_text(encoding="utf-8")
    finally:
        await client.close()


async def test_api_learning_apply_rejects_non_skill_candidate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = await _client(tmp_path, monkeypatch)
    try:
        queue: LearningQueue = client.app[LEARNING_KEY]
        assert queue.add(
            LearningCandidate(
                id="cand-memory",
                kind="memory",
                title="Remember preference",
                rationale="Owner stated a durable preference.",
                content={"text": "Owner prefers direct updates."},
            )
        )

        rejected = await client.post("/learning/cand-memory/apply")

        assert rejected.status == 400
        payload = await rejected.json()
        assert payload["error"]["code"] == "unsupported_kind"
    finally:
        await client.close()


async def test_api_profiles_list_and_detail(tmp_path: Path, monkeypatch) -> None:
    client = await _client(tmp_path, monkeypatch)
    try:
        listed = await client.get("/profiles")
        assert listed.status == 200
        payload = await listed.json()
        ids = {item["id"] for item in payload["data"]}
        assert {"owner", "guest"} <= ids

        detail = await client.get("/profiles/owner")
        assert detail.status == 200
        detail_payload = await detail.json()
        assert detail_payload["data"]["id"] == "owner"
        assert detail_payload["data"]["is_guest"] is False
    finally:
        await client.close()
