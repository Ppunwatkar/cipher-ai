import requests
import os
import json
from pathlib import Path
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GROQ_API = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_API = "https://openrouter.ai/api/v1/chat/completions"

MEMORY_FILE = Path("memory/chats.json")
MEMORY_FILE.parent.mkdir(exist_ok=True)

if not MEMORY_FILE.exists():
    MEMORY_FILE.write_text("{}")

def load_memory():
    return json.loads(MEMORY_FILE.read_text())

def save_memory(data):
    MEMORY_FILE.write_text(json.dumps(data, indent=2))

# =========================
# PROMPTS
# =========================
def get_prompt(mode):
    if mode == "brainstorm":
        return "Be creative, direct, and technical. Focus on ideas."
    elif mode == "thinking":
        return "Think step-by-step and give structured answers."
    else:
        return "Give short, fast answers."

# =========================
# UI
# =========================
@app.get("/", response_class=HTMLResponse)
def home():
    path = Path(__file__).parent / "index.html"
    return HTMLResponse(path.read_text(encoding="utf-8"))

# =========================
# OPENROUTER (DOLPHIN)
# =========================
def call_openrouter(messages):
    api_key = os.environ.get("OPENROUTER_API_KEY")
    app_url = os.environ.get("APP_URL")

    res = requests.post(
        OPENROUTER_API,
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": app_url,
            "X-Title": "Cypher AI",
            "Content-Type": "application/json"
        },
        json={
            "model": "cognitivecomputations/dolphin-mixtral-8x7b",
            "messages": messages,
            "temperature": 0.9
        }
    )

    print("🧠 DOLPHIN STATUS:", res.status_code)

    if res.status_code != 200:
        return {"error": res.text}

    return res.json()

# =========================
# GROQ
# =========================
def call_groq(messages):
    api_key = os.environ.get("GROQ_API_KEY")

    res = requests.post(
        GROQ_API,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "llama-3.3-70b-versatile",
            "messages": messages
        }
    )

    print("⚡ GROQ STATUS:", res.status_code)

    if res.status_code != 200:
        return {"error": res.text}

    return res.json()

# =========================
# CHAT
# =========================
@app.post("/chat")
async def chat(
    message: str = Form(...),
    chat_id: str = Form(...),
    mode: str = Form(...)
):

    mode = mode.lower().strip()
    print("MODE:", mode)

    memory_data = load_memory()

    if chat_id not in memory_data:
        memory_data[chat_id] = []

    history = memory_data[chat_id]

    messages = [
        {"role": "system", "content": get_prompt(mode)},
        *history[-6:],
        {"role": "user", "content": message}
    ]

    # =========================
    # ROUTING
    # =========================
    if mode == "brainstorm":
        print("🧠 USING DOLPHIN")
        data = call_openrouter(messages)

        if "error" in data:
            return {"response": f"❌ DOLPHIN ERROR:\n{data}"}

        tag = "🧠 [DOLPHIN]"

    else:
        print("⚡ USING GROQ")
        data = call_groq(messages)

        if "error" in data:
            return {"response": f"❌ GROQ ERROR:\n{data}"}

        tag = "⚡ [GROQ]"

    try:
        reply = data["choices"][0]["message"]["content"]
    except:
        return {"response": f"❌ RAW:\n{data}"}

    reply = f"{tag}\n{reply}"

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": reply})
    save_memory(memory_data)

    return {"response": reply}

# =========================
# RUN
# =========================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
