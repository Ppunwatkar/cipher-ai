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

# =========================
# STARTUP
# =========================
@app.on_event("startup")
def startup():
    print("🚀 App started")
    Base.metadata.create_all(bind=engine)

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
# UI
# =========================
@app.get("/", response_class=HTMLResponse)
def home():
    path = Path(__file__).parent / "index.html"
    return HTMLResponse(path.read_text())

# =========================
# DEBUG ROUTE (VERY IMPORTANT)
# =========================
@app.get("/test-db")
def test_db(db: Session = Depends(get_db)):
    try:
        count = db.query(models.Message).count()
        return {"status": "DB working", "messages": count}
    except Exception as e:
        return {"error": str(e)}

# =========================
# CHAT (FORCED SAVE VERSION)
# =========================
@app.post("/chat")
async def chat(
    message: str = Form(...),
    chat_id: str = Form(...),
    mode: str = Form(...),
    db: Session = Depends(get_db)
):
    print("\n📩 MESSAGE RECEIVED:", message)
    print("📌 CHAT ID:", chat_id)

    # =========================
    # CREATE CHAT IF NOT EXISTS
    # =========================
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()

    if not chat:
        print("🆕 Creating new chat")
        chat = models.Chat(id=chat_id, user_id=1, title="New Chat")
        db.add(chat)
        db.commit()
        db.refresh(chat)

    # =========================
    # FORCE SAVE USER MESSAGE
    # =========================
    try:
        print("💾 Saving USER message")

        user_msg = models.Message(
            chat_id=chat_id,
            role="user",
            content=message
        )

        db.add(user_msg)
        db.commit()

        print("✅ User message saved")

    except Exception as e:
        print("❌ ERROR saving user message:", e)
        return {"response": "DB ERROR"}

    # =========================
    # SIMPLE REPLY (NO AI FOR NOW)
    # =========================
    reply = "✅ Message stored successfully"

    # =========================
    # SAVE BOT MESSAGE
    # =========================
    try:
        print("💾 Saving BOT message")

        bot_msg = models.Message(
            chat_id=chat_id,
            role="assistant",
            content=reply
        )

        db.add(bot_msg)
        db.commit()

        print("✅ Bot message saved")

    except Exception as e:
        print("❌ ERROR saving bot message:", e)

    return {"response": reply}
