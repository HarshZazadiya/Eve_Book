from typing import TypedDict, Annotated, List, Dict, Any, Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
import json
from AI.RAG import llm, search_documents
from AI.tools.admin_tools import admin_tools
from AI.tools.host_tools import host_tools
from AI.tools.user_tools import user_tools
from AI.tools.default_tools import default_tools
from langchain_mcp_adapters.client import MultiServerMCPClient

# ============================================================
# MCP CLIENT
# ============================================================
# Initialize client (don't use context manager)
client = MultiServerMCPClient(
    {
        "file_handling": {
            "transport": "sse",
            "url": "http://127.0.0.1:8001/sse"
        }
    }
)

# Global for cached tools
_mcp_tools_cache = None

async def get_mcp_tools():
    """Get MCP tools (cached)"""
    global _mcp_tools_cache
    if _mcp_tools_cache is None:
        print("🔌 Connecting to MCP server and loading tools...")
        # Just call get_tools() directly - no __aenter__ needed
        _mcp_tools_cache = await client.get_tools()
        print(f"✅ Connected! Tools: {[t.name for t in _mcp_tools_cache]}")
    return _mcp_tools_cache

# ============================================================
# AGENT STATE
# ============================================================
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_info: Dict[str, Any]

# ============================================================
# RAG TOOL
# ============================================================
@tool
def search_event_documents(query: str) -> str:
    """Search through event documents for information about events."""
    print(f"🔍 Searching documents: {query}")
    result = search_documents(query, k=3)
    if not result:
        return "No information found in documents."
    return result

# ============================================================
# GET TOOLS FOR ROLE
# ============================================================
async def get_tools_for_role(role: str):
    """Get tools based on user role"""
    tools = []
    
    # Add role-specific tools
    if role == "admin":
        tools.extend(admin_tools)
    elif role == "host":
        tools.extend(host_tools)
    elif role == "user":
        tools.extend(user_tools)
    
    # Add default tools
    tools.extend(default_tools)
    
    # Add MCP tools
    try:
        mcp_tools = await get_mcp_tools()
        tools.extend(mcp_tools)
        print(f"✅ Added {len(mcp_tools)} MCP tools")
    except Exception as e:
        print(f"⚠️ Could not load MCP tools: {e}")
    
    return tools

# ============================================================
# AGENT NODE
# ============================================================
async def agent_node(state: AgentState):
    """Let LLM decide what to do"""
    messages = state["messages"]
    user_info = state["user_info"]

    # Get tools
    tools = await get_tools_for_role(user_info["role"])
    all_tools = tools + [search_event_documents]

    system_prompt = f"""You are an AI assistant for EveBook.

Current user: {user_info['name']} (role: {user_info['role']}, ID: {user_info['id']})

You have access to:
- Database operation tools
- File system tools 
- Document search for event PDFs

RULES:
- NEVER give stale or false information - use tools for real data
- NEVER let users know which tools you're using
- Output in pretty format
- Be honest and accurate

Decide what to do based on the user's request:
- Use database tools for user/event data
- Use file tools for reading/writing files
- Use document search for event PDF questions
- Respond naturally otherwise
"""

    llm_with_tools = llm.bind_tools(all_tools)

    response = await llm_with_tools.ainvoke([
        SystemMessage(content=system_prompt),
        *messages
    ])

    return {"messages": [response]}

# ============================================================
# TOOL NODE
# ============================================================
async def tool_node(state: AgentState):
    """Execute tools called by LLM"""
    messages = state["messages"]
    last_message = messages[-1]

    if not last_message.tool_calls:
        return {"messages": []}

    user_info = state["user_info"]
    
    # Get tools
    tools = await get_tools_for_role(user_info["role"])
    all_tools = tools + [search_event_documents]
    tool_map = {t.name: t for t in all_tools}

    results = []

    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call.get("args", {})
        tool_call_id = tool_call["id"]

        print(f"\n🛠️ Using: {tool_name}")

        if tool_name not in tool_map:
            results.append(ToolMessage(
                content=json.dumps({"error": f"Tool '{tool_name}' not found"}),
                tool_call_id=tool_call_id
            ))
            continue

        # Add auth context if needed
        tool_obj = tool_map[tool_name]
        if "authenticated_user_id" in str(tool_obj.args):
            tool_args["authenticated_user_id"] = user_info["id"]
        if "authenticated_host_id" in str(tool_obj.args):
            tool_args["authenticated_host_id"] = user_info["id"]
        if "authenticated_user_type" in str(tool_obj.args):
            tool_args["authenticated_user_type"] = user_info["role"]

        try:
            # Check if tool is async
            if hasattr(tool_obj, 'ainvoke'):
                result = await tool_obj.ainvoke(tool_args)
            else:
                result = tool_obj.invoke(tool_args)
            
            if isinstance(result, str):
                if result.strip().startswith(('✅', '📄', '❌', '📁')) or '\n' in result:
                    content = result
                else:
                    try:
                        parsed = json.loads(result)
                        if isinstance(parsed, dict) and 'readable_content' in parsed:
                            content = parsed['readable_content']
                        else:
                            content = result
                    except:
                        content = result
            else:
                content = json.dumps(result, default=str)
                
            results.append(ToolMessage(
                content=content,
                tool_call_id=tool_call_id
            ))
        except Exception as e:
            results.append(ToolMessage(
                content=json.dumps({"error": str(e)}),
                tool_call_id=tool_call_id
            ))

    return {"messages": results}

# ============================================================
# CONTINUE CONDITION
# ============================================================
def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """Decide next step"""
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        print(f"  🔄 AI wants to call: {[tc['name'] for tc in last_message.tool_calls]}")
        return "tools"

    print(f"  ✅ AI ready to respond")
    return "end"

# ============================================================
# BUILD GRAPH
# ============================================================
def build_agent_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    workflow.add_edge("tools", "agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "end": END}
    )

    workflow.set_entry_point("agent")
    return workflow.compile()

agent_graph = build_agent_graph()

# ============================================================
# AGENT EXECUTOR
# ============================================================
async def run_agent(user_input: str, user_info: Dict[str, Any], conversation_history: List[Dict] = None) -> str:
    """Run the agent"""
    
    print(f"\n🎯 Running agent for {user_info['name']}...")
    
    # Make sure MCP client is connected (just call get_tools to initialize)
    try:
        await get_mcp_tools()
    except Exception as e:
        print(f"⚠️ MCP connection issue: {e}")

    messages = []
    if conversation_history:
        for msg in conversation_history[-3:]:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))

    messages.append(HumanMessage(content=user_input))

    final_state = await agent_graph.ainvoke({
        "messages": messages,
        "user_info": user_info
    })

    for msg in reversed(final_state["messages"]):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            return msg.content

    return "I couldn't process that request."

# No cleanup needed - client handles its own connections