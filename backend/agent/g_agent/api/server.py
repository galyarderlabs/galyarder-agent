"""Local product API server for G-Agent."""

import asyncio
import re
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from aiohttp import web

from g_agent import __version__
from g_agent.agent.api import Agent
from g_agent.api.openai_compat import (
    chat_completion_response,
    chat_completion_stream_events,
    chat_id_from_session_key,
    model_list,
)
from g_agent.bus.events import LifecycleEvent
from g_agent.character.profile import CharacterProfile
from g_agent.character.store import CharacterStore
from g_agent.config.loader import load_config
from g_agent.config.schema import Config
from g_agent.learning.apply import LearningApplyResult, apply_learning_candidate
from g_agent.learning.candidate import LearningCandidate
from g_agent.learning.queue import LearningQueue, VALID_STATUSES
from g_agent.routines.store import RoutineStore
from g_agent.security.approval_state import ApprovalRecord, ApprovalStateStore
from g_agent.session.manager import SessionManager


CONFIG_KEY = web.AppKey("config", Config)
AGENT_KEY = web.AppKey("agent", object)
SESSIONS_KEY = web.AppKey("sessions", SessionManager)
APPROVALS_KEY = web.AppKey("approvals", ApprovalStateStore)
LEARNING_KEY = web.AppKey("learning", LearningQueue)
CHARACTERS_KEY = web.AppKey("characters", CharacterStore)
ROUTINES_KEY = web.AppKey("routines", RoutineStore)


class ApiError(Exception):
    """HTTP API error rendered as a stable JSON payload."""

    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message


async def _webui_bootstrap(request: web.Request) -> web.Response:
    config = request.app[CONFIG_KEY]
    token = config.gateway.api_token or ""
    return web.json_response({
        "token": token,
        "ws_path": "/ws",
        "model_name": config.model.name if hasattr(config, "model") else "g-agent"
    })

def create_app(
    *,
    config: Config | None = None,
    agent: Any | None = None,
    session_manager: SessionManager | None = None,
) -> web.Application:
    """Create the aiohttp product API app."""
    resolved_config = config or load_config()
    resolved_sessions = session_manager or SessionManager(resolved_config.workspace_path)
    resolved_approvals = ApprovalStateStore(resolved_config.workspace_path)
    resolved_learning = LearningQueue(resolved_config.workspace_path)
    resolved_characters = CharacterStore(resolved_config.workspace_path)
    resolved_routines = RoutineStore(resolved_config.workspace_path)
    app = web.Application(
        middlewares=[
            _error_middleware,
            _request_size_middleware(resolved_config.gateway.max_request_bytes),
            _auth_middleware(resolved_config.gateway.api_token),
        ]
    )
    app[CONFIG_KEY] = resolved_config
    app[AGENT_KEY] = agent
    app[SESSIONS_KEY] = resolved_sessions
    app[APPROVALS_KEY] = resolved_approvals
    app[LEARNING_KEY] = resolved_learning
    app[CHARACTERS_KEY] = resolved_characters
    app[ROUTINES_KEY] = resolved_routines

    app.router.add_get("/api/health", _health)
    app.router.add_get("/health", _health)
    app.router.add_get("/api/status", _status)
    app.router.add_get("/status", _status)
    app.router.add_get("/webui/bootstrap", _webui_bootstrap)
    app.router.add_get("/api/sessions", _sessions)
    app.router.add_get("/api/sessions/{session_id}", _session_detail)
    app.router.add_post("/api/sessions/{session_key}/delete", _session_delete)
    app.router.add_get("/api/sessions/{session_key}/messages", _session_messages)
    app.router.add_post("/api/media", _media_upload)
    app.router.add_get("/api/approvals", _approvals)
    app.router.add_post("/api/approvals/{approval_id}/approve", _approval_approve)
    app.router.add_post("/api/approvals/{approval_id}/deny", _approval_deny)
    app.router.add_get("/api/learning", _learning)
    app.router.add_get("/api/learning/{candidate_id}", _learning_detail)
    app.router.add_post("/api/learning/{candidate_id}/approve", _learning_approve)
    app.router.add_post("/api/learning/{candidate_id}/reject", _learning_reject)
    app.router.add_post("/api/learning/{candidate_id}/edit", _learning_edit)
    app.router.add_post("/api/learning/{candidate_id}/apply", _learning_apply)
    app.router.add_get("/api/profiles", _profiles)
    app.router.add_get("/api/profiles/{profile_id}", _profile_detail)
    app.router.add_post("/api/profiles/{profile_id}/activate", _profile_activate)
    app.router.add_get("/api/routines", _routines)
    app.router.add_post("/api/routines/{routine_id}/enable", _routine_enable)
    app.router.add_post("/api/routines/{routine_id}/disable", _routine_disable)
    app.router.add_get("/api/v1/models", _models)
    app.router.add_get("/v1/models", _models)
    app.router.add_post("/api/v1/chat/completions", _chat_completions)
    app.router.add_post("/v1/chat/completions", _chat_completions)

    webui_dir = Path(__file__).parent.parent / "webui" / "dist"
    if webui_dir.exists():
        app.router.add_static("/assets", webui_dir / "assets")

        async def _serve_index(request: web.Request) -> web.Response:
            index_path = webui_dir / "index.html"
            if index_path.exists():
                return web.FileResponse(index_path)
            raise web.HTTPNotFound()

        app.router.add_get("/", _serve_index)
        app.router.add_get("/index.html", _serve_index)

    return app


