import os
import shutil
from pathlib import Path
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.tools import tool
from dotenv import load_dotenv
# ============================================================
# CONFIGURATION
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
VECTOR_STORE_DIR = BASE_DIR / "vector_store"
FAISS_INDEX_PATH = VECTOR_STORE_DIR / "faiss_index"

VECTOR_STORE_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

# ============================================================
# LLM - Kimi K2 via Groq (~1T MoE, best tool calling, 300K/day free)
# ============================================================

print("🔄 Initializing Kimi K2 via Groq...")
llm = ChatGroq(
    # model = "moonshotai/kimi-k2-instruct",
    model = "llama-3.3-70b-versatile",
    temperature = 0,
    max_tokens = 2048,
    groq_api_key = os.getenv("GROQ_API_KEY")
)

# ============================================================
# EMBEDDINGS - HuggingFace (runs on server, no API limits)
# ============================================================
print("🔄 Initializing HuggingFace Embeddings...")
embeddings = HuggingFaceEmbeddings(
    model_name = "sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs = {"device": "cpu"},
    encode_kwargs = {"normalize_embeddings": True}
)
print("✅ LLM and Embeddings ready")

# Global vector store
vector_store = None

# ============================================================
# CLEANUP
# ============================================================
def cleanup_vector_store():
    """Delete FAISS index when app closes"""
    print("\n🧹 Cleaning up vector store...")
    if FAISS_INDEX_PATH.exists():
        try:
            shutil.rmtree(FAISS_INDEX_PATH)
            print("✅ Deleted FAISS index")
        except Exception as e:
            print(f"⚠️ Error deleting: {e}")

# ============================================================
# EXTRACT EVENT ID FROM FILENAME
# ============================================================
def extract_event_id_from_filename(filename: str) -> int:
    """Extract event_id from filename (format: hostId_eventId_name.pdf)"""
    try:
        parts = Path(filename).stem.split('_')
        if len(parts) >= 2:
            return int(parts[1])
    except:
        pass
    return 0

# ============================================================
# BUILD FRESH VECTOR STORE
# ============================================================
def build_fresh_vector_store():
    """Build NEW FAISS index from ALL documents on app start"""
    print("🔨 Building FRESH vector store from all documents...")

    if FAISS_INDEX_PATH.exists():
        shutil.rmtree(FAISS_INDEX_PATH)

    all_chunks = []
    pdf_files = list(UPLOAD_DIR.glob("*.pdf"))
    print(f"📄 Found {len(pdf_files)} PDF files")

    if not pdf_files:
        print("⚠️ No PDFs found, creating empty store")
        store = FAISS.from_texts(["No documents available"], embeddings)
        store.save_local(str(FAISS_INDEX_PATH))
        return store

    for pdf_path in pdf_files:
        try:
            event_id = extract_event_id_from_filename(pdf_path.name)
            print(f"  Processing: {pdf_path.name} (event_id: {event_id})")

            loader = PyPDFLoader(str(pdf_path))
            documents = loader.load()

            if not documents:
                continue

            text_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=30)
            chunks = text_splitter.split_documents(documents)

            for chunk in chunks:
                chunk.metadata["event_id"] = event_id
                chunk.metadata["source"] = pdf_path.name

            all_chunks.extend(chunks)
            print(f"    Added {len(chunks)} chunks")

        except Exception as e:
            print(f"    ❌ Error processing {pdf_path.name}: {e}")

    if not all_chunks:
        store = FAISS.from_texts(["No content available"], embeddings)
    else:
        print(f"📊 Creating index with {len(all_chunks)} chunks...")
        store = FAISS.from_documents(all_chunks, embeddings)

    store.save_local(str(FAISS_INDEX_PATH))
    print(f"✅ Saved vector store with {store.index.ntotal} vectors")
    return store

