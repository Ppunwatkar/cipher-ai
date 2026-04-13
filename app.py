import os
import requests
from fastapi import FastAPI, Form, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base, Session

from passlib.context import CryptContext
from jose import jwt, JWTError

from authlib.integrations.starlette_client import OAuth

# =========================
# CONFIG
# =========================
SECRET_KEY = "cipher_secret"
ALGORITHM = "HS256"

DATABASE_URL = os.environ.get("DATABASE_URL")

engine = create_engine(DATABASE_URL)
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
# AUTH UTILS
# =========================
def hash_password(p):
    return pwd_context.hash(p)

def verify_password(p, h):
    return pwd_context.verify(p, h)

def create_token(data):
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Header(None)):
    if not token:
        return None
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except:
        return None

# =========================
# GOOGLE AUTH (STATELESS)
# =========================
oauth = OAuth()

oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

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

    if db.query(User).filter(User.username == username).first():
        return {"msg": "User exists"}

    user = User(username=username, password=hash_password(password))
    db.add(user)
    db.commit()

    return {"msg": "Signup success"}

# =========================
# LOGIN
# =========================
@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    db: Session = SessionLocal()

    user = db.query(User).filter(User.username == username).first()

    if not user or not verify_password(password, user.password):
        return {"msg": "Invalid credentials"}

    token = create_token({
        "user_id": user.id,
        "username": user.username
    })

    return {"token": token}

# =========================
# GOOGLE LOGIN (MANUAL URL)
# =========================
@app.get("/auth/google")
def google_login():
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    redirect_uri = "https://cipher-ai-production.up.railway.app/auth/google/callback"

    url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope=openid email profile"

    return RedirectResponse(url)

# =========================
# GOOGLE CALLBACK (NO STATE)
# =========================
@app.get("/auth/google/callback")
def google_callback(code: str):
    db: Session = SessionLocal()

    try:
        client_id = os.environ.get("GOOGLE_CLIENT_ID")
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")

        # 🔥 Exchange code for token
        token_res = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": "https://cipher-ai-production.up.railway.app/auth/google/callback",
                "grant_type": "authorization_code"
            }
        )

        token_data = token_res.json()

        access_token = token_data.get("access_token")

        # 🔥 Get user info
        user_res = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        user_info = user_res.json()
        email = user_info.get("email")

        if not email:
            return JSONResponse({"error": "No email"})

        user = db.query(User).filter(User.username == email).first()

        if not user:
            user = User(username=email, password="oauth")
            db.add(user)
            db.commit()

        jwt_token = create_token({
            "user_id": user.id,
            "username": user.username
        })

        return RedirectResponse(f"/?token={jwt_token}")

    except Exception as e:
        print("GOOGLE ERROR:", e)
        return JSONResponse({"error": str(e)})

# =========================
# CHAT
# =========================
@app.post("/chat")
def chat(message: str = Form(...), chat_id: str = Form(...), mode: str = Form(...), user=Depends(get_current_user)):

    if not user:
        return {"response": "❌ Unauthorized", "model": "error"}

    api_key = os.environ.get("OPENROUTER_API_KEY")

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
    reply = data.get("choices", [{}])[0].get("message", {}).get("content", "⚠️ Error")

    return {"response": reply, "model": mode}
