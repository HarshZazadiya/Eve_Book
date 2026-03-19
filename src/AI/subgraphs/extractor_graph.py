import os
from model import Memories
from pydantic import BaseModel
from AI.utils.state import AgentState
from typing import List, Literal
from database import SessionLocal
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import HumanMessage, AIMessage
from AI.RAG import embeddings
# ============================================================
# LLM SETUP
# ============================================================

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    max_tokens=2048,
    groq_api_key=os.getenv("GROQ_API_KEY")
)

# ============================================================
# PROMPT - FIXED: Using a raw string to avoid formatting issues
# ============================================================

PROMPT_TEMPLATE = """
You are a memory extraction system.

Your job is to extract useful long-term memory about the user.

Rules:
- Only extract stable facts (preferences, personal info, habits, goals)
- Ignore temporary conversation
- Do NOT include full messages
- Keep memory concise and structured
- If nothing important, return empty list

Return JSON in this exact format:
{
  "memories": [
    {
      "type": "preference",
      "key": "color",
      "value": "pink"
    }
  ]
}

Conversation:
{conversation}
"""

# ============================================================
# SCHEMA
# ============================================================

class MemoryItem(BaseModel):
    type: Literal["preference", "personal/fact", "goal", "habit"]
    key: str
    value: str


class ExtractedMemory(BaseModel):
    memories: List[MemoryItem]


extractor_llm = llm.with_structured_output(ExtractedMemory)

# ============================================================
# MEMORY SAVER 
# ============================================================

async def memory_saver(user_info, memories: List[MemoryItem]):
    db = SessionLocal()

    try:
        for memory in memories:
            # Check if memory already exists
            existing = db.query(Memories).filter_by(
                user_id=user_info["id"], 
                key=memory.key
            ).first()

            # Generate embedding for the memory value
            memory_embedding = embeddings.embed_query(memory.value)

            if existing:
                # update existing memory
                existing.value = memory.value
                existing.type = memory.type
                existing.embedding = memory_embedding  # Update embedding too
                print(f"🔄 Updated memory: {memory.key} = {memory.value}")
            else:
                # insert new memory with embedding
                db.add(Memories(
                    user_id=user_info["id"],
                    user_role=user_info["role"],
                    type=memory.type,
                    key=memory.key,
                    value=memory.value,
                    embedding=memory_embedding  # Add the embedding here
                ))
                print(f"✅ Added memory: {memory.key} = {memory.value}")

        db.commit()
        print(f"📝 Saved {len(memories)} memories")

    except Exception as e:
        print(f"❌ Error saving memories: {e}")
        db.rollback()
    finally:
        db.close()

# ============================================================
# EXTRACTOR NODE
# ============================================================

async def extractor_node(state: AgentState) -> AgentState:
    try:
        messages = state["messages"]
        user_info = state["user_info"]

        # Format conversation history
        conversation_lines = []
        for msg in messages[-10:]:  # Last 10 messages max
            if isinstance(msg, HumanMessage):
                conversation_lines.append(f"User: {msg.content}")
            elif isinstance(msg, AIMessage):
                conversation_lines.append(f"Assistant: {msg.content}")
        
        conversation = "\n".join(conversation_lines)
        
        if not conversation:
            print("⚠️ No conversation to extract from")
            return state

        # Format prompt - using simple string replacement
        system_prompt = PROMPT_TEMPLATE.replace("{conversation}", conversation)

        # Extract memories
        result = await extractor_llm.ainvoke(system_prompt)
        
        # Save if we got any memories
        if result and result.memories:
            await memory_saver(user_info, result.memories)
            print(f"✅ Extracted {len(result.memories)} memories")
            print(f"📝 Saved {result.memories} memories")
            print("="*60,end="\n")
        else:
            print("ℹ️ No memories extracted")

    except Exception as e:
        print(f"❌ Error in extractor node: {e}")
        import traceback
        traceback.print_exc()
    
    return state

# ============================================================
# GRAPH BUILD
# ============================================================

async def build_extractor_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("extractor", extractor_node)

    workflow.add_edge(START, "extractor")
    workflow.add_edge("extractor", END)

    return workflow.compile()

# ============================================================
# GRAPH GETTER 
# ============================================================

extractor_graph = None

async def get_extractor_graph():
    global extractor_graph
    if extractor_graph is None:
        extractor_graph = await build_extractor_graph()
        print("✅ Extractor graph compiled")
    return extractor_graph