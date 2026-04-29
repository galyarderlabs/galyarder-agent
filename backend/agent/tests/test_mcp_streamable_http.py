"""MCP streamable HTTP transport tests."""

from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from mcp import types

from g_agent.agent.tools.registry import ToolRegistry
from g_agent.mcp.manager import MCPManager, MCPToolWrapper


class FakeClientSession:
    """ClientSession double used to inspect transport wiring."""

    def __init__(self, read: object, write: object) -> None:
        self.read = read
        self.write = write

    async def __aenter__(self) -> "FakeClientSession":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def initialize(self) -> None:
        return None

    async def list_tools(self) -> SimpleNamespace:
        return SimpleNamespace(
            tools=[
                SimpleNamespace(
                    name="ping",
                    description="Ping tool",
                    inputSchema={"type": "object", "properties": {}},
                )
            ]
        )

    async def list_resources(self) -> SimpleNamespace:
        return SimpleNamespace(resources=[])

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> SimpleNamespace:
        return SimpleNamespace(content=[])


async def test_mcp_manager_connects_streamable_http_transport(
    tmp_path: Path,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    @asynccontextmanager
    async def fake_streamablehttp_client(
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float = 30,
        sse_read_timeout: float = 300,
        terminate_on_close: bool = True,
        **kwargs: object,
    ):
        captured.update(
            {
                "url": url,
                "headers": headers,
                "timeout": timeout,
                "sse_read_timeout": sse_read_timeout,
                "terminate_on_close": terminate_on_close,
            }
        )
        yield object(), object(), lambda: "session-1"

    monkeypatch.setattr("mcp.ClientSession", FakeClientSession)
    monkeypatch.setattr(
        "mcp.client.streamable_http.streamablehttp_client",
        fake_streamablehttp_client,
    )
    registry = ToolRegistry()
    manager = MCPManager(tmp_path, registry)

    await manager.connect_server(
        "docs",
        {
            "type": "streamable_http",
            "url": "http://127.0.0.1:9006/mcp",
            "headers": {"Authorization": "Bearer test"},
            "timeout": 7,
            "sse_read_timeout": 13,
            "terminate_on_close": False,
        },
    )

    assert captured == {
        "url": "http://127.0.0.1:9006/mcp",
        "headers": {"Authorization": "Bearer test"},
        "timeout": 7,
        "sse_read_timeout": 13,
        "terminate_on_close": False,
    }
    assert "mcp_docs_ping" in registry.tool_names


async def test_mcp_manager_accepts_http_transport_alias(
    tmp_path: Path,
    monkeypatch,
) -> None:
    @asynccontextmanager
    async def fake_streamablehttp_client(url: str, **kwargs: object):
        yield object(), object(), lambda: None

    monkeypatch.setattr("mcp.ClientSession", FakeClientSession)
    monkeypatch.setattr(
        "mcp.client.streamable_http.streamablehttp_client",
        fake_streamablehttp_client,
    )
    registry = ToolRegistry()
    manager = MCPManager(tmp_path, registry)

    await manager.connect_server("local", {"type": "http", "url": "http://localhost:8000/mcp"})

    assert "mcp_local_ping" in registry.tool_names


async def test_mcp_tool_wrapper_retries_transient_errors() -> None:
    class FlakySession:
        def __init__(self) -> None:
            self.calls = 0

        async def call_tool(self, name: str, arguments: dict[str, Any]) -> SimpleNamespace:
            self.calls += 1
            if self.calls == 1:
                raise ConnectionResetError("temporary disconnect")
            return SimpleNamespace(
                content=[types.TextContent(type="text", text=f"{name}:{arguments['value']}")]
            )

    session = FlakySession()
    tool = MCPToolWrapper(
        session,
        "server",
        SimpleNamespace(
            name="echo",
            description="Echo",
            inputSchema={
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
        ),
        tool_timeout=3,
    )

    result = await tool.execute(value="ok")

    assert result == "echo:ok"
    assert session.calls == 2
