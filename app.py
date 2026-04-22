# app.py
# CIPHER AI
# Keeps existing UI + models + DB working
# Adds:
# Login / Signup / Logout
# Sessions
# User based chat persistence
# Sidebar history APIs
# Rename/Delete chat APIs

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from sqlalchemy import (
    create_engine, Column, Integer, String,
    Text, DateTime
)
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime

from passlib.context import CryptContext

import requests
import os

# =====================================================
# CONFIG
# =====================================================

DATABASE_URL = os.getenv("DATABASE_URL")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

SECRET_KEY = os.getenv("SECRET_KEY", "cipher-secret-key")

# =====================================================
# APP
# =====================================================

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

app.mount("/static", StaticFiles(directory="static"), name="static")

# =====================================================
# DB
# =====================================================

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# =====================================================
# PASSWORD HASHING
# =====================================================

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

# =====================================================
# MODELS
# =====================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100))
    email = Column(String(200), unique=True)
    password_hash = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)


class Chat(Base):
    __tablename__ = "chats"

    id = Column(String, primary_key=True)
    user_id = Column(Integer)
    title = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String)
    role = Column(String(20))
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)

# =====================================================
# GROQ
# =====================================================

try:
    from groq import Groq
    groq_client = Groq(api_key=GROQ_API_KEY)
except:
    groq_client = None

# =====================================================
# HELPERS
# =====================================================

def hash_password(password):
    return pwd_context.hash(password)


def verify_password(password, hashed):
    return pwd_context.verify(password, hashed)


def get_user_id(request: Request):
    return request.session.get("user_id")


def get_user_name(request: Request):
    return request.session.get("user_name")


# =====================================================
# AI CALLS
# =====================================================

def call_openrouter(model, prompt):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ]
            },
            timeout=60
        )

        data = r.json()

        if "choices" not in data:
            return "No response."

        return data["choices"][0]["message"]["content"]

    except Exception:
        return "Provider unavailable."


def call_groq(prompt):
    try:
        if not groq_client:
            return "Groq not configured."

        res = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        return res.choices[0].message.content

    except Exception:
        return "Groq unavailable."


# =====================================================
# MODE SWITCH
# =====================================================

def get_reply(message, mode):

    mode = (mode or "thinking").lower()

    if mode == "thinking":
        return {
            "label": "🧠 THINK · GPT",
            "reply": call_openrouter(
                "openai/gpt-4o-mini",
                message
            )
        }

    elif mode == "fast":
        return {
            "label": "⚡ FAST · GROQ",
            "reply": call_groq(message)
        }

    elif mode == "code":
        return {
            "label": "💻 CODE · CLAUDE",
            "reply": call_openrouter(
                "anthropic/claude-3-haiku",
                message
            )
        }

    return {
        "label": "🧠 THINK · GPT",
        "reply": call_openrouter(
            "openai/gpt-4o-mini",
            message
        )
    }

# =====================================================
# HOME
# =====================================================

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    with open("templates/index.html", "r", encoding="utf-8") as f:
        html = f.read()

    return HTMLResponse(html)

# =====================================================
# SIGNUP
# =====================================================

@app.post("/signup")
async def signup(request: Request):

    data = await request.json()

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()

    if not name or not email or not password:
        return JSONResponse({"ok": False, "msg": "All fields required."})

    db = SessionLocal()

    existing = db.query(User).filter(User.email == email).first()

    if existing:
        db.close()
        return JSONResponse({"ok": False, "msg": "Email already exists."})

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password)
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    request.session["user_id"] = user.id
    request.session["user_name"] = user.name

    db.close()

    return JSONResponse({"ok": True})

# =====================================================
# LOGIN
# =====================================================

@app.post("/login")
async def login(request: Request):

    data = await request.json()

    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()

    db = SessionLocal()

    user = db.query(User).filter(User.email == email).first()

    if not user:
        db.close()
        return JSONResponse({"ok": False, "msg": "Invalid credentials."})

    if not verify_password(password, user.password_hash):
        db.close()
        return JSONResponse({"ok": False, "msg": "Invalid credentials."})

    request.session["user_id"] = user.id
    request.session["user_name"] = user.name

    db.close()

    return JSONResponse({"ok": True})

