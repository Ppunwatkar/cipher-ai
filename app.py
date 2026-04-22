from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker

from groq import Groq
import requests
import os

# ==================================================
# CONFIG
# ==================================================

DATABASE_URL = os.getenv("DATABASE_URL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
APP_SECRET = os.getenv("APP_SECRET", "cipher_secret_key")

# ==================================================
# APP
# ==================================================

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=APP_SECRET)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ==================================================
# DATABASE
# ==================================================

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ==================================================
# TABLES (MATCHING YOUR REAL DB)
# ==================================================

# users = id | username | password
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(255))
    password = Column(String(255))


# chats = id | title | user_id
class Chat(Base):
    __tablename__ = "chats"

    id = Column(String(255), primary_key=True)
    title = Column(String(255))
    user_id = Column(Integer)


# messages = id | chat_id | role | content
class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    chat_id = Column(String(255))
    role = Column(String(50))
    content = Column(Text)


Base.metadata.create_all(bind=engine)

# ==================================================
# AI CLIENTS
# ==================================================

groq_client = Groq(api_key=GROQ_API_KEY)

# ==================================================
# HELPERS
# ==================================================

def current_user(request: Request):
    return request.session.get("user_id")


def ask_groq(prompt):
    try:
        res = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        return res.choices[0].message.content
    except Exception as e:
        return f"GROQ Error: {str(e)}"


def ask_openrouter(prompt, model):
    try:
        r = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=60
        )

        data = r.json()

        if "choices" in data:
            return data["choices"][0]["message"]["content"]

        return str(data)

    except Exception as e:
        return f"AI Error: {str(e)}"

# ==================================================
# HOME
# ==================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )

# ==================================================
# AUTH
# ==================================================

@app.post("/signup")
async def signup(request: Request):
    try:
        data = await request.json()

        email = data["email"].strip().lower()
        password = data["password"].strip()

        db = SessionLocal()

        old = db.query(User).filter(
            User.username == email
        ).first()

        if old:
            db.close()
            return {"ok": False, "msg": "Account already exists"}

        user = User(
            username=email,
            password=password
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        request.session["user_id"] = user.id
        request.session["email"] = user.username

        db.close()

        return {"ok": True}

    except Exception as e:
        return {"ok": False, "msg": str(e)}


@app.post("/login")
async def login(request: Request):
    try:
        data = await request.json()

        email = data["email"].strip().lower()
        password = data["password"].strip()

        db = SessionLocal()

        user = db.query(User).filter(
            User.username == email,
            User.password == password
        ).first()

        if not user:
            db.close()
            return {"ok": False, "msg": "Invalid credentials"}

        request.session["user_id"] = user.id
        request.session["email"] = user.username

        db.close()

        return {"ok": True}

    except Exception as e:
        return {"ok": False, "msg": str(e)}


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/me")
async def me(request: Request):

    uid = current_user(request)

    if uid:
        return {
            "logged_in": True,
            "email": request.session.get("email")
        }

    return {"logged_in": False}

# ==================================================
# CHAT
# ==================================================

@app.post("/chat")
async def chat(request: Request):

    try:
        data = await request.json()

        prompt = data["message"]
        mode = data["mode"]
        chat_id = data["chat_id"]

        uid = current_user(request)

        # ---------- MODEL ROUTING ----------

        if mode == "thinking":
            answer = ask_openrouter(
                prompt,
                "openai/gpt-4o-mini"
            )
            label = "🧠 THINK • GPT"

        elif mode == "code":
            answer = ask_openrouter(
                prompt,
                "anthropic/claude-3-haiku"
            )
            label = "💻 CODE • CLAUDE"

        else:
            answer = ask_groq(prompt)
            label = "⚡ FAST • GROQ"

        # ---------- SAVE ONLY IF LOGIN ----------

        if uid:

            db = SessionLocal()

            chat_exists = db.query(Chat).filter(
                Chat.id == chat_id
            ).first()

            if not chat_exists:
                db.add(Chat(
                    id=chat_id,
                    title=prompt[:40],
                    user_id=uid
                ))

            # user msg
            db.add(Message(
                chat_id=chat_id,
                role="user",
                content=prompt
            ))

            # ai msg
            db.add(Message(
                chat_id=chat_id,
                role="assistant",
                content=answer
            ))

            db.commit()
            db.close()

        return {
            "ok": True,
            "label": label,
            "response": answer
        }

    except Exception as e:
        return {
            "ok": False,
            "label": "SYSTEM",
            "response": str(e)
        }

# ==================================================
# HISTORY
# ==================================================

@app.get("/history")
async def history(request: Request):

    uid = current_user(request)

    if not uid:
        return {"items": []}

    db = SessionLocal()

    chats = db.query(Chat).filter(
        Chat.user_id == uid
    ).order_by(Chat.id.desc()).all()

    result = []

    for c in chats:
        result.append({
            "id": c.id,
            "title": c.title if c.title else "New Chat"
        })

    db.close()

    return {"items": result}

# ==================================================
# LOAD SINGLE CHAT
# ==================================================

@app.get("/chat/{chat_id}")
async def get_chat(chat_id: str, request: Request):

    uid = current_user(request)

    if not uid:
        return {"items": []}

    db = SessionLocal()

    # verify ownership
    owner = db.query(Chat).filter(
        Chat.id == chat_id,
        Chat.user_id == uid
    ).first()

    if not owner:
        db.close()
        return {"items": []}

    msgs = db.query(Message).filter(
        Message.chat_id == chat_id
    ).order_by(Message.id.asc()).all()

    result = []

    for m in msgs:
        result.append({
            "role": m.role,
            "content": m.content
        })

    db.close()

    return {"items": result}

# ==================================================
# HEALTH
# ==================================================

@app.get("/ping")
async def ping():
    return {"status": "ok"}
