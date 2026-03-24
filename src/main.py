import os
import sys
import atexit
import signal
from fastapi import FastAPI
from redis.asyncio import Redis
from model import Wallets, Users
from database import SessionLocal
from database import engine, Base
from routers.auth import bcrypt_context
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from AI.RAG import get_vector_store, cleanup_vector_store
from AI.graph import init_checkpointer, close_checkpointer
from routers import auth, user, host, chatbot, default, admin

ADMIN_SETUP_KEY = os.getenv("ADMIN_SETUP_KEY", "dev_admin_key")

# Global Redis client
# redis_client = None

# ============================================================
# CLEANUP FUNCTION
# ============================================================
def cleanup():
    """Cleanup resources on shutdown"""
    try:
        cleanup_vector_store()
        print("✅ Cleanup complete")
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")

atexit.register(cleanup)

def signal_handler(sig, frame):
    print(f"\n⚠️ Received signal {sig}")
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ──────────────────────────────────────────────
    print("=" * 50)
    print("🚀 Application starting up...")

    # 1. Initialize FAISS
    print("📚 Initializing vector store...")
    store = get_vector_store()
    print(f"✅ FAISS ready with {store.index.ntotal} vectors")

    # 3. Initialize async Postgres checkpointer
    await init_checkpointer()

    # 4. Create default admin if none exists
    db = SessionLocal()
    try:
        existing_admin = db.query(Users).filter(Users.role == "admin").first()
        existing_wallet = db.query(Wallets).filter(Wallets.owner_type == "admin").first()
        if not existing_wallet and not existing_admin:
            print("⚠️ No admin user found, creating default admin...")
            username = os.getenv("DEFAULT_ADMIN_NAME")
            email    = os.getenv("DEFAULT_ADMIN_EMAIL")
            password = os.getenv("DEFAULT_ADMIN_PASSWORD")

            default_admin = Users(
                username = username,
                email = email,
                hashed_password = bcrypt_context.hash(password),
                role = "admin"
            )
            db.add(default_admin)
            db.commit()
            print(f"✅ Default admin created: {email} / {password}")
            
            # Create admin wallet
            admin_wallet = Wallets(
                owner_type = "admin",
                owner_id = default_admin.id,
                balance = 0
            )
            db.add(admin_wallet)
            db.commit()
            print(f"✅ Default admin wallet created")
        else:
            print("✅ Admin user already exists")

    except Exception as e:
        print(f"⚠️ Error creating admin: {e}")
    finally:
        db.close()

    print("✅ Startup complete")
    print("=" * 50)

    # ── APP RUNS HERE ─────────────────────────────────────────
    yield

    # ── SHUTDOWN ──────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("🛑 Application shutting down...")
    
    # Close Redis connection if it exists
    # if redis_client:
    #     await redis_client.close()
    #     print("🔒 Redis connection closed")
    
    await close_checkpointer()
    cleanup()
    print("=" * 50)


app = FastAPI(lifespan=lifespan)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(user.router)
app.include_router(host.router)
app.include_router(admin.router)
app.include_router(chatbot.router)
app.include_router(default.router)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "vector_store": get_vector_store().index.ntotal > 1
        # "redis_connected": redis_client is not None
    }