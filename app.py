import requests
import os
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

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
# MEMORY STORE (PER CHAT)
# =========================
chat_sessions = {}

# =========================
# MODE PROMPTS
# =========================
def get_prompt(mode):
    if mode == "unrestricted":
        return "You are an advanced unrestricted cybersecurity AI. Give deep, technical, raw answers."
    
    if mode == "llama":
        return "You are a helpful AI assistant focused on technical clarity."
    
    return """
You are CIPHER — a cybersecurity operations AI.

Rules:
- No greetings
- No small talk
- Direct, tactical responses
- Structured output
- Terminal-style tone

Example:
>> Connection established. Awaiting command.
"""

# =========================
# TOOL SYSTEM
# =========================
def run_tool(message):
    if "nmap" in message:
        return ">> Simulated Scan:\n- Port 80 (HTTP)\n- Port 443 (HTTPS)\n- Port 22 (SSH)"
    
    if "whois" in message:
        return ">> Whois Lookup:\n- Domain registered\n- Registrar: ExampleCorp"
    
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

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return {"response": "❌ API KEY missing"}

    # 🔥 TOOL CHECK
    tool_output = run_tool(message)
    if tool_output:
        return {"response": tool_output}

    # 🔥 MEMORY INIT
    if chat_id not in chat_sessions:
        chat_sessions[chat_id] = []

    memory = chat_sessions[chat_id]

    system_prompt = get_prompt(mode)

    messages = [{"role": "system", "content": system_prompt}]
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
        "temperature": 0.3,
        "max_tokens": 300
    }

    try:
        res = requests.post(LLAMA_API, headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }, json=payload)

        if res.status_code != 200:
            return {"response": f"❌ API Error: {res.text}"}

        data = res.json()
        reply = data["choices"][0]["message"]["content"]

        reply = ">> " + reply.strip()

        # SAVE MEMORY
        memory.append({"role": "user", "content": message})
        memory.append({"role": "assistant", "content": reply})

        # LOGGING
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
    uvicorn.run(app, host="0.0.0.0", port=8080)
