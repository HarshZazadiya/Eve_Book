import json

from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated, List
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from AI.graph import run_agent
from database import SessionLocal
from model import Wallets
import os
from routers.host import PaymentRequest
from sqlalchemy.orm import Session
from pydantic import BaseModel
from redis.asyncio import Redis

router = APIRouter(
        prefix = "/default", 
        tags = ["default"]
    )

# ── CONFIGURATION ─────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_bearer = OAuth2PasswordBearer(tokenUrl="/auth/token")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]

# redis 
REDIS_URL = os.getenv("REDIS_URL")
if REDIS_URL:
    try:
        # Try to create Redis client with timeout
        test_client = Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
            
        # Test the connection - THIS IS NOW INSIDE AN ASYNC FUNCTION
        test_client.ping()
        redis_client = test_client
        print(f"✅ Redis connected successfully to {REDIS_URL}")
    except Exception as e:
        print(f"⚠️ Redis connection failed: {e}")
        print("⚠️ Redis caching disabled - wallet will still work")
        redis_client = None
else:
    print("⚠️ REDIS_URL not set, Redis caching disabled")
    redis_client = None

@router.post("/topUp")
async def top_up_wallet(db : db_dependency, payment_request : PaymentRequest, token : Annotated[str, Depends(oauth2_bearer)]):
    """Add money to wallet"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        owner_type = payload.get("type")
        owner_id   = payload.get("id")
        owner_role = payload.get("role")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    wallet = db.query(Wallets).filter(Wallets.owner_type == owner_role, Wallets.owner_id   == owner_id).first()

    if wallet:
        wallet.balance += payment_request.amount
    else:
        wallet = Wallets(
            owner_type = owner_type,
            owner_id = owner_id,
            balance = payment_request.amount
        )
        db.add(wallet)

    db.commit()
    db.refresh(wallet)

    # Safely handle Redis operations
    if redis_client:
        try:
            await redis_client.delete(f"wallet:{owner_type} : {owner_id}")
            print(f"✅ Redis cache cleared for {owner_type} : {owner_id}")
        except Exception as e:
            print(f"⚠️ Redis cache clear failed (non-critical) : {e}")
            # Don't fail the request - Redis is optional

    return {
        "owner_type" : owner_type,
        "balance" : wallet.balance,
        "message" : "Wallet topped up successfully"
    }


@router.get("/myWallet")
async def get_my_wallet(db : db_dependency, token : Annotated[str, Depends(oauth2_bearer)]):
    """Get current wallet balance"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms = [ALGORITHM])
        owner_type = payload.get("type")
        owner_id   = payload.get("id")
        owner_role = payload.get("role")
    except JWTError:
        raise HTTPException(status_code = 401, detail = "Invalid token")

    if owner_type not in ("user", "host") or owner_id is None:
        raise HTTPException(status_code = 401, detail = "Invalid token payload")

    wallet = db.query(Wallets).filter(Wallets.owner_type == owner_role, Wallets.owner_id == owner_id).first()

    if not wallet:
        raise HTTPException(status_code = 404, detail = "Wallet not found")

    response = {"balance" : float(wallet.balance)}

    if owner_type == "host" and wallet.balance < 500:
        response["warning"] = "Low balance - need ₹500 to create events"

    return response
