import requests
import os
import json
from pathlib import Path
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

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
# API ENDPOINTS
# =========================
GROQ_API = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_API = "https://openrouter.ai/api/v1/chat/completions"

# =========================
# MEMORY FILE
# =========================
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
    prompts = {
        "assistant": "You are a helpful AI assistant.",
        "research": "You are a deep research AI. Give structured answers.",
        "redteam": "You are a cybersecurity trainer. Explain attacks safely."
    }
    return prompts.get(mode, prompts["assistant"])

# =========================
# TOOL SYSTEM (SAFE SIM)
# =========================
def run_tool(message):
    msg = message.lower()

    if "nmap" in msg:
        return """[SIMULATION]
nmap scan result:
22/tcp open  ssh
80/tcp open  http"""

    if "whois" in msg:
        return """[SIMULATION]
Domain: example.com
Registrar: ICANN"""

    return None

# =========================
# UI
# =========================
@app.get("/", response_class=HTMLResponse)
def home():
    path = Path(__file__).parent / "index.html"
    return HTMLResponse(path.read_text(encoding="utf-8"))

# =========================
# OPENROUTER CALL (FIXED)
# =========================
def call_openrouter(messages):
    api_key = os.environ.get("OPENROUTER_API_KEY")
    app_url = os.environ.get("APP_URL", "https://your-app.up.railway.app")

    if not api_key:
        return {"error": {"message": "Missing OpenRouter API key"}}

    try:
        res = requests.post(
            OPENROUTER_API,
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": app_url,  # ✅ FIXED (NO localhost)
                "X-Title": "Cypher AI",
                "Content-Type": "application/json"
            },
            json={
                "model": "cognitivecomputations/dolphin-mixtral-8x7b",
                "messages": messages
            },
            timeout=30
        )

        print("🔵 OpenRouter STATUS:", res.status_code)
        print("🔵 OpenRouter RAW:", res.text)

        if res.status_code != 200:
            return {"error": {"message": res.text}}

        return res.json()

    except Exception as e:
        return {"error": {"message": str(e)}}

# =========================
# GROQ CALL
# =========================
def call_groq(messages):
    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        return {"error": {"message": "Missing GROQ API key"}}

    try:
        res = requests.post(
            GROQ_API,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": messages
            },
            timeout=30
        )

        print("🟢 Groq STATUS:", res.status_code)

        if res.status_code != 200:
            return {"error": {"message": res.text}}

        return res.json()

    except Exception as e:
        return {"error": {"message": str(e)}}

# =========================
# CHAT
# =========================
@app.post("/chat")
async def chat(
    message: str = Form(...),
    chat_id: str = Form(...),
    mode: str = Form(...),
    provider: str = Form("auto")  # auto / groq / openrouter
):

    # TOOL
    tool = run_tool(message)
    if tool:
        return {"response": tool}

    memory_data = load_memory()

    if chat_id not in memory_data:
        memory_data[chat_id] = []

    history = memory_data[chat_id]

    messages = [
        {"role": "system", "content": get_prompt(mode)},
        *history[-8:],
        {"role": "user", "content": message}
    ]

    # =========================
    # PROVIDER LOGIC
    # =========================
    if provider == "openrouter":
        data = call_openrouter(messages)

    elif provider == "groq":
        data = call_groq(messages)

    else:
        # AUTO FALLBACK
        data = call_openrouter(messages)

        if "error" in data:
            print("⚠️ OpenRouter failed → switching to Groq")
            data = call_groq(messages)

    # =========================
    # RESPONSE PARSE
    # =========================
    if "error" in data:
        return {"response": f"❌ {data['error']['message']}"}

    try:
        reply = data["choices"][0]["message"]["content"]
    except:
        return {"response": "❌ Invalid API response"}

    # SAVE MEMORY
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