async def run_api_server(config: Config | None = None) -> None:
    """Run the API server until interrupted."""
    resolved_config = config or load_config()
    app = create_app(config=resolved_config)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, resolved_config.gateway.host, resolved_config.gateway.port)
    await site.start()
    try:
        while True:
            await _sleep_forever()
    finally:
        await runner.cleanup()


async def _sleep_forever() -> None:
    import asyncio

    await asyncio.sleep(3600)


@web.middleware
async def _error_middleware(request: web.Request, handler: Any) -> web.StreamResponse:
    try:
        return await handler(request)
    except ApiError as exc:
        return _json_error(exc.status, exc.code, exc.message)
    except web.HTTPException:
        raise
    except Exception as exc:
        return _json_error(500, "internal_error", str(exc))


def _auth_middleware(api_token: str):
    @web.middleware
    async def middleware(request: web.Request, handler: Any) -> web.StreamResponse:
        # Exclude health check, status, models, and bootstrap from auth
        if request.path in ("/api/health", "/health", "/api/status", "/status", "/api/v1/models", "/webui/bootstrap") or not api_token:
            return await handler(request)
        header = request.headers.get("Authorization", "")
        token = request.headers.get("X-G-Agent-Token", "")
        if header.startswith("Bearer "):
            token = header.removeprefix("Bearer ").strip()
        if token != api_token:
            raise ApiError(401, "unauthorized", "valid API token required")
        return await handler(request)

    return middleware


def _request_size_middleware(max_request_bytes: int):
    @web.middleware
    async def middleware(request: web.Request, handler: Any) -> web.StreamResponse:
        content_length = request.content_length
        if content_length is not None and content_length > max_request_bytes:
            raise ApiError(413, "request_too_large", "request body exceeds configured limit")
        return await handler(request)

    return middleware


async def _health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def _status(request: web.Request) -> web.Response:
    config = request.app[CONFIG_KEY]
    sessions = request.app[SESSIONS_KEY]
    return web.json_response(
        {
            "status": "ok",
            "version": __version__,
            "workspace": str(config.workspace_path),
            "model": config.agents.defaults.model,
            "sessions": len(sessions.sqlite_store.list_sessions(limit=1000)),
        }
    )


async def _sessions(request: web.Request) -> web.Response:
    sessions = request.app[SESSIONS_KEY]
    limit = _int_query(request, "limit", default=50, minimum=1, maximum=200)
    return web.json_response({"sessions": sessions.sqlite_store.list_sessions(limit=limit)})


async def _session_delete(request: web.Request) -> web.Response:
    sessions = request.app[SESSIONS_KEY]
    session_key = request.match_info["session_key"]
    # Key is often URL-encoded in the path
    decoded_key = unquote(session_key)
    session = sessions.get_or_create(decoded_key)
    if not session:
        raise ApiError(404, "not_found", "session not found")

    # Actually delete from store
    sessions.sqlite_store.delete_session(session["id"])
    return web.json_response({"deleted": True})

async def _session_messages(request: web.Request) -> web.Response:
    sessions = request.app[SESSIONS_KEY]
    session_key = request.match_info["session_key"]
    decoded_key = unquote(session_key)
    session = sessions.get_or_create(decoded_key)
    if not session:
        raise ApiError(404, "not_found", "session not found")

    limit = _int_query(request, "limit", default=100, minimum=1, maximum=500)
    messages = sessions.sqlite_store.get_history(session["id"], limit=limit)

    return web.json_response({
        "key": decoded_key,
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at"),
        "messages": messages
    })


