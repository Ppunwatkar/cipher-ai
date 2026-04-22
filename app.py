from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base
import requests
import os

# =========================
# CONFIG
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# =========================
# APP
# =========================
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# =========================
# DATABASE
# =========================
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Chat(Base):
    __tablename__ = "chats"

    id = Column(String, primary_key=True)
    user_id = Column(Integer, default=1)
    title = Column(String)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String)
    role = Column(String)
    content = Column(Text)


Base.metadata.create_all(bind=engine)

# =========================
# GROQ
# =========================
try:
    from groq import Groq
    groq_client = Groq(api_key=GROQ_API_KEY)
except:
    groq_client = None


# =========================
# OPENROUTER
# =========================
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
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=60
        )

        data = r.json()

        if "choices" not in data:
            return "No response."

        return data["choices"][0]["message"]["content"]

    except Exception as e:
        return f"Error: {str(e)}"


# =========================
# GROQ
# =========================
def call_groq(prompt):
    try:
        res = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content

    except Exception as e:
        return f"Error: {str(e)}"


# =========================
# MODEL ROUTING
# =========================
def get_reply(message, mode):
    mode = mode.lower()

    if mode == "thinking":
        return {
            "label": "🧠 THINK · GPT",
            "reply": call_openrouter("openai/gpt-4o-mini", message)
        }

    elif mode == "fast":
        return {
            "label": "⚡ FAST · GROQ",
            "reply": call_groq(message)
        }

    elif mode == "code":
        return {
            "label": "💻 CODE · CLAUDE",
            "reply": call_openrouter("anthropic/claude-3-haiku", message)
        }

    return {
        "label": "🧠 THINK · GPT",
        "reply": call_openrouter("openai/gpt-4o-mini", message)
    }


# =========================
# HOME
# =========================
@app.get("/", response_class=HTMLResponse)
def home():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


# =========================
# CHAT
# =========================
@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()

        message = data.get("message", "").strip()
        mode = data.get("mode", "thinking")
        chat_id = data.get("chat_id", "chat_1")

        if not message:
            return JSONResponse({"response": "Empty message."})

        db = SessionLocal()

        existing = db.query(Chat).filter(Chat.id == chat_id).first()

        if not existing:
            db.add(Chat(
                id=chat_id,
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

    except Exception as e:
        return JSONResponse({
            "response": f"Server Error: {str(e)}"
        })
