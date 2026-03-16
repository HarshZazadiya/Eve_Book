from typing import TypedDict, Annotated, List, Dict, Any, Literal
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.types import interrupt, Command
import json
from AI.RAG import llm, search_documents
from AI.tools.admin_tools import admin_tools
from AI.tools.host_tools import host_tools
from AI.tools.user_tools import user_tools
from AI.tools.default_tools import default_tools
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import os

# ============================================================
# MCP CLIENT
# ============================================================
client = MultiServerMCPClient(
    {
        "file_handling": {
            "transport": "sse",
            "url": "http://127.0.0.1:8001/sse"
        }
    }
)

_mcp_tools_cache = None

async def get_mcp_tools():
    global _mcp_tools_cache
    if _mcp_tools_cache is None:
        print("🔌 Connecting to MCP server and loading tools...")
        _mcp_tools_cache = await client.get_tools()
        print(f"✅ Connected! Tools: {[t.name for t in _mcp_tools_cache]}")
        print(f"total tools: {len(_mcp_tools_cache)}")
    return _mcp_tools_cache

# ============================================================
# AGENT STATE
# ============================================================
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_info: Dict[str, Any]

# ============================================================
# SENSITIVE TOOLS — require user approval before execution
# ============================================================
SENSITIVE_TOOLS = {
    "delete_event",
    "delete_user",
    "delete_booking",
    "top_up",
    "transfer_funds",
    "delete_file",
}

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
    tools = []
    if role == "admin":
        tools.extend(admin_tools)
    elif role == "host":
        tools.extend(host_tools)
    elif role == "user":
        tools.extend(user_tools)
    tools.extend(default_tools)
    try:
        mcp_tools = await get_mcp_tools()
        tools.extend(mcp_tools)
    except Exception as e:
        print(f"⚠️ Could not load MCP tools: {e}")
    return tools

# ============================================================
# AGENT NODE
# ============================================================
async def agent_node(state: AgentState):
    """
    LLM decides what to do.
    If a sensitive tool is requested, interrupt() pauses the graph
    and waits for the user to send back Command(resume="yes"/"no").
    The return value of interrupt() IS the resume value — exactly
    like the notebook pattern.
    """
    messages  = state["messages"]
    user_info = state["user_info"]

    tools     = await get_tools_for_role(user_info["role"])
    all_tools = tools + [search_event_documents]

    system_prompt = f"""You are an AI assistant for EveBook.
MAIN RULE FOR ANSWERING ANY QUERY:
    - IT SHOULD ONLY BE RELEVANT TO THIS EVENT BOOKING APP
    - NEVER ANSWER QUERIES ABOUT ANYTHING ELSE THAT CAN'T BE ANSWERED BY TOOLS, MCP TOOLS OR RAG FETCHED DOCUMENTS
    - YOUR ANSWER SHOULD ONLY BE FROM TOOLS, MCP TOOLS OR RAG FETCHED DOCUMENTS.
    - NEVER MAKE UP THINGS, ALWAYS USE TOOLS TO ANSWER QUERIES. OR USE CHAT CONTEXT

Current user: {user_info['name']} (role: {user_info['role']}, ID: {user_info['id']})

You have access to:
- Database operation tools
- File system tools
- Document search for event PDFs

RULES:
- NEVER give stale or false information - use tools for real data
- NEVER let users know which tools you're using
- Output in pretty format
- Be honest and accurate"""

    llm_with_tools = llm.bind_tools(all_tools)
    response = await llm_with_tools.ainvoke([
        SystemMessage(content=system_prompt),
        *messages
    ])

    # print(f"🤖 LLM response : {response.content}")
    # print(f"🛠️ Tools calling : {response.tool_calls}")

    # ── HITL: pause if any called tool is sensitive ──────────
    # Pattern from notebook:
    #   decision = interrupt({...payload...})
    #   decision IS the value passed to Command(resume=...) on next invoke
    if response.tool_calls:
        sensitive_calls = [tc for tc in response.tool_calls if tc["name"] in SENSITIVE_TOOLS]

        if sensitive_calls:
            tool_names = [tc["name"] for tc in sensitive_calls]
            tool_args  = [tc["args"]  for tc in sensitive_calls]
            print(f"⚠️  HITL triggered for: {tool_names}")

            # interrupt() suspends the graph here.
            # The VALUE returned by interrupt() is whatever is passed
            # to Command(resume=...) when the graph is resumed.
            decision = interrupt({
                "type":    "hitl_approval",
                "tools":   tool_names,
                "args":    tool_args,
                "message": (
                    f"⚠️ The assistant wants to run: **{', '.join(tool_names)}**\n"
                    f"Arguments: `{json.dumps(tool_args, indent=2)}`\n\n"
                    "Do you approve? (yes / no)"
                ),
            })

            # decision = "yes" or "no" (string sent back from the client)
            print(f"👤 User decision: {decision}")

            if str(decision).strip().lower() not in ("yes", "y"):
                return {
                    "messages": [
                        AIMessage(content=(
                            f"Action cancelled. You chose not to run "
                            f"**{', '.join(tool_names)}**."
                        ))
                    ]
                }
            # "yes" → fall through and return the tool-call response normally

    return {"messages": [response]}

