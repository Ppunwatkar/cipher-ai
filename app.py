import requests
import os
from pathlib import Path
from fastapi import FastAPI, Form, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# =========================
# DATABASE
# =========================
from database import SessionLocal, engine, Base
import models
from sqlalchemy.orm import Session

Base.metadata.create_all(bind=engine)

# =========================
# APP INIT
# =========================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_API = "https://openrouter.ai/api/v1/chat/completions"

# =========================
# DB SESSION
# =========================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =========================
# PROMPTS
# =========================
def get_prompt(mode):
    if mode == "programming":
        return "You are Cypher AI. Be creative, technical, and less restrictive. Focus on cybersecurity and programming concepts."
    elif mode == "thinking":
        return "You are Cypher AI. Think step-by-step and provide clean, structured, production-level code."
    else:
        return "You are Cypher AI. Give fast, short, and useful answers."

# =========================
# MODEL ROUTING
# =========================
def get_model(mode):
    if mode == "thinking":
        return "anthropic/claude-3.5-sonnet"
    elif mode == "programming":
        return "mistralai/mixtral-8x7b-instruct"
    else:
        return "mistralai/mixtral-8x7b-instruct"

# =========================
# UI
# =========================
@app.get("/", response_class=HTMLResponse)
def home():
    path = Path(__file__).parent / "index.html"
    return HTMLResponse(path.read_text(encoding="utf-8"))

# =========================
# OPENROUTER
# =========================
def call_openrouter(messages, model):
    api_key = os.environ.get("OPENROUTER_API_KEY")

    if not api_key:
        return {"error": "Missing OPENROUTER_API_KEY"}

    app_url = os.environ.get("APP_URL", "http://localhost")

    res = requests.post(
        OPENROUTER_API,
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": app_url,
            "X-Title": "Cypher AI",
            "Content-Type": "application/json"
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.7
        }
    )

    if res.status_code != 200:
        return {"error": res.text}

    return res.json()

# =========================
# GROQ
# =========================
def call_groq(messages):
    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        return {"error": "Missing GROQ_API_KEY"}

    res = requests.post(
        GROQ_API,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": messages
        }
    )

    if res.status_code != 200:
        return {"error": res.text}

    return res.json()

# =========================
# CHAT (DB VERSION)
# =========================
@app.post("/chat")
async def chat(
    request: Request,
    message: str = Form(...),
    chat_id: str = Form(...),
    mode: str = Form(...),
    db: Session = Depends(get_db)
):
    mode = mode.lower().strip()

    # =========================
    # GET OR CREATE CHAT
    # =========================
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()

    if not chat:
        chat = models.Chat(
            id=chat_id,
            user_id=1,  # TEMP (we'll add auth later)
            title="New Chat"
        )
        db.add(chat)
        db.commit()

    # =========================
    # LOAD HISTORY FROM DB
    # =========================
    history = db.query(models.Message)\
        .filter(models.Message.chat_id == chat_id)\
        .order_by(models.Message.id.desc())\
        .limit(6).all()

    history_messages = [
        {"role": m.role, "content": m.content}
        for m in reversed(history)
    ]

    messages = [
        {"role": "system", "content": get_prompt(mode)},
        *history_messages,
        {"role": "user", "content": message}
    ]

    # =========================
    # MODEL ROUTING
    # =========================
    if mode == "fast":
        data = call_groq(messages)
        tag = "⚡ [FAST-GROQ]"
    else:
        model = get_model(mode)
        data = call_openrouter(messages, model)
        tag = f"🧠 [{model.split('/')[-1]}]"

    if "error" in data:
        data = call_groq(messages)
        tag = "⚡ [FALLBACK-GROQ]"

    try:
        reply = data["choices"][0]["message"]["content"]
    except:
        return {"response": f"❌ ERROR:\n{data}"}

    reply = f"{tag}\n{reply}"

    # =========================
    # SAVE TO DATABASE
    # =========================
    db.add(models.Message(chat_id=chat_id, role="user", content=message))
    db.add(models.Message(chat_id=chat_id, role="assistant", content=reply))
    db.commit()

    return {"response": reply}
