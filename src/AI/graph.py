import os
import json
from database import SessionLocal
from AI.utils.state import AgentState
from langchain_core.tools import tool
from typing import  Dict, Any, Literal
from langgraph.prebuilt import ToolNode
from AI.mcp_manager import get_mcp_tools
from AI.RAG import llm, search_documents
from AI.tools.host_tools import host_tools
from AI.tools.user_tools import user_tools
from AI.utils.memories import search_memory
from AI.tools.admin_tools import admin_tools
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt, Command
from langgraph.graph.message import add_messages
from AI.tools.default_tools import default_tools
from AI.subgraphs.extractor_graph import get_extractor_graph
from AI.subgraphs.summarizer_graph import get_summarizer_graph
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.messages.utils import count_tokens_approximately
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage

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
# REMEMBERENCE NODE
# ============================================================
async def memory_retriver_node(state : AgentState) -> AgentState:
    """
    This node will take a look into database mainly the Memories table, to look for any data related to query
    to make the answer more peronalized.
    """
    user_info = state["user_info"]
    last_message = state["messages"][-1].content
    db = SessionLocal()

    memory = search_memory(user_id = user_info["id"], user_role = user_info["role"], query = last_message)
    state["memory"] = memory
    return state

# ============================================================
# AGENT NODE
# ============================================================
async def agent_node(state : AgentState):
    """
    LLM decides what to do.
    If a sensitive tool is requested, interrupt() pauses the graph
    and waits for the user to send back Command(resume="yes"/"no").
    The return value of interrupt() IS the resume value — exactly
    like the notebook pattern.
    """
    messages  = state["messages"]
    user_info = state["user_info"]
    summary   = state["summary"]

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
    
    context = []
    if summary:
        context.append(SystemMessage(content = f"""
                    Conversation Summary:
                    {summary}

                    Use this to maintain context. Do not repeat it explicitly.
                """))
        
    memory = state.get("memory", [])
    if memory:
        context.append(SystemMessage(content=f"""
                    User Memory:
                    {memory}

                    Use this to personalize the response.
                    Use the info in response, to answer the query.
                    Do not explicitly mention memory.
                """))
    system_message = SystemMessage(content = system_prompt)
    llm_with_tools = llm.bind_tools(all_tools)
    response = await llm_with_tools.ainvoke([system_message] + context + messages)

    # ── HITL: pause if any called tool is sensitive ──────────
    if response.tool_calls:
        user_sensitive_tools = set(user_info.get("sensitive_tools", []))
        sensitive_calls = [
            tc for tc in response.tool_calls
            if tc["name"] in user_sensitive_tools
        ]

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
tool_node_cache = {}

async def tool_node(state: AgentState):
    user_info = state["user_info"]

    tools = await get_tools_for_role(user_info["role"])
    all_tools = tools + [search_event_documents]
    
    # Get list of tool names that accept authentication parameters
    auth_tools = []
    for tool in all_tools:
        # Check if tool has these parameters in its args schema
        tool_args = str(tool.args)
        if "authenticated_user_id" in tool_args or "authenticated_user_type" in tool_args:
            auth_tools.append(tool.name)

    # Cache ToolNode per role
    role = user_info["role"]
    if role not in tool_node_cache:
        tool_node_cache[role] = ToolNode(all_tools)

    base_tool_node = tool_node_cache[role]

    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        for tc in last_message.tool_calls:
            new_args = dict(tc.get("args", {}))
            
            # Only add auth params if this tool accepts them
            if tc["name"] in auth_tools:
                new_args["authenticated_user_id"] = user_info["id"]
                new_args["authenticated_user_type"] = user_info["role"]
            
            tc["args"] = new_args

    try:
        result = await base_tool_node.ainvoke(state)
        return result
    except Exception as e:
        return {
            "messages": [
                ToolMessage(
                    content = json.dumps({"error" : str(e)}),
                    tool_call_id = "error"
                )
            ]
        }
    
# ============================================================
# ROUTING NODE 
# ============================================================
async def should_continue(state: AgentState) -> Literal["tools", "end"]:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        print(f"  🔄 AI wants to call: {[tc['name'] for tc in last_message.tool_calls]}")
        return "tools"
    print(f"  ✅ AI ready to respond")
    return "checker"

# ============================================================
# CHECKER NODE
# ============================================================
MAX_TOKENS = 3500
async def checker_node(state: AgentState) -> AgentState:
    messages = state["messages"]
    total_tokens = count_tokens_approximately(messages=messages)
    print(f"current tokens: {total_tokens} (max: {MAX_TOKENS})")
    
    if total_tokens > MAX_TOKENS and len(messages) > 10:
        print("Initializing summarizer Graph...")
        graph = await get_summarizer_graph()
        new_state = await graph.ainvoke(state)
        
        # Verify the new state
        new_messages = new_state.get("messages", [])
        new_tokens = count_tokens_approximately(messages=new_messages)
        print(f"✅ After summarization: {len(new_messages)} messages, {new_tokens} tokens")
        
        # Ensure we preserve other state fields
        if "user_info" not in new_state:
            new_state["user_info"] = state.get("user_info")
        if "memory" not in new_state:
            new_state["memory"] = state.get("memory", [])
            
        return new_state
    
    return state

# ============================================================
# EXTRACTOR NODE
# ============================================================
async def extractor_node(state: AgentState) -> AgentState:
    """this node will check if there is anything worthy of being extracted and put into long term memory for later use from current chat messages"""
    graph = await get_extractor_graph()
    return await graph.ainvoke(state)

# ============================================================
# CHECKPOINTER
# ============================================================
DATABASE_URL    = os.getenv("DATABASE_URL")
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

    workflow.add_node("memory_retriver_node", memory_retriver_node)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    workflow.add_node("extractor", extractor_node)
    workflow.add_node("checker", checker_node)

    workflow.add_edge("memory_retriver_node", "agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools" : "tools", "checker" : "checker"})
    workflow.add_edge("tools", "agent")
    workflow.add_edge("checker", "extractor")
    workflow.add_edge("extractor", END)

    workflow.set_entry_point("memory_retriver_node")

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
        "messages" : [HumanMessage(content=user_input)],
        "user_info":  user_info,
        "summary" : "",  # Initialize empty summary
        "memory" : []    # Initialize empty memory list
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