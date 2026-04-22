# ==========================================================
# app.py (UPDATED - Phase 1 Tool Fusion)
# Existing Chat + Login + History preserved
# Added:
# Hash Tool
# Base64 Tool
# Password Checker
# JWT Decoder
# WHOIS Lookup
# DNS Lookup
# ==========================================================

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker

from groq import Groq
import requests
import os
import uuid
import hashlib
import base64
import jwt
import whois
import dns.resolver
import re
import json

# ==========================================================
# CONFIG
# ==========================================================

DATABASE_URL = os.getenv("DATABASE_URL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
APP_SECRET = os.getenv("APP_SECRET", "cipher_secret_key")

# ==========================================================
# APP
# ==========================================================

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=APP_SECRET)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ==========================================================
# DB
# ==========================================================

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ==========================================================
# TABLES
# ==========================================================

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(255), unique=True)
    password = Column(String(255))

class Chat(Base):
    __tablename__ = "chats"
    id = Column(String(255), primary_key=True)
    title = Column(String(255))
    user_id = Column(Integer)

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    chat_id = Column(String(255))
    role = Column(String(50))
    content = Column(Text)

Base.metadata.create_all(bind=engine)

# ==========================================================
# AI CLIENTS
# ==========================================================

groq_client = Groq(api_key=GROQ_API_KEY)

# ==========================================================
# HELPERS
# ==========================================================

def get_user_id(request):
    return request.session.get("user_id")

def ask_groq(prompt):
    try:
        res = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":prompt}]
        )
        return res.choices[0].message.content
    except Exception as e:
        return f"GROQ Error: {str(e)}"

def ask_openrouter(prompt, model):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [{"role":"user","content":prompt}]
            },
            timeout=60
        )
        data = r.json()

        if "choices" in data:
            return data["choices"][0]["message"]["content"]

        return str(data)

    except Exception as e:
        return f"AI Error: {str(e)}"

# ==========================================================
# HOME
# ==========================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )

# ==========================================================
# AUTH
# ==========================================================

@app.post("/signup")
async def signup(request: Request):
    try:
        data = await request.json()

        email = data["email"].strip().lower()
        password = data["password"].strip()

        db = SessionLocal()

        old = db.query(User).filter(User.username == email).first()

        if old:
            db.close()
            return {"ok":False,"msg":"User already exists"}

        user = User(username=email,password=password)
        db.add(user)
        db.commit()
        db.refresh(user)

        request.session["user_id"] = user.id
        request.session["email"] = user.username

        db.close()
        return {"ok":True}

    except Exception as e:
        return {"ok":False,"msg":str(e)}

@app.post("/login")
async def login(request: Request):
    try:
        data = await request.json()

        email = data["email"].strip().lower()
        password = data["password"].strip()

        db = SessionLocal()

        user = db.query(User).filter(
            User.username == email,
            User.password == password
        ).first()

        db.close()

        if not user:
            return {"ok":False,"msg":"Invalid credentials"}

        request.session["user_id"] = user.id
        request.session["email"] = user.username

        return {"ok":True}

    except Exception as e:
        return {"ok":False,"msg":str(e)}

@app.get("/me")
async def me(request: Request):
    uid = get_user_id(request)

    if uid:
        return {
            "logged_in":True,
            "email":request.session.get("email")
        }

    return {"logged_in":False}

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"ok":True}

# ==========================================================
# CHAT
# ==========================================================

@app.post("/chat")
async def chat(request: Request):

    try:
        data = await request.json()

        prompt = data["message"]
        mode = data["mode"]
        chat_id = data.get("chat_id")

        if not chat_id:
            chat_id = "chat_" + str(uuid.uuid4())[:8]

        uid = get_user_id(request)

        if mode == "thinking":
            answer = ask_openrouter(prompt, "openai/gpt-4o-mini")
            label = "🧠 THINK • GPT"

        elif mode == "code":
            answer = ask_openrouter(prompt, "anthropic/claude-3-haiku")
            label = "💻 CODE • CLAUDE"

        else:
            answer = ask_groq(prompt)
            label = "⚡ FAST • GROQ"

        if uid:
            db = SessionLocal()

            exists = db.query(Chat).filter(Chat.id == chat_id).first()

            if not exists:
                db.add(Chat(
                    id=chat_id,
                    title=prompt[:40],
                    user_id=uid
                ))

            db.add(Message(chat_id=chat_id, role="user", content=prompt))
            db.add(Message(chat_id=chat_id, role="assistant", content=answer))

            db.commit()
            db.close()

        return {
            "ok":True,
            "chat_id":chat_id,
            "label":label,
            "response":answer
        }

    except Exception as e:
        return {"ok":False,"msg":str(e)}

