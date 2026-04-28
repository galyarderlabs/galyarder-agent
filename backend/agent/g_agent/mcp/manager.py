"""MCP manager for G-Agent: connects to and manages external tool servers."""

import asyncio
import os
import shutil
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Dict

from loguru import logger

from g_agent.agent.tools.registry import ToolRegistry
from g_agent.agent.tools.base import Tool


# Transient connection errors that warrant a single retry.
_TRANSIENT_EXC_NAMES: frozenset[str] = frozenset(
    (
        "ClosedResourceError",
        "BrokenResourceError",
        "EndOfStream",
        "BrokenPipeError",
        "ConnectionResetError",
        "ConnectionRefusedError",
        "ConnectionAbortedError",
        "ConnectionError",
    )
)

_WINDOWS_SHELL_LAUNCHERS: frozenset[str] = frozenset(("npx", "npm", "pnpm", "yarn", "bunx"))


def _is_transient(exc: BaseException) -> bool:
    return type(exc).__name__ in _TRANSIENT_EXC_NAMES


def _windows_command_basename(command: str) -> str:
    return command.replace("\\", "/").rsplit("/", maxsplit=1)[-1].lower()


def _normalize_windows_stdio_command(
    command: str,
    args: list[str] | None,
    env: dict[str, str] | None,
) -> tuple[str, list[str], dict[str, str] | None]:
    normalized_args = list(args or [])
    if os.name != "nt":
        return command, normalized_args, env

    basename = _windows_command_basename(command)
    if basename in {"cmd", "cmd.exe", "powershell", "powershell.exe", "pwsh", "pwsh.exe"}:
        return command, normalized_args, env

    if basename.endswith((".exe", ".com")):
        return command, normalized_args, env

    resolved = shutil.which(command, path=(env or {}).get("PATH")) or command
    resolved_basename = _windows_command_basename(resolved)
    should_wrap = (
        basename in _WINDOWS_SHELL_LAUNCHERS
        or basename.endswith((".cmd", ".bat"))
        or resolved_basename.endswith((".cmd", ".bat"))
    )
    if not should_wrap:
        return command, normalized_args, env

    comspec = (env or {}).get("COMSPEC") or os.environ.get("COMSPEC") or "cmd.exe"
    return comspec, ["/d", "/c", command, *normalized_args], env


def _extract_nullable_branch(options: Any) -> tuple[dict[str, Any], bool] | None:
    if not isinstance(options, list):
        return None

    non_null: list[dict[str, Any]] = []
    saw_null = False
    for option in options:
        if not isinstance(option, dict):
            return None
        if option.get("type") == "null":
            saw_null = True
            continue
        non_null.append(option)

    if saw_null and len(non_null) == 1:
        return non_null[0], True
    return None


def _normalize_schema_for_openai(schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}}

    normalized = dict(schema)

    raw_type = normalized.get("type")
    if isinstance(raw_type, list):
        non_null = [item for item in raw_type if item != "null"]
        if "null" in raw_type and len(non_null) == 1:
            normalized["type"] = non_null[0]
            normalized["nullable"] = True

    for key in ("oneOf", "anyOf"):
        nullable_branch = _extract_nullable_branch(normalized.get(key))
        if nullable_branch is not None:
            branch, _ = nullable_branch
            merged = {k: v for k, v in normalized.items() if k != key}
            merged.update(branch)
            normalized = merged
            normalized["nullable"] = True
            break

    if "properties" in normalized and isinstance(normalized["properties"], dict):
        normalized["properties"] = {
            name: _normalize_schema_for_openai(prop) if isinstance(prop, dict) else prop
            for name, prop in normalized["properties"].items()
        }

    if "items" in normalized and isinstance(normalized["items"], dict):
        normalized["items"] = _normalize_schema_for_openai(normalized["items"])

    if normalized.get("type") != "object":
        return normalized

    normalized.setdefault("properties", {})
    normalized.setdefault("required", [])
    return normalized


