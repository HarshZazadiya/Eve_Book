import os
from langchain_groq import ChatGroq
from AI.utils.state import AgentState
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage, RemoveMessage, SystemMessage

summary_llm = ChatGroq(
    model = "llama-3.3-70b-versatile",
    temperature = 0,
    max_tokens = 2048,
    groq_api_key = os.getenv("GROQ_API_KEY")
)

prompt = """
    You are a summarizer.

    here is list of messages : {messages}

    here is previous summary (can be empty) : {summary}

    NOTES : 
    - you are performing this job to summarize the conversation.
    - your summary should be short and concise.
    - make sure summary covers all topics and information needed to keep coversation going, or might be helpful in future.
    - if summary is already present then keep in mind both summary and new messages list and create new summary.
    - if summary is not present then create a new summary.
"""

async def summarizer_node(state: AgentState):
    summary = state.get("summary", "")
    messages = state["messages"]
    
    # Keep only the last 5 messages
    RECENT_KEEP = 5
    
    if len(messages) > RECENT_KEEP:
        # Messages to summarize (all except last RECENT_KEEP)
        to_summarize = messages[:-RECENT_KEEP]
        recent_messages = messages[-RECENT_KEEP:]
        
        # Format messages for summarization
        formatted_messages = []
        for msg in to_summarize:
            if isinstance(msg, HumanMessage):
                formatted_messages.append(f"User: {msg.content}")
            elif isinstance(msg, AIMessage):
                formatted_messages.append(f"Assistant: {msg.content}")
        
        messages_text = "\n".join(formatted_messages)
        
        # Generate new summary
        system_prompt = prompt.format(messages=messages_text, summary=summary)
        result = await summary_llm.ainvoke(system_prompt)
        new_summary = result.content
        print("="*60)
        print(f"📝 Generated new summary ({len(to_summarize)} messages summarized)")
        print(f"📝 New summary: {new_summary}")
        print("="*60)
        # Create RemoveMessage for each old message
        messages_to_remove = [RemoveMessage(id = msg.id) for msg in to_summarize if hasattr(msg, 'id')]
        
        # Create summary message
        summary_message = SystemMessage(content=f"Conversation Summary : {new_summary}")
        
        # Return updates
        return {
            "summary" : new_summary,
            "messages" : [summary_message] + recent_messages + messages_to_remove
        }
    else:
        print(f"ℹ️ Not enough messages to summarize (have {len(messages)}, need > {RECENT_KEEP})")
        return state


async def build_summarizer_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("summarizer", summarizer_node)

    workflow.add_edge(START, "summarizer")
    workflow.add_edge("summarizer", END)

    return workflow.compile()

summarizer_graph = None

async def get_summarizer_graph():
    global summarizer_graph
    if summarizer_graph is None:
        summarizer_graph = await build_summarizer_graph()
    return summarizer_graph