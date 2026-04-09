import requests
import os
from pathlib import Path
from fastapi import FastAPI, Form, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

# =========================
# DATABASE
# =========================
from database import SessionLocal, engine, Base
import models
from sqlalchemy.orm import Session

# =========================
# APP INIT (FIXED POSITION)
# =========================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# CREATE TABLES ON STARTUP
# =========================
@app.on_event("startup")
def startup():
    print("🚀 Creating database tables...")
    Base.metadata.create_all(bind=engine)

# =========================
# CONSTANTS
# =========================
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
        return "You are Cypher AI. Be creative, technical, and less restrictive. Focus on cybersecurity and programming."
    elif mode == "thinking":
        return "Think step-by-step and provide structured answers."
    else:
        return "Give fast and short answers."

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
# UI ROUTE
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
# CHAT ROUTE (FULLY FIXED)
# =========================
@app.post("/chat")
async def chat(
    request: Request,
    message: str = Form(...),
    chat_id: str = Form(...),
    mode: str = Form(...),
    db: Session = Depends(get_db)
):
    print("📩 Incoming message:", message)
    print("📌 Chat ID:", chat_id)

    mode = mode.lower().strip()

    # =========================
    # CREATE / GET CHAT
    # =========================
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()

    if not chat:
        print("🆕 Creating new chat")

        chat = models.Chat(
            id=chat_id,
            user_id=1,  # temporary (auth later)
            title="New Chat"
        )
        db.add(chat)
        db.commit()
        db.refresh(chat)

    # =========================
    # LOAD HISTORY
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
    # MODEL CALL
    # =========================
    if mode == "fast":
        data = call_groq(messages)
        tag = "⚡ [FAST-GROQ]"
    else:
        model = get_model(mode)
        data = call_openrouter(messages, model)
        tag = f"🧠 [{model.split('/')[-1]}]"

    if "error" in data:
        print("⚠️ OpenRouter failed → fallback to Groq")
        data = call_groq(messages)
        tag = "⚡ [FALLBACK-GROQ]"

    try:
        reply = data["choices"][0]["message"]["content"]
    except Exception as e:
        print("❌ AI ERROR:", data)
        return {"response": f"❌ ERROR:\n{data}"}

    reply = f"{tag}\n{reply}"

    # =========================
    # SAVE TO DATABASE
    # =========================
    print("💾 Saving messages to DB")

    user_msg = models.Message(
        chat_id=chat_id,
        role="user",
        content=message
    )

    bot_msg = models.Message(
        chat_id=chat_id,
        role="assistant",
        content=reply
    )

    db.add(user_msg)
    db.add(bot_msg)
    db.commit()

    print("✅ Saved successfully")

    return {"response": reply}
