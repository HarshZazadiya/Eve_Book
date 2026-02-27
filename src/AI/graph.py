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

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_info: Dict[str, Any]


def get_tools_for_role(role: str):
    """Get tools based on user role"""
    tools = []
    
    if role == "admin":
        tools.extend(admin_tools)
    elif role == "host":
        tools.extend(host_tools)
    elif role == "user":
        tools.extend(user_tools)
    
    # Add default tools for everyone
    tools.extend(default_tools)
    
    return tools

# ============================================================
# RAG TOOL
# ============================================================
@tool
def search_event_documents(query: str) -> str:
    """
    Search through event documents for information about events.
    Use this for questions about event details, food, venue, dates, etc.
    """
    print(f"🔍 Searching documents: {query}")
    result = search_documents(query, k=3)
    if not result:
        return "No information found in documents."
    return result

# ============================================================
# AGENT NODE
# ============================================================
def agent_node(state: AgentState):
    """Let LLM decide what to do - no hardcoding"""
    messages = state["messages"]
    user_info = state["user_info"]
    
    # Get tools for this role
    tools = get_tools_for_role(user_info["role"])
    all_tools = tools + [search_event_documents]
    
    # Simple prompt - let LLM figure it out
    system_prompt = f"""You are an AI assistant for EveBook.

                        Current user: {user_info['name']} , role :({user_info['role']}, ID : {user_info['id']})

                        You have access to:
                        - Tools for database operations
                        - Document search for event PDFs

                        Decide what to do based on the user's request.
                        - Use tools when you need real data from the system
                        - Use document search when users ask about event details
                        - Respond naturally otherwise

                        RULES FOR ANSWERING : 
                        - NEVER GIVE STALE INFORMATION, USE REAL DATA FROM THE SYSTEM
                        - NEVER GIVE FALSE INFORMATION.
                        - NEVER MAKE UP THINGS.
                        - NEVER LET USER KNOW WHICH TOOLS YOU ARE USING.
                        - NEVER LET USER KNOW YOU ARE USING DOCUMENT SEARCH.
                        - USER ONLY GETS ANSWER FOR WHAT THEY ASKED
                        - TRY TO OUTPUT IN PRETTY FORMAT ALWAYS.

                        Be honest and accurate.
                    """
    
    llm_with_tools = llm.bind_tools(all_tools)
    
    response = llm_with_tools.invoke([
        SystemMessage(content=system_prompt),
        *messages
    ])
    
    return {"messages" : [response]}


# ============================================================
# TOOL NODE
# ============================================================
def tool_node(state: AgentState):
    """Execute tools called by LLM"""
    messages = state["messages"]
    last_message = messages[-1]
    
    if not last_message.tool_calls:
        return {"messages": []}
    
    user_info = state["user_info"]
    tools = get_tools_for_role(user_info["role"]) + [search_event_documents]
    tool_map = {tool.name: tool for tool in tools}
    
    results = []
    
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call.get("args", {})
        
        print(f"\n🛠️ Using: {tool_name}")
        
        # Add authentication based on tool type
        if "authenticated_user_id" in str(tool_map[tool_name].args):
            tool_args["authenticated_user_id"] = user_info["id"]
        
        if "authenticated_host_id" in str(tool_map[tool_name].args):
            tool_args["authenticated_host_id"] = user_info["id"]
        
        if "authenticated_user_type" in str(tool_map[tool_name].args):
            tool_args["authenticated_user_type"] = user_info["role"]
        
        try:
            result = tool_map[tool_name].invoke(tool_args)
            results.append(
                ToolMessage(
                    content=json.dumps(result, default=str),
                    tool_call_id=tool_call["id"]
                )
            )
        except Exception as e:
            results.append(
                ToolMessage(
                    content=json.dumps({"error": str(e)}),
                    tool_call_id=tool_call["id"]
                )
            )
    
    return {"messages": results}

# ============================================================
# CONTINUE CONDITION
# ============================================================
def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """Decide next step"""
    last_message = state["messages"][-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
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
        {
            "tools": "tools",
            "end": END
        }
    )
    
    workflow.set_entry_point("agent")
    return workflow.compile()

agent_graph = build_agent_graph()

# ============================================================
# AGENT EXECUTOR
# ============================================================
async def run_agent(user_input : str, user_info : Dict[str, Any], conversation_history: List[Dict] = None) -> str:
    """Run the agent"""
    
    messages = []
    if conversation_history:
        for msg in conversation_history[-3:]:
            if msg["role"] == "user":
                messages.append(HumanMessage(content = msg["content"]))
            else:
                messages.append(AIMessage(content = msg["content"]))
    
    messages.append(HumanMessage(content=user_input))
    
    final_state = await agent_graph.ainvoke({
        "messages" : messages,
        "user_info" : user_info
    })
    
    for msg in reversed(final_state["messages"]):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            return msg.content
    
    return "I couldn't process that request."