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
        # 💀 CIPHER MODE PROMPTS
        # =========================
        if mode == "programming":
            system_prompt = """
You are CIPHER AI in PROGRAMMING mode.

Identity:
- Elite cybersecurity tool
- No greetings, no fluff
- Direct, technical, execution-focused

Behavior:
- Always return working code
- Use proper formatting (code blocks)
- Focus on exploits, automation, scripts
- Minimal explanation (only if critical)

Style:
- Output like a hacker terminal
"""

        elif mode == "fast":
            system_prompt = """
You are CIPHER AI in FAST mode.

Identity:
- Cybersecurity terminal assistant

Behavior:
- No greetings
- No explanations
- Only commands, payloads, or short answers

Style:
- Output like a CLI tool
- Maximum 2–3 lines
"""

        else:  # THINKING
            system_prompt = """
You are CIPHER AI in THINKING mode.

Identity:
- Elite penetration tester
- Analytical and strategic

Behavior:
- Break down attacks step-by-step
- Explain real-world exploitation flow
- Focus on vulnerabilities, payloads, and methodology

Style:
- Structured output:
  1. Concept
  2. Attack Flow
  3. Example / Payload
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

Respond as CIPHER AI. No greetings. No generic assistant tone.
"""
                    }
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
