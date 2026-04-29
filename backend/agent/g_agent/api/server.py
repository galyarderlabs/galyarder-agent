"""Local product API server for G-Agent."""

import time
import uuid
from typing import Any

from aiohttp import web

from g_agent import __version__
from g_agent.agent.api import Agent
from g_agent.config.loader import load_config
from g_agent.config.schema import Config
from g_agent.session.manager import SessionManager


CONFIG_KEY = web.AppKey("config", Config)
AGENT_KEY = web.AppKey("agent", object)
SESSIONS_KEY = web.AppKey("sessions", SessionManager)


class ApiError(Exception):
    """HTTP API error rendered as a stable JSON payload."""

    def __init__(self, status: int, code: str, message: str):
        self.status = status
        self.code = code
        self.message = message


def create_app(
    *,
    config: Config | None = None,
    agent: Any | None = None,
    session_manager: SessionManager | None = None,
) -> web.Application:
    """Create the aiohttp product API app."""
    resolved_config = config or load_config()
    resolved_sessions = session_manager or SessionManager(resolved_config.workspace_path)
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

    app.router.add_get("/health", _health)
    app.router.add_get("/status", _status)
    app.router.add_get("/sessions", _sessions)
    app.router.add_get("/sessions/{session_id}", _session_detail)
    app.router.add_get("/v1/models", _models)
    app.router.add_post("/v1/chat/completions", _chat_completions)
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
        if request.path == "/health" or not api_token:
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
    return web.json_response({"data": sessions.sqlite_store.list_sessions(limit=limit)})


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


async def _models(request: web.Request) -> web.Response:
    config = request.app[CONFIG_KEY]
    model_ids = [config.agents.defaults.model, *config.agents.defaults.routing.fallback_models]
    seen: set[str] = set()
    data = []
    for model_id in model_ids:
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        data.append({"id": model_id, "object": "model", "owned_by": "g-agent"})
    return web.json_response({"object": "list", "data": data})


async def _chat_completions(request: web.Request) -> web.Response:
    payload = await request.json()
    if payload.get("stream"):
        raise ApiError(400, "streaming_not_supported", "streaming chat completions are not shipped")
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ApiError(400, "invalid_request", "messages must be a non-empty array")

    content = _last_user_content(messages)
    if not content:
        raise ApiError(400, "invalid_request", "last user message content is required")

    config = request.app[CONFIG_KEY]
    agent = await _get_agent(request)
    model = str(payload.get("model") or config.agents.defaults.model)
    session_key = str(payload.get("session_key") or "api:default")
    response_text = await agent.ask(
        content,
        session_key=session_key,
        channel="api",
        chat_id=session_key.split(":", 1)[1] if ":" in session_key else session_key,
    )

    return web.json_response(
        {
            "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": response_text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
    )


async def _get_agent(request: web.Request) -> Any:
    agent = request.app[AGENT_KEY]
    if agent is None:
        agent = Agent(config=request.app[CONFIG_KEY])
        request.app[AGENT_KEY] = agent
    return agent


def _last_user_content(messages: list[Any]) -> str:
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        return _normalize_content(message.get("content"))
    return ""


def _normalize_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") in {"text", "input_text"}:
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()
    return ""


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


def _json_error(status: int, code: str, message: str) -> web.Response:
    return web.json_response(
        {"error": {"code": code, "message": message}},
        status=status,
    )
