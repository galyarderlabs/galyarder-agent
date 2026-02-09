import asyncio
from typing import Any

from g_agent.agent.tools.google_workspace import GoogleWorkspaceClient


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, factory: "_FakeAsyncClientFactory"):
        self._factory = factory

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def post(self, url: str, data: dict[str, Any] | None = None) -> _FakeResponse:
        self._factory.post_calls.append({"url": url, "data": data or {}})
        return self._factory.post_responses.pop(0)

    async def request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> _FakeResponse:
        self._factory.request_calls.append(
            {
                "method": method,
                "url": url,
                "params": params or {},
                "json": json or {},
                "headers": headers or {},
            }
        )
        return self._factory.request_responses.pop(0)


class _FakeAsyncClientFactory:
    def __init__(
        self,
        *,
        post_responses: list[_FakeResponse] | None = None,
        request_responses: list[_FakeResponse] | None = None,
    ):
        self.post_responses = post_responses or []
        self.request_responses = request_responses or []
        self.post_calls: list[dict[str, Any]] = []
        self.request_calls: list[dict[str, Any]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> _FakeAsyncClient:
        return _FakeAsyncClient(self)


def test_google_request_reports_expired_refresh_token(monkeypatch):
    factory = _FakeAsyncClientFactory(
        post_responses=[
            _FakeResponse(
                400,
                {
                    "error": "invalid_grant",
                    "error_description": "Token has been expired or revoked.",
                },
            )
        ],
        request_responses=[],
    )
    monkeypatch.setattr("g_agent.agent.tools.google_workspace.httpx.AsyncClient", factory)

    client = GoogleWorkspaceClient(
        client_id="cid",
        client_secret="csecret",
        refresh_token="refresh",
    )
    ok, data = asyncio.run(
        client.request("GET", "https://gmail.googleapis.com/gmail/v1/users/me/profile")
    )

    assert ok is False
    assert "expired or revoked" in data.get("error", "").lower()
    assert "auth-url" in data.get("error", "")
    assert len(factory.post_calls) == 1
    assert len(factory.request_calls) == 0


def test_google_request_reports_scope_drift_with_guidance(monkeypatch):
    factory = _FakeAsyncClientFactory(
        post_responses=[
            _FakeResponse(200, {"access_token": "fresh-token", "expires_in": 3600}),
        ],
        request_responses=[
            _FakeResponse(
                403,
                {
                    "error": {
                        "code": 403,
                        "message": "Request had insufficient authentication scopes.",
                        "status": "PERMISSION_DENIED",
                        "details": [
                            {
                                "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                                "reason": "ACCESS_TOKEN_SCOPE_INSUFFICIENT",
                            }
                        ],
                    }
                },
            )
        ],
    )
    monkeypatch.setattr("g_agent.agent.tools.google_workspace.httpx.AsyncClient", factory)

    client = GoogleWorkspaceClient(
        client_id="cid",
        client_secret="csecret",
        refresh_token="refresh",
    )
    ok, data = asyncio.run(
        client.request("GET", "https://gmail.googleapis.com/gmail/v1/users/me/profile")
    )

    assert ok is False
    assert "scope mismatch" in data.get("error", "").lower()
    assert "auth-url" in data.get("error", "")
    assert len(factory.post_calls) == 1
    assert len(factory.request_calls) == 1

