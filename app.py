import os
import requests
from fastapi import FastAPI, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from passlib.context import CryptContext
from pathlib import Path
from jose import jwt

# ================= CONFIG =================
SECRET_KEY = "cipher_secret"
ALGORITHM = "HS256"

# ================= DATABASE =================
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")
else:
    DATABASE_URL = "sqlite:///./local.db"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ================= MODELS =================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    chat_id = Column(String)
    role = Column(String)
    content = Column(Text)

Base.metadata.create_all(bind=engine)

# ================= AUTH =================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(p):
    return pwd_context.hash(p)

def verify_password(p, h):
    return pwd_context.verify(p, h)

def create_token(data):
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

def get_user(authorization: str = Header(None)):
    if not authorization:
        return None
    try:
        token = authorization.replace("Bearer ", "")
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except:
        return None

# ================= APP =================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= HEALTH =================
@app.get("/health")
def health():
    return {"status": "alive"}

# ================= DB CHECK =================
@app.get("/db-check")
def db_check():
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        return {"status": "DB connected"}
    except Exception as e:
        return {"error": str(e)}

# ================= HOME =================
@app.get("/", response_class=HTMLResponse)
def home():
    try:
        base_dir = Path(__file__).parent
        file_path = base_dir / "templates" / "index.html"
        return HTMLResponse(file_path.read_text(encoding="utf-8"))
    except Exception as e:
        return HTMLResponse(f"<h1>UI Error: {str(e)}</h1>")

# ================= SIGNUP =================
@app.post("/signup")
def signup(username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            return {"success": False, "msg": "User exists"}

        user = User(username=username, password=hash_password(password))
        db.add(user)
        db.commit()

        return {"success": True}
    except Exception as e:
        db.rollback()
        return {"success": False, "msg": str(e)}
    finally:
        db.close()

# ================= LOGIN =================
@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()

        if not user or not verify_password(password, user.password):
            return {"success": False, "msg": "Invalid"}

        token = create_token({
            "user_id": user.id,
            "username": user.username
        })

        return {"success": True, "token": token}
    finally:
        db.close()

# ================= CHAT =================
@app.post("/chat")
def chat(
    message: str = Form(...),
    chat_id: str = Form(...),
    mode: str = Form(...),
    authorization: str = Header(None)
):
    db = SessionLocal()

    try:
        # ================= SAVE USER MESSAGE =================
        user_msg = Message(chat_id=chat_id, role="user", content=message)
        db.add(user_msg)
        db.commit()

        # ================= MODEL CALL =================
        api_key = os.environ.get("OPENROUTER_API_KEY")

        if not api_key:
            reply = "⚠️ OPENROUTER_API_KEY missing"
        else:
            try:
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "openai/gpt-3.5-turbo",
                        "messages": [
                            {"role": "system", "content": "You are a cybersecurity assistant."},
                            {"role": "user", "content": message}
                        ]
                    },
                    timeout=15
                )

                print("MODEL STATUS:", response.status_code)
                print("MODEL RAW:", response.text)

                if response.status_code != 200:
                    reply = f"⚠️ Model HTTP {response.status_code}"
                else:
                    data = response.json()
                    reply = data.get("choices", [{}])[0].get("message", {}).get("content")

                    if not reply:
                        reply = "⚠️ Empty model response"

            except Exception as model_err:
                reply = f"⚠️ Model failed: {str(model_err)}"

        # ================= SAVE BOT MESSAGE =================
        bot_msg = Message(chat_id=chat_id, role="assistant", content=reply)
        db.add(bot_msg)
        db.commit()

        return {"response": reply}

    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"response": f"❌ Backend error: {str(e)}"}
        )

    finally:
        db.close()
