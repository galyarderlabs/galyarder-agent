"""MCP manager for G-Agent: connects to and manages external tool servers."""

import asyncio
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Dict

from loguru import logger

from g_agent.agent.tools.registry import ToolRegistry
from g_agent.agent.tools.base import Tool


class MCPToolWrapper(Tool):
    """Wraps an MCP tool as a G-Agent tool."""

    def __init__(self, session: Any, server_name: str, tool_def: Any, timeout: int = 30):
        self._session = session
        self._original_name = tool_def.name
        self.name = f"mcp_{server_name}_{tool_def.name}"
        self.description = tool_def.description or self.name
        # Simple schema normalization could go here
        self.parameters = tool_def.inputSchema or {"type": "object", "properties": {}}
        self._timeout = timeout

    async def execute(self, **kwargs: Any) -> str:
        from mcp import types

        try:
            result = await asyncio.wait_for(
                self._session.call_tool(self._original_name, arguments=kwargs),
                timeout=self._timeout,
            )

            parts = []
            for block in result.content:
                if isinstance(block, types.TextContent):
                    parts.append(block.text)
                else:
                    parts.append(str(block))
            return "\n".join(parts) or "(no output)"

        except asyncio.TimeoutError:
            return f"Error: MCP tool '{self.name}' timed out after {self._timeout}s"
        except Exception as e:
            logger.exception(f"MCP tool '{self.name}' failed")
            return f"Error executing MCP tool: {str(e)}"


class MCPManager:
    """Manages connections to multiple MCP servers."""

    def __init__(self, workspace: Path, registry: ToolRegistry):
        self.workspace = workspace
        self.registry = registry
        self._server_stacks: Dict[str, AsyncExitStack] = {}

    async def connect_server(self, name: str, config: Dict[str, Any]):
        """Connect to a single MCP server based on config."""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        stack = AsyncExitStack()
        await stack.__aenter__()

        try:
            transport_type = config.get("type", "stdio")

            if transport_type == "stdio":
                command = config.get("command")
                args = config.get("args", [])
                env = config.get("env")

                if not command:
                    logger.warning(f"MCP server '{name}' missing command, skipping")
                    await stack.aclose()
                    return

                params = StdioServerParameters(command=command, args=args, env=env)
                read, write = await stack.enter_async_context(stdio_client(params))

                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()

                # List and register tools
                tools_result = await session.list_tools()
                for tool_def in tools_result.tools:
                    wrapper = MCPToolWrapper(session, name, tool_def)
                    self.registry.register(wrapper)
                    logger.info(f"Registered MCP tool: {wrapper.name}")

                self._server_stacks[name] = stack
                logger.info(f"Successfully connected to MCP server: {name}")

            else:
                logger.warning(f"Unsupported MCP transport type: {transport_type}")
                await stack.aclose()

        except Exception as e:
            logger.error(f"Failed to connect to MCP server '{name}': {e}")
            await stack.aclose()

    async def disconnect_all(self):
        """Close all active MCP server connections."""
        for name, stack in self._server_stacks.items():
            logger.info(f"Disconnecting MCP server: {name}")
            await stack.aclose()
        self._server_stacks = {}
