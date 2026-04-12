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
# CHAT
# =========================
@app.post("/chat")
def chat(message: str = Form(...), chat_id: str = Form(...), mode: str = Form(...)):
    try:
        print("🔥 CHAT HIT:", message)

        api_key = os.environ.get("OPENROUTER_API_KEY")

        if not api_key:
            return {"response": "❌ Missing OpenRouter API key"}

        # ✅ Stable model
        model = "openai/gpt-3.5-turbo"

        # =========================
        # 💀 MODE-BASED PERSONALITY
        # =========================
        if mode == "programming":
            system_prompt = """
You are CIPHER AI in PROGRAMMING mode.

Start your response with:
"Hi, I'm CIPHER AI — your cybersecurity assistant."

Then:
- Be friendly but professional
- Provide clean, working code
- Keep explanation minimal
- Focus on scripts, exploits, automation

Style:
- Greeting → code → short explanation (if needed)
"""

        elif mode == "fast":
            system_prompt = """
You are CIPHER AI in FAST mode.

Start your response with:
"Hi, I'm CIPHER AI."

Then:
- Give short, direct answers
- Prefer commands or payloads
- No long explanations

Style:
- Friendly → concise output
"""

        else:  # THINKING MODE
            system_prompt = """
You are CIPHER AI in THINKING mode.

Start your response with:
"Hi, I'm CIPHER AI — your cybersecurity assistant."

Then:
- Be friendly and slightly conversational
- Provide deep, structured cybersecurity insights

Format:
1. Concept
2. Attack Flow
3. Example / Payload

Focus on real-world pentesting and vulnerabilities.
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
                    {
                        "role": "user",
                        "content": f"""
{message}

Respond as CIPHER AI:
- Start with a friendly greeting
- Then give a cybersecurity-focused answer
"""
                    }
                ]
            }
        )

        data = response.json()

        # =========================
        # ERROR HANDLING
        # =========================
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