# ==========================================================
# HISTORY
# ==========================================================

@app.get("/history")
async def history(request: Request):

    uid = get_user_id(request)

    if not uid:
        return {"items":[]}

    db = SessionLocal()

    chats = db.query(Chat).filter(Chat.user_id == uid).all()

    result = []

    for c in chats:
        result.append({
            "id":c.id,
            "title":c.title
        })

    db.close()
    return {"items":result}

@app.get("/chat/{chat_id}")
async def load_chat(chat_id: str, request: Request):

    uid = get_user_id(request)

    if not uid:
        return {"items":[]}

    db = SessionLocal()

    owner = db.query(Chat).filter(
        Chat.id == chat_id,
        Chat.user_id == uid
    ).first()

    if not owner:
        db.close()
        return {"items":[]}

    msgs = db.query(Message).filter(
        Message.chat_id == chat_id
    ).all()

    result = []

    for m in msgs:
        result.append({
            "role":m.role,
            "content":m.content
        })

    db.close()
    return {"items":result}

# ==========================================================
# TOOLS
# ==========================================================

@app.post("/tool/hash")
async def tool_hash(request: Request):
    data = await request.json()
    text = data["text"]

    return {
        "ok":True,
        "md5": hashlib.md5(text.encode()).hexdigest(),
        "sha1": hashlib.sha1(text.encode()).hexdigest(),
        "sha256": hashlib.sha256(text.encode()).hexdigest()
    }

@app.post("/tool/base64")
async def tool_base64(request: Request):
    data = await request.json()

    text = data["text"]
    mode = data["mode"]

    try:
        if mode == "encode":
            result = base64.b64encode(text.encode()).decode()
        else:
            result = base64.b64decode(text.encode()).decode()

        return {"ok":True,"result":result}

    except Exception as e:
        return {"ok":False,"msg":str(e)}

@app.post("/tool/password")
async def tool_password(request: Request):
    data = await request.json()
    pwd = data["text"]

    score = 0

    if len(pwd) >= 8: score += 1
    if re.search(r"[A-Z]", pwd): score += 1
    if re.search(r"[a-z]", pwd): score += 1
    if re.search(r"[0-9]", pwd): score += 1
    if re.search(r"[^A-Za-z0-9]", pwd): score += 1

    levels = {
        0:"Very Weak",
        1:"Weak",
        2:"Medium",
        3:"Good",
        4:"Strong",
        5:"Very Strong"
    }

    return {
        "ok":True,
        "score":score,
        "strength":levels[score]
    }

@app.post("/tool/jwt")
async def tool_jwt(request: Request):
    data = await request.json()
    token = data["text"]

    try:
        decoded = jwt.decode(
            token,
            options={"verify_signature":False}
        )

        return {"ok":True,"payload":decoded}

    except Exception as e:
        return {"ok":False,"msg":str(e)}

@app.post("/tool/whois")
async def tool_whois(request: Request):
    data = await request.json()
    domain = data["text"]

    try:
        w = whois.whois(domain)

        return {
            "ok":True,
            "domain":domain,
            "registrar":str(w.registrar),
            "creation_date":str(w.creation_date),
            "expiration_date":str(w.expiration_date),
            "name_servers":str(w.name_servers)
        }

    except Exception as e:
        return {"ok":False,"msg":str(e)}

@app.post("/tool/dns")
async def tool_dns(request: Request):
    data = await request.json()

    domain = data["text"]
    rtype = data.get("rtype","A")

    try:
        answers = dns.resolver.resolve(domain, rtype)

        result = []
        for r in answers:
            result.append(str(r))

        return {"ok":True,"records":result}

    except Exception as e:
        return {"ok":False,"msg":str(e)}
