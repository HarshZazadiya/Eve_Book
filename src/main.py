from fastapi import FastAPI, Depends, HTTPException
from database import engine
from database import Base
from routers import auth, user, host
from model import Wallets
from routers.host import db_dependency, PaymentRequest
from jose import jwt, JWTError
from typing import Annotated
from fastapi.security import OAuth2PasswordBearer
from database import SessionLocal
from redis.asyncio import Redis
from routers import admin
import os
from contextlib import asynccontextmanager
from model import Users
from routers.auth import bcrypt_context
from fastapi.staticfiles import StaticFiles
from AI import chatbot
from AI.RAG import get_vector_store, cleanup_vector_store
import atexit
import signal
import sys


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

ADMIN_SETUP_KEY = os.getenv("ADMIN_SETUP_KEY", "dev_admin_key")

# ============================================================
# CLEANUP FUNCTION
# ============================================================
def cleanup():
    """Cleanup resources on shutdown"""
    print("\n🧹 Cleaning up...")
    try:
        cleanup_vector_store()
        print("✅ Cleanup complete")
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")

# Register cleanup for normal exit
atexit.register(cleanup)

# Handle signals for forced shutdown
def signal_handler(sig, frame):
    print(f"\n⚠️ Received signal {sig}")
    cleanup()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    print("=" * 50)
    print("🚀 Application starting up...")
    
    # 1. Initialize FAISS
    print("📚 Initializing vector store...")
    store = get_vector_store()
    print(f"✅ FAISS ready with {store.index.ntotal} vectors")
    
    # 2. Create default admin if none exists
    db = SessionLocal()
    try:
        admin = db.query(Users).filter(Users.role == "admin").first()
        
        if not admin:
            username = os.getenv("DEFAULT_ADMIN_NAME", "admin")
            email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@event.com")
            password = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
            
            default_admin = Users(
                username=username,
                email=email,
                hashed_password=bcrypt_context.hash(password),
                role="admin"
            )
            db.add(default_admin)
            db.commit()
            print(f"✅ Default admin created: {email} / {password}")
        else:
            print("✅ Admin user already exists")
            
    except Exception as e:
        print(f"⚠️ Error creating admin: {e}")
    finally:
        db.close()
    
    print("✅ Startup complete")
    print("=" * 50)
    
    # APP RUNS HERE
    yield
    
    # SHUTDOWN
    print("\n" + "=" * 50)
    print("🛑 Application shutting down...")
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

# CONFIGURATION
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_bearer = OAuth2PasswordBearer(tokenUrl="/auth/token")

REDIS_URL = os.getenv("REDIS_URL")
redis_client = Redis.from_url(REDIS_URL, decode_responses=True) if REDIS_URL else None


@app.post("/topUp")
async def top_up_wallet(db: db_dependency,  payment_request: PaymentRequest,  token: Annotated[str, Depends(oauth2_bearer)]):
    """Add money to wallet"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        owner_type = payload.get("type")
        owner_id = payload.get("id")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Get or create wallet
    wallet = db.query(Wallets).filter(Wallets.owner_type == owner_type,  Wallets.owner_id == owner_id).first()

    if wallet:
        wallet.balance += payment_request.amount
    else:
        wallet = Wallets(
            owner_type=owner_type,
            owner_id=owner_id,
            balance=payment_request.amount
        )
        db.add(wallet)

    db.commit()
    db.refresh(wallet)

    # Clear cache
    if redis_client:
        await redis_client.delete(f"wallet:{owner_type}:{owner_id}")

    return {
        "owner_type": owner_type,
        "balance": wallet.balance,
        "message": "Wallet topped up successfully"
    }


@app.get("/myWallet")
async def get_my_wallet(db: db_dependency,  token: Annotated[str, Depends(oauth2_bearer)]):
    """Get current wallet balance"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        owner_type = payload.get("type")
        owner_id = payload.get("id")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if owner_type not in ("user", "host") or owner_id is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    wallet = db.query(Wallets).filter(Wallets.owner_type == owner_type,  Wallets.owner_id == owner_id).first()

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    
    response = {"balance": float(wallet.balance)}
    
    # Add warning for low balance hosts
    if owner_type == "host" and wallet.balance < 500:
        response["warning"] = "Low balance - need ₹500 to create events"
    
    return response


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "vector_store": get_vector_store().index.ntotal > 1
    }