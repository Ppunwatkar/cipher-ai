from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from groq import Groq

# =========================
# CONFIG
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# =========================
# DB SETUP
# =========================
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# =========================
# MODELS
# =========================
class Chat(Base):
    __tablename__ = "chats"

    id = Column(String, primary_key=True)
    title = Column(String)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String)
    role = Column(String)
    content = Column(Text)


# Create tables if not exist
Base.metadata.create_all(bind=engine)

# =========================
# AI SETUP
# =========================
client = Groq(api_key=GROQ_API_KEY)

def get_ai_response(user_message):
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI Error: {str(e)}"

# =========================
# FASTAPI
# =========================
app = FastAPI()

# =========================
# HOME (UI)
# =========================
@app.get("/", response_class=HTMLResponse)
def home():
    try:
        with open("templates/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except Exception as e:
        return HTMLResponse(f"<h1>UI Error: {str(e)}</h1>")


# =========================
# CREATE / CHAT
# =========================
@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    user_message = data.get("message")
    chat_id = data.get("chat_id")

    db = SessionLocal()

    try:
        # ✅ FIX: Create chat if not exists
        chat = db.query(Chat).filter(Chat.id == chat_id).first()

        if not chat:
            chat = Chat(id=chat_id, title="New Chat")
            db.add(chat)
            db.commit()

        # Save user message
        user_msg = Message(
            chat_id=chat_id,
            role="user",
            content=user_message
        )
        db.add(user_msg)
        db.commit()

        # AI response
        bot_reply = get_ai_response(user_message)

        # Save bot message
        bot_msg = Message(
            chat_id=chat_id,
            role="assistant",
            content=bot_reply
        )
        db.add(bot_msg)
        db.commit()

        return {"response": bot_reply}

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

    finally:
        db.close()


# =========================
# GET CHAT HISTORY
# =========================
@app.get("/chat/{chat_id}")
def get_chat(chat_id: str):
    db = SessionLocal()

    try:
        messages = db.query(Message)\
            .filter(Message.chat_id == chat_id)\
            .order_by(Message.id)\
            .all()

        return [
            {"role": m.role, "content": m.content}
            for m in messages
        ]

    finally:
        db.close()


# =========================
# DB CHECK
# =========================
from sqlalchemy import text

@app.get("/db-check")
def db_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "connected"}
    except Exception as e:
        return {"error": str(e)}
