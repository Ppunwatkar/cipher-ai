from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base

import os

# =========================
# CONFIG
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# =========================
# DB SETUP
# =========================
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class Chat(Base):
    __tablename__ = "chats"
    id = Column(String, primary_key=True)
    user_id = Column(Integer)
    title = Column(String)

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    chat_id = Column(String)
    role = Column(String)
    content = Column(Text)

Base.metadata.create_all(bind=engine)

# =========================
# APP
# =========================
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# =========================
# AI CLIENT
# =========================
try:
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
except:
    client = None

# =========================
# MULTI MODEL RESPONSE
# =========================
def ask_model(model, message):
    try:
        res = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": message}]
        )
        return res.choices[0].message.content
    except Exception as e:
        return f"[{model} ERROR]"

def get_multi_response(message):
    if not client:
        return "⚠️ AI not configured"

    responses = []

    # 🔥 ALL MODELS RUN
    models = {
        "🧠 THINK": "llama-3.1-70b-versatile",
        "⚡ FAST": "llama-3.1-8b-instant",
        "💻 CODE": "llama-3.1-70b-versatile"
    }

    for label, model in models.items():
        reply = ask_model(model, message)
        responses.append(f"### {label}\n{reply}")

    return "\n\n---\n\n".join(responses)

# =========================
# ROUTES
# =========================
@app.get("/", response_class=HTMLResponse)
def home():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.post("/chat")
async def chat(request: Request):
    try:
        data = await request.json()
    except:
        return {"response": "Invalid request"}

    message = data.get("message")
    chat_id = data.get("chat_id")

    if not message:
        return {"response": "Empty message"}

    db = SessionLocal()

    try:
        chat = db.query(Chat).filter(Chat.id == chat_id).first()
        if not chat:
            chat = Chat(id=chat_id, user_id=1, title=message[:30])
            db.add(chat)
            db.commit()

        db.add(Message(chat_id=chat_id, role="user", content=message))
        db.commit()

        reply = get_multi_response(message)

        db.add(Message(chat_id=chat_id, role="assistant", content=reply))
        db.commit()

        return {"response": reply}

    except Exception as e:
        return {"response": f"Error: {str(e)}"}

    finally:
        db.close()
