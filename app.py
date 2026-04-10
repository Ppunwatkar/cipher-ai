import requests
import os
from pathlib import Path
from fastapi import FastAPI, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from database import SessionLocal, engine, Base
import models
from sqlalchemy.orm import Session

app = FastAPI()

# =========================
# CORS FIX (IMPORTANT)
# =========================
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
    print("🚀 Backend running...")
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
# ROOT (SERVE UI)
# =========================
@app.get("/")
def home():
    path = Path("index.html")
    return HTMLResponse(path.read_text())

# =========================
# DEBUG ROUTE
# =========================
@app.get("/ping")
def ping():
    return {"status": "alive"}

# =========================
# CHAT ROUTE (FORCED WORKING)
# =========================
@app.post("/chat")
def chat(
    message: str = Form(...),
    chat_id: str = Form(...),
    mode: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        print("📩 RECEIVED:", message)

        # CREATE CHAT
        chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()

        if not chat:
            chat = models.Chat(id=chat_id, user_id=1, title="New Chat")
            db.add(chat)
            db.commit()
            db.refresh(chat)

        # SAVE USER MESSAGE
        db.add(models.Message(chat_id=chat_id, role="user", content=message))
        db.commit()

        # SIMPLE RESPONSE
        reply = "✅ Backend working + saved to DB"

        # SAVE BOT MESSAGE
        db.add(models.Message(chat_id=chat_id, role="assistant", content=reply))
        db.commit()

        print("✅ SAVED TO DB")

        return {"response": reply}

    except Exception as e:
        print("❌ ERROR:", str(e))
        return JSONResponse(
            status_code=500,
            content={"response": "❌ Server error"}
        )
