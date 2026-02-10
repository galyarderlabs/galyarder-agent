import asyncio
import json
from pathlib import Path
from typing import Any

from g_agent.observability.http_server import MetricsHttpServer
from g_agent.observability.metrics import MetricsStore


class _FakeReader:
    def __init__(self, payload: bytes):
        self.payload = payload

    async def read(self, _size: int = -1) -> bytes:
        return self.payload


class _FakeWriter:
    def __init__(self):
        self._chunks: list[bytes] = []
        self.closed = False
        self.wait_closed_called = False

    def write(self, data: bytes) -> None:
        self._chunks.append(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        self.wait_closed_called = True

    @property
    def payload(self) -> bytes:
        return b"".join(self._chunks)


def _parse_http(payload: bytes) -> tuple[int, str, str]:
    head, _, body = payload.partition(b"\r\n\r\n")
    head_text = head.decode("utf-8", errors="ignore")
    status_line = head_text.splitlines()[0] if head_text.splitlines() else ""
    try:
        status = int(status_line.split()[1])
    except (IndexError, ValueError):
        status = 0
    return status, head_text, body.decode("utf-8", errors="ignore")


def test_metrics_http_server_handle_client_routes(tmp_path: Path):
    store = MetricsStore(tmp_path / "events.jsonl")
    store.record_llm_call(model="gemini-3-pro", success=True, latency_ms=300)
    store.record_tool_call(
        tool='web_search"prod"', success=False, latency_ms=700, attempts=2, error="429"
    )
    server = MetricsHttpServer(
        store=store,
        host="127.0.0.1",
        port=0,
        path="/metrics",
        default_hours=24,
        default_format="prometheus",
    )

    async def send(raw_request: str) -> tuple[int, str, str]:
        reader = _FakeReader(raw_request.encode("utf-8"))
        writer = _FakeWriter()
        await server._handle_client(reader, writer)
        assert writer.closed is True
        assert writer.wait_closed_called is True
        return _parse_http(writer.payload)

    status, headers, body = asyncio.run(send("GET /metrics HTTP/1.1\r\nHost: localhost\r\n\r\n"))
    assert status == 200
    assert "text/plain" in headers.lower()
    assert "g_agent_llm_calls_total 1" in body
    assert 'g_agent_top_tool_calls{tool="web_search\\"prod\\""} 1' in body

    status, headers, body = asyncio.run(
        send("GET /metrics?format=dashboard_json&hours=24 HTTP/1.1\r\nHost: localhost\r\n\r\n")
    )
    assert status == 200
    assert "application/json" in headers.lower()
    payload = json.loads(body)
    assert payload["tool_calls"] == 1
    assert payload["tool_errors"] == 1

    status, _, body = asyncio.run(send("GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n"))
    assert status == 200
    assert body.strip() == "ok"

    status, _, _ = asyncio.run(send("GET /missing HTTP/1.1\r\nHost: localhost\r\n\r\n"))
    assert status == 404

    status, _, _ = asyncio.run(send("POST /metrics HTTP/1.1\r\nHost: localhost\r\n\r\n"))
    assert status == 405


def test_metrics_http_server_start_stop_with_mocked_server(tmp_path: Path, monkeypatch):
    store = MetricsStore(tmp_path / "events.jsonl")
    server = MetricsHttpServer(
        store=store,
        host="127.0.0.1",
        port=18791,
        path="/metrics",
    )

    class _FakeSocket:
        def getsockname(self):
            return ("127.0.0.1", 19991)

    class _FakeAsyncServer:
        def __init__(self):
            self.sockets = [_FakeSocket()]
            self.closed = False
            self.wait_closed_called = False

        def close(self) -> None:
            self.closed = True

        async def wait_closed(self) -> None:
            self.wait_closed_called = True

    capture: dict[str, Any] = {}
    fake_server = _FakeAsyncServer()

    async def fake_start_server(handler, host, port):
        capture["handler"] = handler
        capture["host"] = host
        capture["port"] = port
        return fake_server

    monkeypatch.setattr("g_agent.observability.http_server.asyncio.start_server", fake_start_server)

    async def run_case() -> None:
        await server.start()
        assert server.is_running is True
        assert server.bound_port == 19991
        assert capture["host"] == "127.0.0.1"
        assert capture["port"] == 18791

        await server.stop()
        assert fake_server.closed is True
        assert fake_server.wait_closed_called is True
        assert server.is_running is False

    asyncio.run(run_case())
