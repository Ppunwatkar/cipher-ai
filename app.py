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
# CORS
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
# ROOT
# =========================
@app.get("/", response_class=HTMLResponse)
def home():
    file_path = Path(__file__).parent / "index.html"

    if not file_path.exists():
        return HTMLResponse("<h1>index.html not found</h1>", status_code=404)

    return HTMLResponse(file_path.read_text())

# =========================
# PING
# =========================
@app.get("/ping")
def ping():
    return {"status": "alive"}

# =========================
# CHAT
# =========================
@app.post("/chat")
def chat(
    message: str = Form(...),
    chat_id: str = Form(...),
    mode: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        print("🔥 CHAT ENDPOINT HIT")
        print("📩 RECEIVED:", message)

        chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()

        if not chat:
            chat = models.Chat(id=chat_id, user_id=1, title="New Chat")
            db.add(chat)
            db.commit()
            db.refresh(chat)

        db.add(models.Message(chat_id=chat_id, role="user", content=message))
        db.commit()

        reply = "✅ Backend working + saved to DB"

        db.add(models.Message(chat_id=chat_id, role="assistant", content=reply))
        db.commit()

        return {"response": reply}

    except Exception as e:
        print("❌ ERROR:", str(e))
        return JSONResponse(
            status_code=500,
            content={"response": "❌ Server error"}
        )
