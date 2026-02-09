import token
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from database import engine
from database import Base
from routers import auth, user, host
from model import Wallets, Events, Bookings
from routers.host import host_dependency, db_dependency, PaymentRequest
from routers.auth import get_current_user, get_current_host
from jose import jwt, JWTError
from typing import Annotated
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from fastapi.responses import HTMLResponse
from database import SessionLocal
from pathlib import Path
from redis.asyncio import Redis
import json
from routers import admin
import os
from contextlib import asynccontextmanager
from model import Users
from routers.auth import bcrypt_context


ADMIN_SETUP_KEY = os.getenv("ADMIN_SETUP_KEY", "dev_admin_key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()

    admin = db.query(Users).filter(Users.role == "admin").first()

    username = os.getenv("DEFAULT_ADMIN_NAME", "admin")
    email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@event.com")
    password = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")

    if not admin:
        default_admin = Users(
            username=username,
            email=email,
            hashed_password=bcrypt_context.hash(password),
            role="admin"
        )

        db.add(default_admin)
        db.commit()

        print("✅ Default admin created -> admin@event.com / admin123")

    db.close()

    yield

    print("App shutting down")


app = FastAPI(lifespan=lifespan)


Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(user.router)
app.include_router(host.router)
app.include_router(admin.router)

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_bearer = OAuth2PasswordBearer(tokenUrl="/auth/token")

REDIS_URL = os.getenv("REDIS_URL")
redis_client = Redis.from_url(REDIS_URL, decode_responses=True) if REDIS_URL else None

@app.post("/topUp")
async def top_up_wallet(db: db_dependency, payment_request: PaymentRequest, token: Annotated[str, Depends(oauth2_bearer)]):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        owner_type = payload.get("type")
        owner_id = payload.get("id")

    except JWTError:
        raise HTTPException(status_code = 401, detail = "Invalid token")

    wallet = db.query(Wallets).filter(Wallets.owner_type == owner_type, Wallets.owner_id == owner_id).first()

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

    if redis_client:
        await redis_client.delete(f"wallet:{owner_type}:{owner_id}")

    return {
        "owner_type": owner_type,
        "wallet_balance": wallet.balance,
        "message": "Wallet topped up successfully"
    }


@app.get("/myWallet")
async def get_my_wallet(db: db_dependency, token: Annotated[str, Depends(oauth2_bearer)]):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        owner_type = payload.get("type")
        owner_id = payload.get("id")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    if owner_type not in ("user", "host") or owner_id is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    wallet = db.query(Wallets).filter(Wallets.owner_type == owner_type, Wallets.owner_id == owner_id).first()

    if not wallet:
        raise HTTPException(status_code=404, detail="Wallet not found")
    if owner_type == "host" and wallet.balance < 500:
        data = {
            "balance": wallet.balance,
            "message": "Insufficient wallet balance. Please top up or host rights may be revoked."
        }
    data = {"balance": float(wallet.balance)}
    return data
