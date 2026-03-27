import os
import asyncio
from typing import Annotated
from pydantic import BaseModel
from jose import jwt, JWTError
from database import SessionLocal
from sqlalchemy.orm import Session
from model import Users, Hosts, Wallets
from passlib.context import CryptContext
from datetime import timedelta, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from AI.tools.workflows.workflow import workflow_request_sync
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer

router = APIRouter(
    prefix = "/auth",
    tags = ["Auth"],
)

header_secret = os.getenv("HEADER_SECRET")

class Token(BaseModel):
    access_token : str
    token_type : str


class CreateUserRequest(BaseModel):
    username : str
    email : str
    password : str


class CreateHostRequest(BaseModel):
    company_name : str
    email : str
    password : str

SECRET_KEY = os.getenv("SECRET_KEY")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

bcrypt_context = CryptContext(schemes = ["bcrypt"], deprecated = "auto")
oauth2_bearer = OAuth2PasswordBearer(tokenUrl = "/auth/token")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

db_dependency = Annotated[Session, Depends(get_db)]

def authenticate_user(username: str, password: str, db: Session):
    user = db.query(Users).filter(Users.username == username).first()
    if not user or user.role == "host":
        return None
    if not bcrypt_context.verify(password, user.hashed_password):
        return None
    return user


def authenticate_host(email: str, password: str, db: Session):
    host = db.query(Hosts).filter(Hosts.email == email).first()
    if not host:
        return None
    if not bcrypt_context.verify(password, host.hashed_password):
        return None
    return host


def create_access_token(entity_id: int, entity_type: str, role: str):
    payload = {
        "id": entity_id,
        "type": entity_type,
        "role": role,
        "exp" : datetime.now(timezone.utc)
        + timedelta(minutes = ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm = ALGORITHM)

async def get_current_user(token: Annotated[str, Depends(oauth2_bearer)], db: db_dependency,):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms = [ALGORITHM])
        if payload.get("type") != "user":
            raise HTTPException(status_code = 403, detail = "User access only")

        user = db.query(Users).filter(Users.id == payload.get("id")).first()
        if not user:
            raise HTTPException(status_code = 401, detail = "Invalid token")

        return user

    except JWTError:
        raise HTTPException(status_code = 401, detail = "Invalid token")


async def get_current_host(token: Annotated[str, Depends(oauth2_bearer)], db: db_dependency,):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "host":
            raise HTTPException(status_code = 403, detail="Host access only")

        host = db.query(Hosts).filter(Hosts.id == payload.get("id")).first()
        if not host:
            raise HTTPException(status_code = 401, detail = "Invalid token")

        return host

    except JWTError:
        raise HTTPException(status_code = 401, detail = "Invalid token")


@router.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends(),db: Session = Depends(get_db)):
    user = authenticate_user(form_data.username, form_data.password, db)
    if user:
        return {
            "access_token": create_access_token(user.id, "user", user.role),
            "token_type": "bearer",
            "type": "user",
            "id" : user.id,
            "role" : user.role,
            "name" : user.username
        }

    host = authenticate_host(form_data.username, form_data.password, db)
    if host:
        return {
            "access_token": create_access_token(host.id, "host", "host"),
            "token_type": "bearer",
            "type": "host",
            "id" : host.id,
            "role" : "host",
            "name" : host.company_name
        }

    
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.post("/user", status_code=201)
async def create_user(request: CreateUserRequest,db: db_dependency):
    user = Users(
        username = request.username,
        email = request.email,
        hashed_password = bcrypt_context.hash(request.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    wallet = Wallets(
        owner_id = user.id,
        owner_type = user.role,
        balance = 0 
    )
    db.add(wallet)
    db.commit()
    db.refresh(wallet)

    data = {
        "id" : user.id,
        "username" : user.username,
        "email" : user.email,
        "role" : user.role
    }
    
    workflow_request_sync(data, "http://n8n:5678/webhook/new", "POST")
    return {"id": user.id, "username": user.username}

@router.post("/host", status_code = 201)
async def create_host(request: CreateHostRequest,db: db_dependency):
    host = Hosts(
        company_name = request.company_name,
        email = request.email,
        hashed_password = bcrypt_context.hash(request.password),
    )
    db.add(host)
    db.commit()
    db.refresh(host)

    wallet = Wallets(
        owner_id = host.id,
        owner_type = "host",
        balance = 0 
    )
    db.add(wallet)
    db.commit() 
    db.refresh(wallet)

    data = {
        "id" : host.id,
        "company_name" : host.company_name,
        "email" : host.email,
        "role" : "host"
    }
    workflow_request_sync(data, "http://n8n:5678/webhook/new", "POST")
    return {"id": host.id, "company_name": host.company_name}

@router.get("/me")
async def get_me(token: Annotated[str, Depends(oauth2_bearer)],db: db_dependency):
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return {"id": payload["id"], "type": payload["type"], "role": payload["role"]}  