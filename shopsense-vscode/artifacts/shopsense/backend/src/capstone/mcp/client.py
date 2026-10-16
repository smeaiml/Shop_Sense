"""Small MCP stdio client for channel adapters that need tool discovery."""

from __future__ import annotations

import sys
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def call_shop_sense_tool(name: str, arguments: dict[str, Any]) -> Any:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "capstone.mcp.server"],
    )
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(name, arguments)
            if result.isError:
                raise RuntimeError(f"MCP tool failed: {name}")
            return result.content
