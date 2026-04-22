from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
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
# TABLES
# ==================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    email = Column(String(200), unique=True)
    password = Column(String(200))


class Chat(Base):
    __tablename__ = "chats"

    id = Column(String(200), primary_key=True)
    user_id = Column(Integer)
    title = Column(String(300))


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)
    chat_id = Column(String(200))
    role = Column(String(20))
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
        chat = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":prompt}]
        )
        return chat.choices[0].message.content
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
                "messages":[{"role":"user","content":prompt}]
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
        request=request,
        name="index.html",
        context={"request": request}
    )

# ==================================================
# AUTH
# ==================================================

@app.post("/signup")
async def signup(request: Request):

    try:
        data = await request.json()

        db = SessionLocal()

        old = db.query(User).filter(
            User.email == data["email"]
        ).first()

        if old:
            db.close()
            return {"ok": False, "msg": "Email already exists"}

        user = User(
            name=data["name"],
            email=data["email"],
            password=data["password"]
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        request.session["user_id"] = user.id
        request.session["name"] = user.name

        db.close()

        return {"ok": True}

    except Exception as e:
        return {"ok": False, "msg": str(e)}


@app.post("/login")
async def login(request: Request):

    try:
        data = await request.json()

        db = SessionLocal()

        user = db.query(User).filter(
            User.email == data["email"],
            User.password == data["password"]
        ).first()

        if not user:
            db.close()
            return {"ok": False, "msg": "Invalid credentials"}

        request.session["user_id"] = user.id
        request.session["name"] = user.name

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
            "name": request.session.get("name")
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

        # MODEL ROUTING
        if mode == "thinking":
            answer = ask_openrouter(
                prompt,
                "openai/gpt-4o-mini"
            )
            label = "🧠 THINK • GPT"

        elif mode == "code":
            answer = ask_openrouter(
                prompt,
                "anthropic/claude-3.5-sonnet"
            )
            label = "💻 CODE • CLAUDE"

        else:
            answer = ask_groq(prompt)
            label = "⚡ FAST • GROQ"

        # SAVE ONLY IF LOGIN
        if uid:

            db = SessionLocal()

            exists = db.query(Chat).filter(
                Chat.id == chat_id
            ).first()

            if not exists:
                db.add(Chat(
                    id=chat_id,
                    user_id=uid,
                    title=prompt[:40]
                ))

            db.add(Message(
                user_id=uid,
                chat_id=chat_id,
                role="user",
                content=prompt
            ))

            db.add(Message(
                user_id=uid,
                chat_id=chat_id,
                role="assistant",
                content=answer
            ))

            db.commit()
            db.close()

        return {
            "response": answer,
            "label": label
        }

    except Exception as e:
        return {
            "response": f"Error: {str(e)}",
            "label": "SYSTEM"
        }

# ==================================================
# HISTORY
# ==================================================

@app.get("/history")
async def history(request: Request):

    uid = current_user(request)

    if not uid:
        return []

    db = SessionLocal()

    chats = db.query(Chat).filter(
        Chat.user_id == uid
    ).all()

    result = []

    for c in chats:
        result.append({
            "id": c.id,
            "title": c.title
        })

    db.close()

    return result


@app.get("/chat/{chat_id}")
async def get_chat(chat_id: str, request: Request):

    uid = current_user(request)

    if not uid:
        return []

    db = SessionLocal()

    msgs = db.query(Message).filter(
        Message.user_id == uid,
        Message.chat_id == chat_id
    ).all()

    result = []

    for m in msgs:
        result.append({
            "role": m.role,
            "content": m.content
        })

    db.close()

    return result

# ==================================================
# TEST
# ==================================================

@app.get("/ping")
async def ping():
    return {"status": "ok"}
