from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from sqlalchemy import create_engine, Column, Integer, String, Text, text
from sqlalchemy.orm import sessionmaker, declarative_base

import os
import time

# =========================
# CONFIG
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

print("DB URL:", DATABASE_URL)
print("GROQ KEY PRESENT:", bool(GROQ_API_KEY))

# =========================
# DB SETUP
# =========================
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# =========================
# MODELS
# =========================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True)


class Chat(Base):
    __tablename__ = "chats"
    id = Column(String, primary_key=True)
    user_id = Column(Integer)
    title = Column(String)


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String)
    role = Column(String)
    content = Column(Text)


Base.metadata.create_all(bind=engine)

# =========================
# FASTAPI INIT
# =========================
app = FastAPI()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# =========================
# AI SETUP
# =========================
try:
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
except Exception as e:
    print("Groq import failed:", e)
    client = None


def get_ai_response(msg):
    try:
        if not client:
            return "⚠️ Groq client not initialized"

        print("🔵 Sending to AI:", msg)

        res = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": msg}]
        )

        reply = res.choices[0].message.content

        print("🟢 AI Reply:", reply)

        return reply

    except Exception as e:
        print("🔴 AI ERROR:", str(e))
        return f"AI Error: {str(e)}"


# =========================
# ROUTES
# =========================

# HOME
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# CHAT
@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    message = data.get("message")
    chat_id = data.get("chat_id")

    user_id = 1  # TEMP

    db = SessionLocal()

    try:
        print("📩 Received:", message)

        # Check or create chat
        chat = db.query(Chat).filter(Chat.id == chat_id).first()

        if not chat:
            print("🆕 Creating new chat")
            chat = Chat(
                id=chat_id,
                user_id=user_id,
                title=message[:30]
            )
            db.add(chat)
            db.commit()

        # Save user message
        db.add(Message(chat_id=chat_id, role="user", content=message))
        db.commit()

        # AI response
        reply = get_ai_response(message)

        # Save assistant message
        db.add(Message(chat_id=chat_id, role="assistant", content=reply))
        db.commit()

        return {"response": reply}

    except Exception as e:
        print("❌ CHAT ERROR:", str(e))
        return JSONResponse(status_code=500, content={"error": str(e)})

    finally:
        db.close()


# GET CHAT MESSAGES
@app.get("/chat/{chat_id}")
def get_chat(chat_id: str):
    db = SessionLocal()

    msgs = db.query(Message)\
        .filter(Message.chat_id == chat_id)\
        .order_by(Message.id)\
        .all()

    db.close()

    return [{"role": m.role, "content": m.content} for m in msgs]


# SIDEBAR CHATS
@app.get("/chats")
def get_chats():
    user_id = 1

    db = SessionLocal()

    chats = db.query(Chat)\
        .filter(Chat.user_id == user_id)\
        .order_by(Chat.id.desc())\
        .all()

    db.close()

    return [
        {"chat_id": c.id, "title": c.title}
        for c in chats
    ]


# DB CHECK
@app.get("/db-check")
def db_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "connected"}
    except Exception as e:
        return {"error": str(e)}


# AI TEST
@app.get("/ai-test")
def ai_test():
    return {"response": get_ai_response("Hello")}