async def _session_detail(request: web.Request) -> web.Response:
    sessions = request.app[SESSIONS_KEY]
    session_id = request.match_info["session_id"]
    session = sessions.sqlite_store.get_session(session_id)
    if not session:
        raise ApiError(404, "not_found", "session not found")
    limit = _int_query(request, "limit", default=100, minimum=1, maximum=500)
    return web.json_response(
        {
            "session": session,
            "messages": sessions.sqlite_store.get_history(session["id"], limit=limit),
        }
    )


async def _media_upload(request: web.Request) -> web.Response:
    if not request.content_type.startswith("multipart/"):
        raise ApiError(400, "invalid_request", "multipart upload is required")

    config = request.app[CONFIG_KEY]
    sessions = request.app[SESSIONS_KEY]
    fields: dict[str, str] = {}
    uploaded: dict[str, Any] | None = None
    upload_dir = config.workspace_path / "media" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    reader = await request.multipart()
    async for part in reader:
        if part.filename:
            filename = _safe_filename(part.filename)
            target = upload_dir / f"{uuid.uuid4().hex}-{filename}"
            size = 0
            with target.open("wb") as handle:
                while True:
                    chunk = await part.read_chunk()
                    if not chunk:
                        break
                    size += len(chunk)
                    handle.write(chunk)
            uploaded = {
                "path": str(target),
                "filename": filename,
                "size": size,
                "mime_type": part.headers.get("Content-Type"),
                "field": part.name,
            }
        elif part.name:
            fields[part.name] = (await part.text()).strip()

    if uploaded is None:
        raise ApiError(400, "invalid_request", "file part is required")

    session_key = fields.get("session_key") or request.query.get("session_key") or "api:uploads"
    session = sessions.sqlite_store.get_or_create_session(session_key)
    kind = fields.get("kind") or _media_kind(uploaded.get("mime_type")) or "file"
    caption = fields.get("caption") or f"[{kind}: {uploaded['filename']}]"
    metadata = {
        "attachments": [
            {
                "type": kind,
                "path": uploaded["path"],
                "mime": uploaded.get("mime_type"),
                "filename": uploaded["filename"],
                "size": uploaded["size"],
                "sourceChannel": "api",
            }
        ]
    }
    message_id = sessions.sqlite_store.append_message(
        session["id"],
        "user",
        caption,
        content_type="media",
        metadata=metadata,
    )
    media_id = sessions.sqlite_store.append_media_ref(
        session["id"],
        message_id=message_id,
        kind=kind,
        path=uploaded["path"],
        mime_type=uploaded.get("mime_type"),
        metadata={
            "filename": uploaded["filename"],
            "size": uploaded["size"],
            "source": "api_upload",
            "field": uploaded.get("field"),
        },
    )

    try:
        agent = await _get_agent(request)
        chat_id = session_key.split(":", 1)[1] if ":" in session_key else session_key
        asyncio.create_task(
            agent.bus.publish_event(
                LifecycleEvent(
                    type="media_upload",
                    chat_id=chat_id,
                    data={
                        "id": media_id,
                        "session_id": session["id"],
                        "session_key": session_key,
                        "message_id": message_id,
                        "kind": kind,
                        "path": uploaded["path"],
                        "mime_type": uploaded.get("mime_type"),
                        "filename": uploaded["filename"],
                        "size": uploaded["size"],
                    }
                )
            )
        )
    except Exception:
        pass

    return web.json_response(
        {
            "data": {
                "id": media_id,
                "session_id": session["id"],
                "session_key": session_key,
                "message_id": message_id,
                "kind": kind,
                "path": uploaded["path"],
                "mime_type": uploaded.get("mime_type"),
                "filename": uploaded["filename"],
                "size": uploaded["size"],
            }
        },
        status=201,
    )


async def _approvals(request: web.Request) -> web.Response:
    approvals = request.app[APPROVALS_KEY]
    session_key = request.query.get("session_key") or None
    raw_status = request.query.get("status") or "pending"
    status = None if raw_status == "all" else raw_status
    records = approvals.list(session_key=session_key, status=status)
    return web.json_response({"approvals": [_approval_json(record) for record in records]})