# ============================================================
# TOOL NODE
# ============================================================
async def tool_node(state: AgentState):
    messages     = state["messages"]
    last_message = messages[-1]

    if not last_message.tool_calls:
        return {"messages": []}

    user_info = state["user_info"]
    tools     = await get_tools_for_role(user_info["role"])
    all_tools = tools + [search_event_documents]
    tool_map  = {t.name: t for t in all_tools}
    results   = []

    for tool_call in last_message.tool_calls:
        tool_name    = tool_call["name"]
        tool_args    = tool_call.get("args", {})
        tool_call_id = tool_call["id"]

        print(f"\n🛠️ Using: {tool_name}")

        if tool_name not in tool_map:
            results.append(ToolMessage(
                content=json.dumps({"error": f"Tool '{tool_name}' not found"}),
                tool_call_id=tool_call_id
            ))
            continue

        tool_obj = tool_map[tool_name]
        if "authenticated_user_id"   in str(tool_obj.args): tool_args["authenticated_user_id"]   = user_info["id"]
        if "authenticated_host_id"   in str(tool_obj.args): tool_args["authenticated_host_id"]   = user_info["id"]
        if "authenticated_user_type" in str(tool_obj.args): tool_args["authenticated_user_type"] = user_info["role"]

        try:
            result = await tool_obj.ainvoke(tool_args) if hasattr(tool_obj, "ainvoke") else tool_obj.invoke(tool_args)

            if isinstance(result, str):
                try:
                    parsed  = json.loads(result)
                    content = parsed.get("readable_content", result) if isinstance(parsed, dict) else result
                except Exception:
                    content = result
            else:
                content = json.dumps(result, default=str)

            results.append(ToolMessage(content=content, tool_call_id=tool_call_id))

        except Exception as e:
            results.append(ToolMessage(
                content=json.dumps({"error": str(e)}),
                tool_call_id=tool_call_id
            ))

    # print("results", results)
    return {"messages": results}

# ============================================================
# ROUTING
# ============================================================
def should_continue(state: AgentState) -> Literal["tools", "end"]:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        print(f"  🔄 AI wants to call: {[tc['name'] for tc in last_message.tool_calls]}")
        return "tools"
    print(f"  ✅ AI ready to respond")
    return "end"

# ============================================================
# CHECKPOINTER
# ============================================================
DATABASE_URL     = os.getenv("DATABASE_URL")
_checkpointer    = None
_checkpointer_cm = None