# ============================================================
# GET VECTOR STORE
# ============================================================
def get_vector_store():
    """Get vector store - builds fresh if needed"""
    global vector_store

    if not FAISS_INDEX_PATH.exists():
        vector_store = build_fresh_vector_store()
        return vector_store

    try:
        vector_store = FAISS.load_local(
            str(FAISS_INDEX_PATH),
            embeddings,
            allow_dangerous_deserialization=True
        )
        return vector_store
    except:
        vector_store = build_fresh_vector_store()
        return vector_store

# ============================================================
# ADD DOCUMENT TO VECTOR STORE
# ============================================================
def add_document_to_store(event_id: int, pdf_path: str) -> bool:
    """Add a new document to vector store (called when host uploads)"""
    try:
        print(f"📄 Adding document for event {event_id}: {os.path.basename(pdf_path)}")

        loader = PyPDFLoader(pdf_path)
        documents = loader.load()

        if not documents:
            return False

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=30)
        chunks = text_splitter.split_documents(documents)

        for chunk in chunks:
            chunk.metadata["event_id"] = event_id
            chunk.metadata["source"] = os.path.basename(pdf_path)

        store = get_vector_store()
        store.add_documents(chunks)
        store.save_local(str(FAISS_INDEX_PATH))

        print(f"✅ Added {len(chunks)} chunks for event {event_id}")
        return True

    except Exception as e:
        print(f"❌ Error adding document: {e}")
        return False

# ============================================================
# DELETE DOCUMENTS FROM VECTOR STORE
# ============================================================
def delete_event_documents(event_id: int) -> bool:
    """Delete all documents for a specific event from vector store"""
    try:
        print(f"🗑️ Deleting documents for event {event_id}")

        store = get_vector_store()
        all_docs = list(store.docstore._dict.values())

        docs_to_keep = []
        docs_deleted = 0

        for doc in all_docs:
            if doc.metadata.get("event_id") != event_id:
                docs_to_keep.append(doc)
            else:
                docs_deleted += 1

        if docs_deleted == 0:
            print(f"ℹ️ No documents found for event {event_id}")
            return True

        if docs_to_keep:
            new_store = FAISS.from_documents(docs_to_keep, embeddings)
        else:
            new_store = FAISS.from_texts(["No documents available"], embeddings)

        new_store.save_local(str(FAISS_INDEX_PATH))

        global vector_store
        vector_store = new_store

        print(f"✅ Deleted {docs_deleted} chunks for event {event_id}")
        return True

    except Exception as e:
        print(f"❌ Error deleting documents: {e}")
        return False

# ============================================================
# SEARCH DOCUMENTS (for RAG)
# ============================================================
@tool
def search_documents(query: str, k: int = 3) -> str:
    """Search for relevant documents and return formatted results
    - Use this tool to search for relevant documents in the vector store
    - IF user asks about something related to event which is not from this fields
        [ EVENT ID, NAME/TITLE, DATE, PRICE, LOCATION/VENUE, TOTAL SEATS, AVAILABLE SEATS ]
        THEN use this tool to search for relevant documents
    ARGS :
        query (str) : Query to search for
        k (int) : Number of results to return

    RETURNS :
        Formatted results
    """
    try:
        store = get_vector_store()

        if store.index.ntotal <= 1:
            return ""

        docs = store.similarity_search(query, k=k)

        if not docs:
            return ""

        result = []
        for i, doc in enumerate(docs, 1):
            event_id = doc.metadata.get("event_id", "Unknown")
            source = doc.metadata.get("source", "Unknown")
            content = doc.page_content.strip()
            result.append(
                f"[Document {i} - Event {event_id}]\n"
                f"{content}\n"
                f"(Source: {source})"
            )

        return "\n\n---\n\n".join(result)

    except Exception as e:
        print(f"Search error: {e}")
        return ""

rag_tools = [search_documents]

# Alias for FAISS_ensure.py
def build_faiss_from_all_documents():
    return build_fresh_vector_store()