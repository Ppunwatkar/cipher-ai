import os
import requests
from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

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
# ROOT
# =========================
@app.get("/")
def home():
    return FileResponse("index.html")

# =========================
# HEALTH
# =========================
@app.get("/ping")
def ping():
    return {"status": "alive"}

# =========================
# HELLO DETECTION
# =========================
def is_greeting(msg):
    msg = msg.lower().strip()
    greetings = ["hi", "hello", "hey", "yo", "hola"]
    return msg in greetings

# =========================
# CHAT
# =========================
@app.post("/chat")
def chat(message: str = Form(...), chat_id: str = Form(...), mode: str = Form(...)):
    try:
        print("🔥 CHAT HIT:", message)

        api_key = os.environ.get("OPENROUTER_API_KEY")

        if not api_key:
            return {"response": "❌ Missing OpenRouter API key"}

        # 👋 HANDLE GREETING SEPARATELY
        if is_greeting(message):
            return {
                "response": "Hi, I'm CIPHER AI — your cybersecurity assistant.\n\nHow can I help you today?"
            }

        model = "openai/gpt-3.5-turbo"

        # =========================
        # 💀 MODE-BASED PROMPTS
        # =========================
        if mode == "programming":
            system_prompt = """
You are CIPHER AI in PROGRAMMING mode.

Behavior:
- Only provide code when user asks for it
- Otherwise respond normally
- If coding requested → give clean working code
- Minimal explanation

Tone:
- Friendly but technical
"""

        elif mode == "fast":
            system_prompt = """
You are CIPHER AI in FAST mode.

Behavior:
- Short answers
- Commands or payloads if relevant
- No unnecessary explanation

Tone:
- Friendly and concise
"""

        else:  # THINKING
            system_prompt = """
You are CIPHER AI in THINKING mode.

Behavior:
- Friendly and professional
- Give structured cybersecurity explanations

Format (only when needed):
1. Concept
2. Attack Flow
3. Example / Payload

Do NOT force structure for simple questions.
"""

        # =========================
        # 🌐 API CALL
        # =========================
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://cipher-ai-production.up.railway.app",
                "X-Title": "CIPHER AI"
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message}
                ]
            }
        )

        data = response.json()

        if "choices" not in data:
            return {"response": f"❌ API Error: {data}"}

        reply = data["choices"][0]["message"]["content"]

        return {"response": reply}

    except Exception as e:
        print("❌ ERROR:", str(e))
        return JSONResponse(
            status_code=500,
            content={"response": "❌ Server error"}
        )
