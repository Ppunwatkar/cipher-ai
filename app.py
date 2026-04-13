import os
import requests
from datetime import datetime, timedelta

from fastapi import FastAPI, Form, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base, Session

from passlib.context import CryptContext
from jose import jwt, JWTError

# =========================
# CONFIG
# =========================
SECRET_KEY = "cipher_secret_key"
ALGORITHM = "HS256"

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./cipher.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
# DB MODEL
# =========================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)

Base.metadata.create_all(bind=engine)

# =========================
# UTILS
# =========================
def hash_password(password):
    return pwd_context.hash(password)

def verify_password(password, hashed):
    return pwd_context.verify(password, hashed)

def create_token(data):
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Header(None)):
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

# =========================
# ROOT
# =========================
@app.get("/")
def home():
    return FileResponse("index.html")

# =========================
# SIGNUP
# =========================
@app.post("/signup")
def signup(username: str = Form(...), password: str = Form(...)):
    db: Session = SessionLocal()

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        return {"msg": "User already exists"}

    user = User(
        username=username,
        password=hash_password(password)
    )

    db.add(user)
    db.commit()

    return {"msg": "Signup successful"}

# =========================
# LOGIN
# =========================
@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    db: Session = SessionLocal()

    user = db.query(User).filter(User.username == username).first()

    if not user or not verify_password(password, user.password):
        return {"msg": "Invalid credentials"}

    token = create_token({"user_id": user.id})

    return {"token": token}

# =========================
# CHAT (PROTECTED)
# =========================
@app.post("/chat")
def chat(
    message: str = Form(...),
    chat_id: str = Form(...),
    mode: str = Form(...),
    user = Depends(get_current_user)
):
    if not user:
        return {"response": "❌ Unauthorized", "model": "error"}

    try:
        api_key = os.environ.get("OPENROUTER_API_KEY")

        if not api_key:
            return {"response": "❌ Missing API key"}

        model = "openai/gpt-3.5-turbo"

        system_prompt = """
You are CIPHER AI — a cybersecurity assistant.
Be helpful, friendly, and practical.
"""

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://cipher-ai-production.up.railway.app",
                "X-Title": "CIPHER AI"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ]
            }
        )

        data = response.json()

        if "choices" not in data:
            return {"response": str(data)}

        return {
            "response": data["choices"][0]["message"]["content"],
            "model": mode
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"response": "❌ Server error"}
        )
