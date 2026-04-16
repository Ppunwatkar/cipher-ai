import os
import requests
from fastapi import FastAPI, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base

from passlib.context import CryptContext
from jose import jwt

# ================= CONFIG =================
SECRET_KEY = "cipher_secret"
ALGORITHM = "HS256"

# ================= DATABASE (FIXED) =================
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    print("⚠️ DATABASE_URL not found → using SQLite fallback")
    DATABASE_URL = "sqlite:///./local.db"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ================= AUTH =================
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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

# ================= APP =================
app = FastAPI()

# STATIC + TEMPLATES
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= DATABASE MODEL =================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    password = Column(String)

Base.metadata.create_all(bind=engine)

# ================= ROUTES =================

# HOME (FIXED)
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# DEBUG ROUTE
@app.get("/test")
def test():
    return {"status": "working"}

# ================= SIGNUP =================
@app.post("/signup")
def signup(username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            return {"success": False, "msg": "User already exists"}

        user = User(username=username, password=hash_password(password))
        db.add(user)
        db.commit()

        return {"success": True, "msg": "Signup successful"}

    except Exception as e:
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
            return {"success": False, "msg": "Invalid credentials"}

        token = create_token({
            "user_id": user.id,
            "username": user.username
        })

        return {"success": True, "token": token}

    finally:
        db.close()

# ================= GOOGLE LOGIN =================
@app.get("/auth/google")
def google_login():
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    redirect_uri = os.environ.get("APP_URL") + "/auth/google/callback"

    url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        "&response_type=code"
        "&scope=openid email profile"
    )

    return RedirectResponse(url)

@app.get("/auth/google/callback")
def google_callback(code: str):
    db = SessionLocal()
    try:
        client_id = os.environ.get("GOOGLE_CLIENT_ID")
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
        redirect_uri = os.environ.get("APP_URL") + "/auth/google/callback"

        token_res = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code"
            }
        )

        access_token = token_res.json().get("access_token")

        user_res = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        email = user_res.json().get("email")

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
    user = get_current_user(authorization)
    if not user:
        user = {"username": "guest"}

    api_key = os.environ.get("OPENROUTER_API_KEY")

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
                    {"role": "system", "content": "You are CIPHER AI, a cybersecurity assistant."},
                    {"role": "user", "content": message}
                ]
            }
        )

        data = response.json()
        reply = data.get("choices", [{}])[0].get("message", {}).get("content")

        if not reply:
            return {"response": "⚠️ Model error"}

        return {"response": reply}

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"response": f"❌ Server error: {str(e)}"}
        )