async def _approval_approve(request: web.Request) -> web.Response:
    approvals = request.app[APPROVALS_KEY]
    approval_id = request.match_info["approval_id"]
    payload = await _optional_json(request)
    scope = str(payload.get("scope") or "once")
    record = approvals.get(approval_id)
    if record is None:
        raise ApiError(404, "not_found", "approval not found")
    if scope in {"session", "always"}:
        approvals.update_status(approval_id, "approved", decision=f"api_approve_{scope}")
        updated = approvals.allow_tool(
            session_key=record.session_key,
            tool_name=record.tool_name,
            scope=scope,
        )
    else:
        updated = approvals.update_status(approval_id, "approved", decision="approve_once")
    return web.json_response({"data": _approval_json(updated)})


async def _approval_deny(request: web.Request) -> web.Response:
    approvals = request.app[APPROVALS_KEY]
    approval_id = request.match_info["approval_id"]
    updated = approvals.update_status(approval_id, "denied", decision="api_deny")
    if updated is None:
        raise ApiError(404, "not_found", "approval not found")
    return web.json_response({"data": _approval_json(updated)})


async def _learning(request: web.Request) -> web.Response:
    queue = request.app[LEARNING_KEY]
    status = request.query.get("status") or "pending"
    if status == "all":
        status = None
    if status is not None and status not in VALID_STATUSES:
        raise ApiError(400, "invalid_status", "invalid learning candidate status")
    return web.json_response({"candidates": [_candidate_json(item) for item in queue.list(status=status)]})


async def _learning_detail(request: web.Request) -> web.Response:
    queue = request.app[LEARNING_KEY]
    candidate = queue.get(request.match_info["candidate_id"])
    if candidate is None:
        raise ApiError(404, "not_found", "learning candidate not found")
    return web.json_response({"data": _candidate_json(candidate)})


async def _learning_approve(request: web.Request) -> web.Response:
    return await _learning_set_status(request, "approved")


async def _learning_reject(request: web.Request) -> web.Response:
    return await _learning_set_status(request, "rejected")


async def _learning_set_status(request: web.Request, status: str) -> web.Response:
    queue = request.app[LEARNING_KEY]
    candidate_id = request.match_info["candidate_id"]
    if not queue.update_status(candidate_id, status):
        raise ApiError(404, "not_found", "learning candidate not found")
    candidate = queue.get(candidate_id)
    return web.json_response({"data": _candidate_json(candidate)})


async def _learning_edit(request: web.Request) -> web.Response:
    queue = request.app[LEARNING_KEY]
    candidate_id = request.match_info["candidate_id"]
    payload = await request.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("content"), dict):
        raise ApiError(400, "invalid_request", "content object is required")
    diff_preview = payload.get("diff_preview")
    if diff_preview is not None and not isinstance(diff_preview, str):
        raise ApiError(400, "invalid_request", "diff_preview must be a string")
    if not queue.update_content(candidate_id, payload["content"], diff_preview=diff_preview):
        raise ApiError(404, "not_found", "learning candidate not found or cannot be edited")
    candidate = queue.get(candidate_id)
    return web.json_response({"data": _candidate_json(candidate)})


async def _learning_apply(request: web.Request) -> web.Response:
    config = request.app[CONFIG_KEY]
    result = apply_learning_candidate(config.workspace_path, request.match_info["candidate_id"])
    if not result.ok:
        status = 404 if result.code == "not_found" else 400
        raise ApiError(status, result.code, _apply_error_message(result))
    return web.json_response(
        {
            "data": _candidate_json(result.candidate),
            "result": {
                "code": result.code,
                "message": result.message,
                "errors": result.errors,
            },
        }
    )


async def _profiles(request: web.Request) -> web.Response:
    characters = request.app[CHARACTERS_KEY]
    characters.setup_default_profiles()
    return web.json_response({"profiles": [_profile_json(profile) for profile in characters.list()]})


async def _profile_detail(request: web.Request) -> web.Response:
    characters = request.app[CHARACTERS_KEY]
    characters.setup_default_profiles()
    profile = characters.get(request.match_info["profile_id"])
    if profile is None:
        raise ApiError(404, "not_found", "profile not found")
    return web.json_response({"data": _profile_json(profile)})


async def _profile_activate(request: web.Request) -> web.Response:
    characters = request.app[CHARACTERS_KEY]
    sessions = request.app[SESSIONS_KEY]
    profile_id = request.match_info["profile_id"]
    session_key = request.query.get("session_key")
    if not session_key:
        raise ApiError(400, "missing_session", "session_key query param required")

    profile = characters.get(profile_id)
    if profile is None:
        raise ApiError(404, "not_found", "profile not found")

    session = sessions.get_or_create(session_key)
    session.metadata["current_profile_id"] = profile.id
    sessions.save(session)

    return web.json_response({"activated": True, "profile_id": profile.id})


