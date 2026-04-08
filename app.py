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

GROQ_API = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_API = "https://openrouter.ai/api/v1/chat/completions"

chat_sessions = {}

# =========================
# PROMPTS
# =========================
def get_prompt(mode):
    if mode == "llama":
        return "You are a fast and concise AI assistant."

    if mode == "unrestricted":
        return "You are a creative cybersecurity AI. Brainstorm ideas freely."

    return """You are CIPHER — a cybersecurity AI assistant.
Give clear, structured, and intelligent responses.
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
# UI
# =========================
@app.get("/", response_class=HTMLResponse)
def home():
    path = Path(__file__).parent / "index.html"
    return HTMLResponse(path.read_text(encoding="utf-8"))

# =========================
# CHAT
# =========================
@app.post("/chat")
async def chat(
    message: str = Form(...),
    chat_id: str = Form(...),
    mode: str = Form(...)
):

    # TOOL CHECK
    tool_output = run_tool(message)
    if tool_output:
        return {"response": tool_output}

    # MEMORY INIT
    if chat_id not in chat_sessions:
        chat_sessions[chat_id] = []

    memory = chat_sessions[chat_id]

    # =====================
    # 🔴 BRAINSTORM → DOLPHIN
    # =====================
    if mode == "unrestricted":

        api_key = os.environ.get("OPENROUTER_API_KEY")

        if not api_key:
            return {"response": "❌ Missing OpenRouter API key"}

        try:
            res = requests.post(
                OPENROUTER_API,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "dolphin-2.9-llama3",
                    "messages": [
                        {"role": "user", "content": message}
                    ]
                },
                timeout=30
            )

            if res.status_code != 200:
                return {"response": f"❌ Dolphin HTTP Error: {res.text}"}

            data = res.json()

            if "error" in data:
                return {"response": f"❌ Dolphin API Error: {data['error']['message']}"}

            reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            if not reply:
                reply = "⚠️ Empty response from Dolphin"

        except Exception as e:
            reply = f"❌ Dolphin backend error: {str(e)}"

        memory.append({"role": "user", "content": message})
        memory.append({"role": "assistant", "content": reply})

        return {"response": reply}

    # =====================
    # 🟢 GROQ (THINKING + FAST)
    # =====================
    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        return {"response": "❌ Missing GROQ API key"}

    messages = [{"role": "system", "content": get_prompt(mode)}]
    messages.extend(memory[-6:])
    messages.append({"role": "user", "content": message})

    model_map = {
        "live": "llama-3.3-70b-versatile",
        "llama": "llama-3.1-8b-instant"
    }

    payload = {
        "model": model_map.get(mode, "llama-3.3-70b-versatile"),
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": 400
    }

    try:
        res = requests.post(
            GROQ_API,
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

        memory.append({"role": "user", "content": message})
        memory.append({"role": "assistant", "content": reply})

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
