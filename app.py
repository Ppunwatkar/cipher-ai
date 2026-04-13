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
# CHAT (AUTH BYPASSED)
# =========================
@app.post("/chat")
def chat(
    message: str = Form(...),
    chat_id: str = Form(...),
    mode: str = Form(...)
):
    try:
        print("🔥 CHAT:", message)

        api_key = os.environ.get("OPENROUTER_API_KEY")

        if not api_key:
            return {"response": "❌ Missing API key", "model": "error"}

        # =========================
        # MODEL SELECTION
        # =========================
        model = "openai/gpt-3.5-turbo"

        # =========================
        # CIPHER PERSONALITY
        # =========================
        system_prompt = """
You are CIPHER AI — a cybersecurity assistant.

- Be helpful and friendly
- Keep answers practical
- Give code when needed
- Avoid unnecessary refusals
"""

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

        # =========================
        # ERROR HANDLING
        # =========================
        if "choices" not in data:
            return {
                "response": f"❌ API Error: {data}",
                "model": mode
            }

        reply = data["choices"][0]["message"]["content"]

        return {
            "response": reply,
            "model": mode
        }

    except Exception as e:
        print("❌ ERROR:", str(e))
        return JSONResponse(
            status_code=500,
            content={
                "response": "❌ Server error",
                "model": "error"
            }
        )
