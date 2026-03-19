from sqlalchemy import text
from AI.RAG import embeddings
from database import SessionLocal


def search_memory(user_id: int, user_role: str, query: str, top_k: int = 2):
    """
    Search for relevant memories using vector similarity
    
    Args:
        user_id: ID of the user
        user_role: Role of the user (user/host/admin)
        query: Search query text
        top_k: Number of results to return
    
    Returns:
        List of relevant memories with key, value, type
    """
    db = SessionLocal()

    try:
        # Get query embedding using LangChain's method
        query_embedding = embeddings.embed_query(query)
        
        # For pgvector, we need to format the embedding as a string
        # pgvector expects format like '[0.1, 0.2, 0.3]'
        embedding_str = '[' + ','.join(str(x) for x in query_embedding) + ']'

        # Use cosine distance (<->) for similarity search
        result = db.execute(text("""
            SELECT key, value, type
            FROM memories
            WHERE user_id = :user_id
              AND user_role = :user_role
            ORDER BY embedding <-> :embedding
            LIMIT :top_k
        """), {
            "user_id": user_id,
            "user_role": user_role,
            "embedding": embedding_str,
            "top_k": top_k
        })

        memories = []
        for row in result:
            memories.append({
                "key": row.key,
                "value": row.value,
                "type": row.type
            })
        
        if memories:
            print(f"✅ Found {len(memories)} relevant memories")
        else:
            print("ℹ️ No relevant memories found")
        
        return memories

    except Exception as e:
        print(f"❌ Error searching memories: {e}")
        return []
    finally:
        db.close()


def store_memory(user_id: int, user_role: str, memory_type: str, key: str, value: str):
    """
    Store a new memory with embedding
    
    Args:
        user_id: ID of the user
        user_role: Role of the user
        memory_type: Type of memory (preference, fact, etc.)
        key: Memory key/identifier
        value: Memory value/content
    """
    from model import Memories
    
    db = SessionLocal()
    
    try:
        # Generate embedding for the memory value
        embedding = embeddings.embed_query(value)
        
        # Create new memory
        memory = Memories(
            user_id=user_id,
            user_role=user_role,
            type=memory_type,
            key=key,
            value=value,
            embedding=embedding
        )
        
        db.add(memory)
        db.commit()
        print(f"✅ Stored memory: {key} = {value[:50]}...")
        return True
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error storing memory: {e}")
        return False
    finally:
        db.close()


def delete_memory(user_id: int, user_role: str, key: str):
    """
    Delete a specific memory by key
    
    Args:
        user_id: ID of the user
        user_role: Role of the user
        key: Memory key to delete
    """
    from model import Memories
    
    db = SessionLocal()
    
    try:
        result = db.query(Memories).filter(
            Memories.user_id == user_id,
            Memories.user_role == user_role,
            Memories.key == key
        ).delete()
        
        db.commit()
        
        if result:
            print(f"✅ Deleted memory: {key}")
        else:
            print(f"ℹ️ No memory found with key: {key}")
        
        return result > 0
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error deleting memory: {e}")
        return False
    finally:
        db.close()