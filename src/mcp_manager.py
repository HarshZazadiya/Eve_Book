"""
MCP manager — reads MCP_SERVER_URL from the environment so it works
both locally (http://127.0.0.1:8001/sse) and in Docker (http://mcp:8001/sse).
"""
import os
from langchain_mcp_adapters.client import MultiServerMCPClient

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8001/sse")

_client: MultiServerMCPClient | None = None
_mcp_tools: list | None = None


async def get_mcp_tools() -> list:
    global _client, _mcp_tools

    if _mcp_tools is not None:
        return _mcp_tools

    _client = MultiServerMCPClient(
        {
            "filesystem": {
                "url": MCP_SERVER_URL,
                "transport": "sse",
            }
        }
    )
    _mcp_tools = await _client.get_tools()
    print(f"✅ Loaded {len(_mcp_tools)} MCP tools from {MCP_SERVER_URL}")
    return _mcp_tools