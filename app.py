import os
import requests
from fastapi import FastAPI, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base

from passlib.context import CryptContext
from jose import jwt

# ================= CONFIG =================
SECRET_KEY = "cipher_secret"
ALGORITHM = "HS256"

DATABASE_URL = os.environ.get("DATABASE_URL")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= DB =================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)

Base.metadata.create_all(bind=engine)

# ================= AUTH =================
def hash_password(p):
    return pwd_context.hash(p)

def verify_password(p, h):
    return pwd_context.verify(p, h)

def create_token(data):
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(authorization: str = Header(None)):
    if not authorization:
        return None
    try:
        token = authorization.replace("Bearer ", "")
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except:
        return None

# ================= ROUTES =================
@app.get("/")
def home():
    return FileResponse("index.html")

@app.post("/signup")
def signup(username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            return {"success": False, "msg": "User exists"}

        user = User(username=username, password=hash_password(password))
        db.add(user)
        db.commit()

        return {"success": True, "msg": "Signup success"}
    finally:
        db.close()

@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()

        if not user or not verify_password(password, user.password):
            return {"success": False, "msg": "Invalid credentials"}

        token = create_token({
            "user_id": user.id,
            "username": user.username
        })

        return {"success": True, "token": token}
    finally:
        db.close()

# ================= CHAT =================
@app.post("/chat")
def chat(message: str = Form(...), chat_id: str = Form(...), mode: str = Form(...), authorization: str = Header(None)):

    user = get_current_user(authorization)

    if not user:
        return {"response": "❌ Unauthorized", "model": "error"}

    api_key = os.environ.get("OPENROUTER_API_KEY")

    try:
        res = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "openai/gpt-3.5-turbo",
                "messages": [
                    {"role": "system", "content": "You are CIPHER AI."},
                    {"role": "user", "content": message}
                ]
            }
        )

        data = res.json()

        reply = data.get("choices", [{}])[0].get("message", {}).get("content", "⚠️ API Error")

        return {"response": reply, "model": mode}

    except Exception as e:
        return JSONResponse(status_code=500, content={"response": str(e)})