async def _routines(request: web.Request) -> web.Response:
    store = request.app[ROUTINES_KEY]
    routines = store.list()
    return web.json_response({"routines": [r.model_dump() for r in routines]})


async def _routine_enable(request: web.Request) -> web.Response:
    store = request.app[ROUTINES_KEY]
    routine_id = request.match_info["routine_id"]
    routine = store.get(routine_id)
    if not routine:
        raise ApiError(404, "not_found", "routine not found")
    routine.enabled = True
    store.save(routine)
    return web.json_response({"status": "ok", "enabled": True})


async def _routine_disable(request: web.Request) -> web.Response:
    store = request.app[ROUTINES_KEY]
    routine_id = request.match_info["routine_id"]
    routine = store.get(routine_id)
    if not routine:
        raise ApiError(404, "not_found", "routine not found")
    routine.enabled = False
    store.save(routine)
    return web.json_response({"status": "ok", "enabled": False})


async def _models(request: web.Request) -> web.Response:
    config = request.app[CONFIG_KEY]
    model_ids = [config.agents.defaults.model, *config.agents.defaults.routing.fallback_models]
    return web.json_response(model_list(model_ids))


async def _chat_completions(request: web.Request) -> web.Response:
    payload = await request.json()
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ApiError(400, "invalid_request", "messages must be a non-empty array")

    # Extract content and images
    content = ""
    media_paths = []
    last_msg = messages[-1]
    if isinstance(last_msg, dict) and last_msg.get("role") == "user":
        raw_content = last_msg.get("content")
        if isinstance(raw_content, str):
            content = raw_content
        elif isinstance(raw_content, list):
            for item in raw_content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") in {"text", "input_text"}:
                    content += str(item.get("text") or "") + "\n"
                elif item.get("type") == "image_url":
                    url_obj = item.get("image_url")
                    if isinstance(url_obj, dict):
                        url = url_obj.get("url")
                        if url:
                            media_paths.append(url)

    if not content and not media_paths:
        raise ApiError(400, "invalid_request", "last user message content is required")

    config = request.app[CONFIG_KEY]
    agent = await _get_agent(request)
    model = str(payload.get("model") or config.agents.defaults.model)
    session_key = str(payload.get("session_key") or "api:default")

    response_text = await agent.ask(
        content.strip(),
        session_key=session_key,
        channel="api",
        chat_id=chat_id_from_session_key(session_key),
        media=media_paths,
    )

    if payload.get("stream"):
        return await _chat_completion_stream(request, model=model, response_text=response_text)
    return web.json_response(chat_completion_response(model=model, response_text=response_text))


async def _chat_completion_stream(
    request: web.Request,
    *,
    model: str,
    response_text: str,
) -> web.StreamResponse:
    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
    await response.prepare(request)
    for event in chat_completion_stream_events(model=model, response_text=response_text):
        await response.write(event)
    await response.write_eof()
    return response


async def _get_agent(request: web.Request) -> Any:
    agent = request.app[AGENT_KEY]
    if agent is None:
        agent = Agent(config=request.app[CONFIG_KEY])
        request.app[AGENT_KEY] = agent
    return agent


def _int_query(
    request: web.Request,
    name: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    raw = request.query.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


async def _optional_json(request: web.Request) -> dict[str, Any]:
    if not request.can_read_body:
        return {}
    try:
        payload = await request.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _approval_json(record: ApprovalRecord | None) -> dict[str, Any]:
    if record is None:
        return {}
    return record.model_dump()


def _candidate_json(candidate: LearningCandidate | None) -> dict[str, Any]:
    if candidate is None:
        return {}
    return candidate.model_dump(mode="json")


def _profile_json(profile: CharacterProfile) -> dict[str, Any]:
    return profile.model_dump(mode="json")


def _apply_error_message(result: LearningApplyResult) -> str:
    if result.errors:
        return result.message + ": " + "; ".join(result.errors)
    return result.message


def _safe_filename(filename: str) -> str:
    name = Path(unquote(filename).replace("\\", "/")).name
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
    return sanitized or "upload.bin"


def _media_kind(mime_type: str | None) -> str | None:
    if not mime_type:
        return None
    prefix = mime_type.split("/", 1)[0].lower()
    if prefix in {"image", "audio", "video"}:
        return prefix
    return "document"


def _json_error(status: int, code: str, message: str) -> web.Response:
    return web.json_response(
        {"error": {"code": code, "message": message}},
        status=status,
    )
