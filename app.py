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
from starlette.middleware.sessions import SessionMiddleware

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
# MIDDLEWARE
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REQUIRED FOR GOOGLE AUTH
app.add_middleware(
    SessionMiddleware,
    secret_key="super_secret_session_key"
)

# =========================
# DB MODEL
# =========================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)
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
    except JWTError:
        return None

# =========================
# GOOGLE AUTH
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
        return {"msg": "User already exists"}

    user = User(username=username, password=hash_password(password))
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
# GOOGLE LOGIN (FIXED HTTPS)
# =========================
@app.get("/auth/google")
async def google_login(request: Request):
    # FORCE HTTPS redirect to fix mismatch error
    redirect_uri = "https://cipher-ai-production.up.railway.app/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)

# =========================
# GOOGLE CALLBACK
# =========================
@app.get("/auth/google/callback")
async def google_callback(request: Request):
    db: Session = SessionLocal()

    token = await oauth.google.authorize_access_token(request)
    user_info = token.get("userinfo")

    email = user_info["email"]

    user = db.query(User).filter(User.username == email).first()

    if not user:
        user = User(username=email, password="oauth")
        db.add(user)
        db.commit()

    jwt_token = create_token({"user_id": user.id})

    return RedirectResponse(f"/?token={jwt_token}")

# =========================
# CHAT (PROTECTED)
# =========================
@app.post("/chat")
def chat(
    message: str = Form(...),
    chat_id: str = Form(...),
    mode: str = Form(...),
    user=Depends(get_current_user)
):
    if not user:
        return {"response": "❌ Please login first", "model": "error"}

    try:
        api_key = os.environ.get("OPENROUTER_API_KEY")

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
                    {"role": "system", "content": "You are CIPHER AI, a cybersecurity assistant."},
                    {"role": "user", "content": message}
                ]
            }
        )

        data = response.json()

        reply = data.get("choices", [{}])[0].get("message", {}).get("content", "⚠️ No response")

        return {"response": reply, "model": mode}

    except Exception as e:
        print("ERROR:", e)
        return JSONResponse(
            status_code=500,
            content={"response": "❌ Server error", "model": "error"}
        )
