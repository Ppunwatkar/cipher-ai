import requests
import os
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

app = FastAPI()

# =========================
 CORS
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
        return """
You are an advanced cybersecurity AI.

- Provide deep technical answers
- No unnecessary explanations
- Focus on practical attack/defense concepts
"""

    if mode == "llama":
        return """
You are a helpful AI assistant with strong technical knowledge.
Explain clearly and concisely.
"""

    return """
You are CIPHER — a cybersecurity AI assistant.

CORE BEHAVIOR:
- You are a chatbot first, not a command terminal
- Respond naturally but with a cyber-intelligent tone
- Be direct, technical, and useful
- Avoid robotic/system-like responses unless required

STYLE:
- Clear answers
- Slight hacker tone (subtle, not overdone)
- No forced command lists

COMMAND MODE (IMPORTANT):
- Only use command-style output IF user explicitly asks for:
  - scanning
  - recon
  - exploitation
  - tools

Example:
User: hi
Response:
CIPHER online. What's the objective?

User: what is CTF
Response:
CTF (Capture The Flag) is a cybersecurity challenge where participants exploit systems, solve crypto, or reverse binaries to retrieve flags.

User: scan a target
Response:
>> Initiating recon...
- nmap -sC -sV <target>
- Identify open ports and services

DO NOT default to command interface.
"""
# =========================
# TOOL SYSTEM
# =========================
def run_tool(message):
    msg = message.lower()

    if "scan" in msg or "nmap" in msg:
        return """>> Recon initiated
- nmap -sC -sV target
- Enumerating open ports
"""

    if "whois" in msg:
        return """>> Whois lookup
- Domain registered
- Registrar info found
"""

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
