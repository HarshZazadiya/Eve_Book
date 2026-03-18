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
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import os
from AI.mcp_manager import get_mcp_tools

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
    "delet_file",
    "delete_pdf",
    "update_file",
    "update_pdf",
    "top_up_wallet",
    "change_directory"
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

    system_prompt = f"""
                        You are an AI assistant for EveBook.
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
                        - Be honest and accurate
                        """
    system_message = SystemMessage(content=system_prompt)
    llm_with_tools = llm.bind_tools(all_tools)
    response = await llm_with_tools.ainvoke([system_message] + messages)

    # ── HITL: pause if any called tool is sensitive ──────────
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
                "type" :    "hitl_approval",
                "tools" :   tool_names,
                "args" :    tool_args,
                "message": (
                    f"⚠️ The assistant wants to run: **{', '.join(tool_names)}**\n"
                    f"Arguments: `{json.dumps(tool_args, indent = 2)}`\n\n"
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
from langgraph.prebuilt import ToolNode

tool_node_cache = {}

async def tool_node(state: AgentState):
    user_info = state["user_info"]

    tools = await get_tools_for_role(user_info["role"])
    all_tools = tools + [search_event_documents]

    # Cache ToolNode per role
    role = user_info["role"]
    if role not in tool_node_cache:
        tool_node_cache[role] = ToolNode(all_tools)

    base_tool_node = tool_node_cache[role]

    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        for tc in last_message.tool_calls:
            new_args = dict(tc.get("args", {}))
            new_args["authenticated_user_id"] = user_info["id"]
            new_args["authenticated_user_type"] = user_info["role"]
            # new_args["authenticated_host_id"] = user_info["id"]
            tc["args"] = new_args

    try:
        result = await base_tool_node.ainvoke(state)
        return result
    except Exception as e:
        return {
            "messages": [
                ToolMessage(
                    content=json.dumps({"error": str(e)}),
                    tool_call_id="error"
                )
            ]
        }
    
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
checkpointer    = None
checkpointer_cm = None

async def init_checkpointer():
    global checkpointer, checkpointer_cm
    print("🔄 Initializing async Postgres checkpointer...")
    checkpointer_cm = AsyncPostgresSaver.from_conn_string(DATABASE_URL)
    checkpointer    = await checkpointer_cm.__aenter__()
    await checkpointer.setup()
    print("✅ Async checkpointer ready")

async def close_checkpointer():
    global checkpointer_cm
    if checkpointer_cm is not None:
        await checkpointer_cm.__aexit__(None, None, None)
        print("🔒 Checkpointer connection closed")

def get_checkpointer():
    if checkpointer is None:
        raise RuntimeError("Checkpointer not initialized. Call init_checkpointer() at startup.")
    return checkpointer

# ============================================================
# BUILD GRAPH  (no interrupt_before — interrupt is mid-node)
# ============================================================
agent_graph = None

def build_workflow():
    workflow = StateGraph(AgentState)

    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    workflow.add_edge("tools", "agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "end": END})

    workflow.set_entry_point("agent")

    return workflow

def get_agent_graph():
    global agent_graph
    if agent_graph is None:
        # NOTE: no interrupt_before= here — the interrupt lives inside agent_node
        agent_graph = build_workflow().compile(checkpointer = get_checkpointer())
        print("✅ Agent graph compiled with checkpointer")
    return agent_graph

# ============================================================
# AGENT EXECUTOR
# ============================================================
async def run_agent(user_input : str, thread_id : int, user_info : Dict[str, Any], human_approval : str = None) -> Dict[str, Any]:
    """
    Returns:
        {"type": "response",      "content": str}
        {"type": "hitl_required", "content": str, "tools": list, "args": list}
    """
    global graph
    print(f"\n🎯 Running agent for {user_info['name']}...")

    try:
        await get_mcp_tools()
    except Exception as e:
        print(f"⚠️ MCP connection issue: {e}")

    graph  = get_agent_graph()
    config = {"configurable": {"thread_id": str(thread_id)}}

    # ── HITL resume — user replied yes/no ─────────────────────
    if human_approval is not None:
        print(f"▶️  Resuming graph with approval='{human_approval}'")
        # Snapshot how many messages exist before resume
        prior_state   = await graph.aget_state(config)
        prior_count   = len(prior_state.values.get("messages", [])) if prior_state.values else 0
        final_state   = await graph.ainvoke(Command(resume=human_approval), config=config)
        return extract_response(final_state, prior_count)

    # ── Normal first-turn invoke ───────────────────────────────
    # Snapshot message count BEFORE this invocation so we can
    # isolate only the new messages added during this turn.
    prior_state = await graph.aget_state(config)
    prior_count = len(prior_state.values.get("messages", [])) if prior_state.values else 0
    print(f"📊 Prior message count in thread: {prior_count}")

    initial_state = {
        "messages" :  [HumanMessage(content=user_input)],
        "user_info" : user_info,
    }

    final_state = await graph.ainvoke(initial_state, config=config)

    # Check for interrupt
    if "__interrupt__" in final_state:
        interrupts = final_state["__interrupt__"]
        if interrupts:
            payload = interrupts[0].value
            print(f"⏸️  Graph interrupted — payload: {payload}")
            return {
                "type":    "hitl_required",
                "content": payload.get("message", "Approval required."),
                "tools":   payload.get("tools", []),
                "args":    payload.get("args",  []),
            }

    return extract_response(final_state, prior_count)


def extract_response(final_state : dict, prior_count : int = 0) -> Dict[str, Any]:
    """
    Pull the last AIMessage text + tool calls from the CURRENT turn only.
    prior_count = number of messages that existed before this invocation.
    We only look at messages[prior_count:] for tool calls.
    """
    if not final_state:
        return {"type": "response", "content": "I couldn't process that request.", "tools_used": []}

    messages = final_state.get("messages", [])

    # Only messages added THIS turn (after the prior snapshot)
    current_turn_msgs = messages[prior_count:]
    print(f"🔍 Current turn messages : {len(current_turn_msgs)}")

    tools_used = []
    for msg in current_turn_msgs:
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                tools_used.append({
                    "name" : tc.get("name", "unknown"),
                    "args" : tc.get("args", {}),
                })

    print(f"🔧 Tools used this turn: {[t['name'] for t in tools_used]}")

    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls and msg.content:
            return {"type": "response", "content": msg.content, "tools_used": tools_used}

    return {"type" : "response", "content" : "I couldn't process that request.", "tools_used" : tools_used}