from langchain_mcp_adapters.client import MultiServerMCPClient

# ============================================================
# MCP CLIENT
# ============================================================
client = MultiServerMCPClient(
    {
        "file_handling": {
            "transport": "sse",
            "url": "http://mcp:8001/sse"
        }
    }
)

mcp_tools_cache = None

async def get_mcp_tools():
    global mcp_tools_cache
    if mcp_tools_cache is None:
        print("🔌 Connecting to MCP server and loading tools...")
        mcp_tools_cache = await client.get_tools()
        print(f"✅ Connected! Tools: {[t.name for t in mcp_tools_cache]}")
        print(f"total tools: {len(mcp_tools_cache)}")
    return mcp_tools_cache
