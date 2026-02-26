# AI/RAG.py
import os
import shutil
from pathlib import Path
from typing import Optional, List
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.messages import HumanMessage, SystemMessage
import sys
import atexit
import re

# Add parent directory to path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# ============================================================
# CONFIGURATION
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BASE_DIR / "uploads"
VECTOR_STORE_DIR = BASE_DIR / "vector_store"
FAISS_INDEX_PATH = VECTOR_STORE_DIR / "faiss_index"

# Create directories
VECTOR_STORE_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)

# Initialize LLM and embeddings
print("🔄 Initializing Ollama...")
llm = ChatOllama(model="mistral", temperature=0.1)
embeddings = OllamaEmbeddings(model="nomic-embed-text")
print("✅ Ollama ready")

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
            print(f"✅ Deleted FAISS index")
        except Exception as e:
            print(f"⚠️ Error deleting: {e}")
    else:
        print("ℹ️ No index to delete")

# Register cleanup
atexit.register(cleanup_vector_store)

# ============================================================
# EXTRACT EVENT ID
# ============================================================
def extract_event_id_from_filename(filename: str) -> int:
    """Extract event_id from filename like '1_2_Seminar.pdf'"""
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
    """Build NEW FAISS index from ALL documents"""
    print("🔨 Building FRESH vector store...")
    
    # Delete old index if exists
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
    
    # Process each PDF
    for pdf_path in pdf_files:
        try:
            event_id = extract_event_id_from_filename(pdf_path.name)
            print(f"  Processing: {pdf_path.name} (event_id: {event_id})")
            
            # Load PDF
            loader = PyPDFLoader(str(pdf_path))
            documents = loader.load()
            
            if not documents:
                continue
            
            # Split into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=300,
                chunk_overlap=30
            )
            chunks = text_splitter.split_documents(documents)
            
            # Add metadata
            for chunk in chunks:
                chunk.metadata["event_id"] = event_id
                chunk.metadata["source"] = pdf_path.name
                chunk.metadata["event_name"] = pdf_path.stem
            
            all_chunks.extend(chunks)
            print(f"    Added {len(chunks)} chunks")
            
        except Exception as e:
            print(f"    ❌ Error: {e}")
    
    if not all_chunks:
        store = FAISS.from_texts(["No content available"], embeddings)
    else:
        print(f"📊 Creating index with {len(all_chunks)} chunks...")
        store = FAISS.from_documents(all_chunks, embeddings)
    
    store.save_local(str(FAISS_INDEX_PATH))
    print(f"✅ Saved with {store.index.ntotal} vectors")
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

# Initialize
print("🚀 Initializing...")
vector_store = get_vector_store()

# ============================================================
# PROCESS NEW DOCUMENT
# ============================================================
def process_event_document(event_id: int, pdf_path: str) -> bool:
    """Add a new document to vector store"""
    try:
        print(f"📄 Adding event {event_id}: {os.path.basename(pdf_path)}")
        
        # Load and split
        loader = PyPDFLoader(pdf_path)
        documents = loader.load()
        
        if not documents:
            return False
        
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=30)
        chunks = text_splitter.split_documents(documents)
        
        # Add metadata
        for chunk in chunks:
            chunk.metadata["event_id"] = event_id
            chunk.metadata["source"] = os.path.basename(pdf_path)
        
        # Add to store
        store = get_vector_store()
        store.add_documents(chunks)
        store.save_local(str(FAISS_INDEX_PATH))
        
        print(f"✅ Added {len(chunks)} chunks")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

# ============================================================
# DELETE EVENT DOCUMENTS - FIX: ADD THIS FUNCTION
# ============================================================
def delete_event_documents(event_id: int) -> bool:
    """Delete all documents for a specific event from vector store"""
    try:
        print(f"🗑️ Deleting documents for event {event_id}")
        
        store = get_vector_store()
        
        # FAISS doesn't support direct deletion, so we need to rebuild without this event
        # Get all documents except those from this event
        all_docs = store.docstore._dict.values()
        
        # Filter out docs from this event
        docs_to_keep = []
        for doc in all_docs:
            if doc.metadata.get("event_id") != event_id:
                docs_to_keep.append(doc)
        
        if len(docs_to_keep) == len(all_docs):
            print(f"ℹ️ No documents found for event {event_id}")
            return True
        
        # Rebuild index with remaining docs
        if docs_to_keep:
            print(f"📊 Rebuilding index with {len(docs_to_keep)} documents...")
            new_store = FAISS.from_documents(docs_to_keep, embeddings)
        else:
            print("📊 No documents left, creating empty store")
            new_store = FAISS.from_texts(["No documents available"], embeddings)
        
        # Save new store
        new_store.save_local(str(FAISS_INDEX_PATH))
        
        # Update global store
        global vector_store
        vector_store = new_store
        
        print(f"✅ Deleted documents for event {event_id}")
        return True
        
    except Exception as e:
        print(f"❌ Error deleting documents: {e}")
        return False

# ============================================================
# SEARCH DOCUMENTS
# ============================================================
def search_documents(query: str, k: int = 5) -> str:
    """Search for relevant documents - returns formatted text"""
    try:
        store = get_vector_store()
        
        if store.index.ntotal <= 1:  # Only placeholder
            return ""
        
        # Search
        docs = store.similarity_search(query, k=k)
        
        if not docs:
            return ""
        
        # Format results nicely
        result = []
        for i, doc in enumerate(docs, 1):
            event_id = doc.metadata.get("event_id", "?")
            source = doc.metadata.get("source", "Unknown")
            content = doc.page_content.strip()
            
            # Clean up content
            content = re.sub(r'\s+', ' ', content)
            
            result.append(f"[DOCUMENT {i} - Event {event_id}]\n{content}\n(Source: {source})")
        
        return "\n\n---\n\n".join(result)
        
    except Exception as e:
        print(f"Search error: {e}")
        return ""

# ============================================================
# REBUILD INDEX
# ============================================================
def rebuild_index():
    """Manually rebuild entire index"""
    global vector_store
    vector_store = build_fresh_vector_store()
    return vector_store