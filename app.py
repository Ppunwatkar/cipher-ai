import os
import requests
from fastapi import FastAPI, Form, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from jose import jwt

from database import SessionLocal, engine, Base
import models

app = FastAPI()
Base.metadata.create_all(bind=engine)

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

SECRET_KEY = "cipher_secret"
ALGORITHM = "HS256"

# =========================
# DB
# =========================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =========================
# AUTH
# =========================
def get_current_user(token: str = Header(None), db: Session = Depends(get_db)):
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return db.query(models.User).filter(models.User.id == payload["user_id"]).first()
    except:
        return None

# =========================
# ROOT
# =========================
@app.get("/")
def home():
    return FileResponse("index.html")

# =========================
# GET CHATS
# =========================
@app.get("/chats")
def get_chats(db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not user:
        return []
    chats = db.query(models.Chat).filter(models.Chat.user_id == user.id).all()
    return [{"id": c.id} for c in chats]

# =========================
# GET CHAT
# =========================
@app.get("/chat/{chat_id}")
def get_chat(chat_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    msgs = db.query(models.Message).filter(models.Message.chat_id == chat_id).all()
    return {"messages": [{"role": m.role, "content": m.content} for m in msgs]}

# =========================
# CHAT
# =========================
@app.post("/chat")
def chat(
    message: str = Form(...),
    chat_id: str = Form(...),
    mode: str = Form(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    if not user:
        return {"response": "❌ Unauthorized", "model": "error"}

    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if not chat:
        chat = models.Chat(id=chat_id, user_id=user.id)
        db.add(chat)
        db.commit()

    db.add(models.Message(chat_id=chat_id, role="user", content=message))
    db.commit()

    # AI
    if message.lower() in ["hi", "hello"]:
        reply = "Hi, I'm CIPHER AI — your cybersecurity assistant."
    else:
        api_key = os.environ.get("OPENROUTER_API_KEY")

        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://cipher-ai-production.up.railway.app",
                    "X-Title": "CIPHER AI"
                },
                json={
                    "model": "openai/gpt-3.5-turbo",
                    "messages": [
                        {"role": "system", "content": "You are a cybersecurity assistant."},
                        {"role": "user", "content": message}
                    ]
                }
            )

            data = response.json()
            reply = data.get("choices", [{}])[0].get("message", {}).get("content", "⚠️ No response")

        except:
            reply = "❌ AI request failed"

    db.add(models.Message(chat_id=chat_id, role="assistant", content=reply))
    db.commit()

    return {"response": reply, "model": mode}