async def init_checkpointer():
    global _checkpointer, _checkpointer_cm
    print("🔄 Initializing async Postgres checkpointer...")
    _checkpointer_cm = AsyncPostgresSaver.from_conn_string(DATABASE_URL)
    _checkpointer    = await _checkpointer_cm.__aenter__()
    await _checkpointer.setup()
    print("✅ Async checkpointer ready")

async def close_checkpointer():
    global _checkpointer_cm
    if _checkpointer_cm is not None:
        await _checkpointer_cm.__aexit__(None, None, None)
        print("🔒 Checkpointer connection closed")

def get_checkpointer():
    if _checkpointer is None:
        raise RuntimeError("Checkpointer not initialized. Call init_checkpointer() at startup.")
    return _checkpointer

# ============================================================
# BUILD GRAPH  (no interrupt_before — interrupt is mid-node)
# ============================================================
_agent_graph = None

def _build_workflow():
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    workflow.add_edge("tools", "agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})
    workflow.set_entry_point("agent")
    return workflow

def get_agent_graph():
    global _agent_graph
    if _agent_graph is None:
        # NOTE: no interrupt_before= here — the interrupt lives inside agent_node
        _agent_graph = _build_workflow().compile(checkpointer=get_checkpointer())
        print("✅ Agent graph compiled with checkpointer")
    return _agent_graph

# ============================================================
# AGENT EXECUTOR
# ============================================================
async def run_agent(
    user_input: str,
    thread_id: int,
    user_info: Dict[str, Any],
    human_approval: str = None,   # "yes"/"no" on HITL resume turn
) -> Dict[str, Any]:
    """
    Returns:
        {"type": "response",      "content": str}
        {"type": "hitl_required", "content": str, "tools": list, "args": list}
    """
    print(f"\n🎯 Running agent for {user_info['name']}...")

    try:
        await get_mcp_tools()
    except Exception as e:
        print(f"⚠️ MCP connection issue: {e}")

    graph  = get_agent_graph()
    config = {"configurable": {"thread_id": str(thread_id)}}

    # ── STEP 2: HITL resume — user replied yes/no ─────────────
    # Mirrors notebook:  app.invoke(Command(resume={"approved": user_input}), config)
    # We send back just the plain string "yes"/"no"
    if human_approval is not None:
        print(f"▶️  Resuming graph with approval='{human_approval}'")
        final_state = await graph.ainvoke(
            Command(resume=human_approval),
            config=config,
        )
        return _extract_response(final_state)

    # ── STEP 1: Normal first-turn invoke ──────────────────────
    initial_state = {
        "messages":  [HumanMessage(content=user_input)],
        "user_info": user_info,
    }

    final_state = await graph.ainvoke(initial_state, config=config)

    # If the graph was interrupted, ainvoke() returns the state WITH
    # a '__interrupt__' key — exactly like the notebook's result dict.
    if "__interrupt__" in final_state:
        interrupts = final_state["__interrupt__"]
        if interrupts:
            payload = interrupts[0].value   # the dict passed to interrupt()
            print(f"⏸️  Graph interrupted — payload: {payload}")
            return {
                "type":    "hitl_required",
                "content": payload.get("message", "Approval required."),
                "tools":   payload.get("tools", []),
                "args":    payload.get("args",  []),
            }

    return _extract_response(final_state)


def _extract_response(final_state: dict) -> Dict[str, Any]:
    """Pull the last AIMessage text out of a completed graph state."""
    if not final_state:
        return {"type": "response", "content": "I couldn't process that request."}

    messages = final_state.get("messages", [])
    # print(f"\n📨 Final state messages ({len(messages)}):")
    # for msg in messages:
        # print(f"  [{type(msg).__name__}] tool_calls={getattr(msg,'tool_calls',[])} | content={str(msg.content)[:80]}")

    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls and msg.content:
            return {"type": "response", "content": msg.content}

    return {"type": "response", "content": "I couldn't process that request."}