# =====================================================
# LOGOUT
# =====================================================

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/")

# =====================================================
# SESSION CHECK
# =====================================================

@app.get("/me")
def me(request: Request):

    uid = get_user_id(request)

    if not uid:
        return JSONResponse({"logged_in": False})

    return JSONResponse({
        "logged_in": True,
        "name": get_user_name(request)
    })

# =====================================================
# CHAT HISTORY
# =====================================================

@app.get("/history")
def history(request: Request):

    uid = get_user_id(request)

    if not uid:
        return JSONResponse([])

    db = SessionLocal()

    chats = (
        db.query(Chat)
        .filter(Chat.user_id == uid)
        .order_by(Chat.created_at.desc())
        .all()
    )

    data = []

    for c in chats:
        data.append({
            "id": c.id,
            "title": c.title
        })

    db.close()

    return JSONResponse(data)

# =====================================================
# LOAD CHAT
# =====================================================

@app.get("/chat/{chat_id}")
def load_chat(chat_id: str, request: Request):

    uid = get_user_id(request)

    if not uid:
        return JSONResponse([])

    db = SessionLocal()

    chat = (
        db.query(Chat)
        .filter(Chat.id == chat_id, Chat.user_id == uid)
        .first()
    )

    if not chat:
        db.close()
        return JSONResponse([])

    msgs = (
        db.query(Message)
        .filter(Message.chat_id == chat_id)
        .order_by(Message.id.asc())
        .all()
    )

    data = []

    for m in msgs:
        data.append({
            "role": m.role,
            "content": m.content
        })

    db.close()

    return JSONResponse(data)

# =====================================================
# DELETE CHAT
# =====================================================

@app.delete("/chat/{chat_id}")
def delete_chat(chat_id: str, request: Request):

    uid = get_user_id(request)

    if not uid:
        return JSONResponse({"ok": False})

    db = SessionLocal()

    db.query(Message).filter(
        Message.chat_id == chat_id
    ).delete()

    db.query(Chat).filter(
        Chat.id == chat_id,
        Chat.user_id == uid
    ).delete()

    db.commit()
    db.close()

    return JSONResponse({"ok": True})

# =====================================================
# RENAME CHAT
# =====================================================

@app.post("/rename-chat")
async def rename_chat(request: Request):

    uid = get_user_id(request)

    if not uid:
        return JSONResponse({"ok": False})

    data = await request.json()

    chat_id = data.get("chat_id")
    title = data.get("title", "").strip()

    db = SessionLocal()

    chat = db.query(Chat).filter(
        Chat.id == chat_id,
        Chat.user_id == uid
    ).first()

    if chat:
        chat.title = title
        db.commit()

    db.close()

    return JSONResponse({"ok": True})

# =====================================================
# MAIN CHAT
# =====================================================

@app.post("/chat")
async def chat(request: Request):

    uid = get_user_id(request)

    if not uid:
        return JSONResponse({
            "response": "Please login first."
        })

    data = await request.json()

    message = data.get("message", "").strip()
    mode = data.get("mode", "thinking")
    chat_id = data.get("chat_id")

    if not message:
        return JSONResponse({
            "response": "Empty message."
        })

    db = SessionLocal()

    existing = db.query(Chat).filter(
        Chat.id == chat_id,
        Chat.user_id == uid
    ).first()

    if not existing:
        db.add(Chat(
            id=chat_id,
            user_id=uid,
            title=message[:40]
        ))
        db.commit()

    db.add(Message(
        chat_id=chat_id,
        role="user",
        content=message
    ))
    db.commit()

    result = get_reply(message, mode)

    db.add(Message(
        chat_id=chat_id,
        role="assistant",
        content=result["reply"]
    ))
    db.commit()

    db.close()

    return JSONResponse({
        "response": result["reply"],
        "label": result["label"]
    })
