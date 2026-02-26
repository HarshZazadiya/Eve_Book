# ensure_faiss.py
"""
Run this script to ensure FAISS index is built before starting the app
"""
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent))

from AI.RAG import build_faiss_from_all_documents

if __name__ == "__main__":
    print="🚀 Ensuring FAISS index is built..."
    build_faiss_from_all_documents()
    print="✅ FAISS index ready!"