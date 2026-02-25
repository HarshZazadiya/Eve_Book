# AI/RAG.py

from typing import TypedDict, Optional
from sqlalchemy.orm import Session
from langchain_ollama import ChatOllama
from langchain_core.messages import (
    HumanMessage,
    SystemMessage,
    AIMessage,
)
from langgraph.graph import StateGraph, END
from model import Events
from langchain_community.vectorstores import FAISS
from pathlib import Path

# =============================
# CONFIG
# =============================

llm = ChatOllama(model="mistral", temperature=0)

BASE_DIR = Path(__file__).resolve().parent.parent
VECTOR_DIR = BASE_DIR / "vector_store"
FAISS_INDEX_PATH = VECTOR_DIR / "faiss_index"

# =============================
# STATE
# =============================

class GraphState(TypedDict):
    question: str
    db: Session
    conversation: list
    classification: Optional[str]
    event_data: Optional[list]
    document_context: Optional[str]
    final_answer: Optional[str]


# =============================
# NODE 1 — CLASSIFY
# =============================

def classify_node(state: GraphState):
    question = state["question"]

    messages = [
        SystemMessage(content="""
You are a classifier.
If the message is related to events, tickets, price, seats, venue, booking, etc → return ONLY: EVENT_QUERY
If it is greeting or general conversation → return ONLY: NORMAL_CHAT
Do not explain.
"""),
        HumanMessage(content=question)
    ]

    response = llm.invoke(messages).content.strip()

    return {"classification": response}


# =============================
# NODE 2 — NORMAL CHAT
# =============================

def normal_chat_node(state: GraphState):
    messages = [
        SystemMessage(content="""
You are an assistant inside an event booking website.
Answer politely and briefly.
"""),
    ]

    messages.extend(state["conversation"])
    messages.append(HumanMessage(content=state["question"]))

    response = llm.invoke(messages).content

    return {"final_answer": response}


# =============================
# NODE 3 — FETCH EVENT METADATA
# =============================

def fetch_event_metadata_node(state: GraphState):
    db = state["db"]
    question = state["question"]

    events = db.query(Events).all()

    summary = []
    for e in events:
        summary.append(
            f"{e.title} | Price: {e.ticket_price} | Seats: {e.available_seats}"
        )

    return {"event_data": summary}


# =============================
# NODE 4 — CHECK IF ANSWERABLE FROM METADATA
# =============================

def metadata_answer_node(state: GraphState):
    question = state["question"]
    metadata = "\n".join(state["event_data"])

    messages = [
        SystemMessage(content="""
You must decide:
Can the user question be fully answered from the metadata below?

If YES → answer the question directly.
If NO → return ONLY: NEED_DOCUMENT
"""),
        HumanMessage(content=f"""
Metadata:
{metadata}

Question:
{question}
""")
    ]

    response = llm.invoke(messages).content.strip()

    if response == "NEED_DOCUMENT":
        return {"final_answer": None}
    else:
        return {"final_answer": response}


# =============================
# NODE 5 — DOCUMENT RETRIEVAL
# =============================

def document_node(state: GraphState):
    if not FAISS_INDEX_PATH.exists():
        return {"document_context": None}

    vector_store = FAISS.load_local(
        FAISS_INDEX_PATH,
        llm,  # embeddings not needed for load
        allow_dangerous_deserialization=True,
    )

    docs = vector_store.similarity_search(
        state["question"],
        k=3
    )

    if not docs:
        return {"document_context": None}

    text = "\n".join([d.page_content for d in docs])
    return {"document_context": text}


# =============================
# NODE 6 — FINAL DOC ANSWER
# =============================

def document_answer_node(state: GraphState):
    if not state["document_context"]:
        return {"final_answer": "No information found for your query."}

    messages = [
        SystemMessage(content="""
Answer ONLY using the document context.
If answer not found, say:
No information found for your query.
"""),
        HumanMessage(content=f"""
Document:
{state["document_context"]}

Question:
{state["question"]}
""")
    ]

    response = llm.invoke(messages).content
    return {"final_answer": response}


# =============================
# BUILD GRAPH
# =============================

builder = StateGraph(GraphState)

builder.add_node("classify", classify_node)
builder.add_node("normal_chat", normal_chat_node)
builder.add_node("fetch_metadata", fetch_event_metadata_node)
builder.add_node("metadata_answer", metadata_answer_node)
builder.add_node("document", document_node)
builder.add_node("document_answer", document_answer_node)

builder.set_entry_point("classify")

builder.add_conditional_edges(
    "classify",
    lambda state: state["classification"],
    {
        "NORMAL_CHAT": "normal_chat",
        "EVENT_QUERY": "fetch_metadata"
    }
)

builder.add_edge("fetch_metadata", "metadata_answer")

builder.add_conditional_edges(
    "metadata_answer",
    lambda state: "DOCUMENT" if state["final_answer"] is None else "DONE",
    {
        "DOCUMENT": "document",
        "DONE": END
    }
)

builder.add_edge("document", "document_answer")
builder.add_edge("document_answer", END)

builder.add_edge("normal_chat", END)

graph = builder.compile()


# =============================
# MAIN FUNCTION
# =============================

def ask_agent(question: str, db: Session, conversation: list):
    result = graph.invoke({
        "question": question,
        "db": db,
        "conversation": conversation,
        "classification": None,
        "event_data": None,
        "document_context": None,
        "final_answer": None
    })

    return result["final_answer"]