class MCPToolWrapper(Tool):
    def __init__(self, session, server_name: str, tool_def, tool_timeout: int = 30):
        self._session = session
        self._original_name = tool_def.name
        self.name = f"mcp_{server_name}_{tool_def.name}"
        self.description = tool_def.description or self.name
        self.parameters = _normalize_schema_for_openai(
            tool_def.inputSchema or {"type": "object", "properties": {}}
        )
        self._tool_timeout = tool_timeout

    async def execute(self, **kwargs: Any) -> str:
        from mcp import types

        for attempt in range(2):
            try:
                result = await asyncio.wait_for(
                    self._session.call_tool(self._original_name, arguments=kwargs),
                    timeout=self._tool_timeout,
                )
            except asyncio.TimeoutError:
                return f"(MCP tool call timed out after {self._tool_timeout}s)"
            except asyncio.CancelledError:
                task = asyncio.current_task()
                if task is not None and task.cancelling() > 0:
                    raise
                return "(MCP tool call was cancelled)"
            except Exception as exc:
                if _is_transient(exc):
                    if attempt == 0:
                        await asyncio.sleep(1)
                        continue
                    return f"(MCP tool call failed after retry: {type(exc).__name__})"
                return f"(MCP tool call failed: {type(exc).__name__})"
            else:
                parts = []
                for block in result.content:
                    if isinstance(block, types.TextContent):
                        parts.append(block.text)
                    else:
                        parts.append(str(block))
                return "\n".join(parts) or "(no output)"
        return "(MCP tool call failed)"


class MCPResourceWrapper(Tool):
    def __init__(self, session, server_name: str, resource_def, resource_timeout: int = 30):
        self._session = session
        self._uri = resource_def.uri
        self.name = f"mcp_{server_name}_resource_{resource_def.name}"
        desc = resource_def.description or resource_def.name
        self.description = f"[MCP Resource] {desc}\nURI: {self._uri}"
        self.parameters = {"type": "object", "properties": {}, "required": []}
        self._resource_timeout = resource_timeout

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        from mcp import types

        for attempt in range(2):
            try:
                result = await asyncio.wait_for(
                    self._session.read_resource(self._uri),
                    timeout=self._resource_timeout,
                )
            except asyncio.TimeoutError:
                return f"(MCP resource read timed out after {self._resource_timeout}s)"
            except Exception as exc:
                if _is_transient(exc) and attempt == 0:
                    await asyncio.sleep(1)
                    continue
                return f"(MCP resource read failed: {type(exc).__name__})"
            else:
                parts = []
                for block in result.contents:
                    if isinstance(block, types.TextResourceContents):
                        parts.append(block.text)
                    elif isinstance(block, types.BlobResourceContents):
                        parts.append(f"[Binary resource: {len(block.blob)} bytes]")
                return "\n".join(parts) or "(no output)"
        return "(MCP resource read failed)"


class MCPManager:
    def __init__(self, workspace: Path, registry: ToolRegistry):
        self.workspace = workspace
        self.registry = registry
        self._server_stacks: Dict[str, AsyncExitStack] = {}

    async def connect_server(self, name: str, config: Dict[str, Any]):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.sse import sse_client
        from mcp.client.stdio import stdio_client

        stack = AsyncExitStack()
        await stack.__aenter__()

        try:
            transport_type = config.get("type", "stdio")
            if transport_type == "stdio":
                cmd, args, env = _normalize_windows_stdio_command(
                    config.get("command", ""),
                    config.get("args", []),
                    config.get("env"),
                )
                if not cmd:
                    await stack.aclose()
                    return

                params = StdioServerParameters(command=cmd, args=args, env=env)
                read, write = await stack.enter_async_context(stdio_client(params))
            elif transport_type == "sse":
                url = config.get("url")
                if not url:
                    await stack.aclose()
                    return
                read, write = await stack.enter_async_context(sse_client(url))
            else:
                logger.warning(f"Unsupported MCP transport: {transport_type}")
                await stack.aclose()
                return

            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            # Register Tools
            tools_res = await session.list_tools()
            for tool_def in tools_res.tools:
                wrapper = MCPToolWrapper(session, name, tool_def)
                self.registry.register(wrapper)

            # Register Resources
            try:
                res_res = await session.list_resources()
                for r_def in res_res.resources:
                    self.registry.register(MCPResourceWrapper(session, name, r_def))
            except Exception:
                pass

            self._server_stacks[name] = stack
            logger.info(f"Connected to MCP server: {name}")

        except Exception as e:
            hint = ""
            if any(m in str(e).lower() for m in ("parse error", "invalid json", "jsonrpc")):
                hint = " (Check for stdio protocol pollution)"
            logger.error(f"Failed to connect to MCP '{name}': {e}{hint}")
            await stack.aclose()

    async def disconnect_all(self):
        for name, stack in self._server_stacks.items():
            await stack.aclose()
        self._server_stacks = {}
