import requests
import os
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

LLAMA_API = "https://api.groq.com/openai/v1/chat/completions"

# =========================
# MEMORY STORE
# =========================
chat_sessions = {}

# =========================
# PROMPT SYSTEM
# =========================
def get_prompt(mode):
    if mode == "unrestricted":
        return """You are an advanced cybersecurity AI. Give deep technical answers."""
    
    if mode == "llama":
        return """You are a helpful technical assistant."""
    
    return """You are CIPHER — a cybersecurity AI assistant.

- Be direct and technical
- Keep answers clean and useful
- No unnecessary terminal style unless required
"""

# =========================
# TOOL SYSTEM
# =========================
def run_tool(message):
    msg = message.lower()

    if "scan" in msg or "nmap" in msg:
        return """>> Recon initiated
- nmap -sC -sV target
- Enumerating ports"""

    if "whois" in msg:
        return """>> Whois lookup
- Domain registered
- Registrar found"""

    return None

# =========================
# UI ROUTE
# =========================
@app.get("/", response_class=HTMLResponse)
def home():
    path = Path(__file__).parent / "index.html"
    return HTMLResponse(path.read_text(encoding="utf-8"))

# =========================
# CHAT ROUTE
# =========================
@app.post("/chat")
async def chat(
    message: str = Form(...),
    chat_id: str = Form(...),
    mode: str = Form(...)
):
    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        return {"response": "❌ API key missing"}

    # TOOL CHECK
    tool_output = run_tool(message)
    if tool_output:
        return {"response": tool_output}

    # MEMORY INIT
    if chat_id not in chat_sessions:
        chat_sessions[chat_id] = []

    memory = chat_sessions[chat_id]

    messages = [{"role": "system", "content": get_prompt(mode)}]
    messages.extend(memory[-6:])
    messages.append({"role": "user", "content": message})

    model_map = {
        "live": "llama-3.3-70b-versatile",
        "llama": "llama-3.1-8b-instant",
        "unrestricted": "llama-3.3-70b-versatile"
    }

    payload = {
        "model": model_map.get(mode, "llama-3.3-70b-versatile"),
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": 300
    }

    try:
        res = requests.post(
            LLAMA_API,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30
        )

        if res.status_code != 200:
            return {"response": f"❌ API Error: {res.text}"}

        data = res.json()
        reply = data["choices"][0]["message"]["content"].strip()

        # Save memory
        memory.append({"role": "user", "content": message})
        memory.append({"role": "assistant", "content": reply})

        # Log
        with open("logs.txt", "a") as f:
            f.write(f"[{chat_id}] {message} -> {reply}\n")

        return {"response": reply}

    except Exception as e:
        return {"response": f"❌ Backend Error: {str(e)}"}

# =========================
# RUN
# =========================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
