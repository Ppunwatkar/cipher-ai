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
# HEALTH CHECK
# =========================
@app.get("/ping")
def ping():
    return {"status": "alive"}

# =========================
# CHAT ROUTE (AI ENABLED)
# =========================
@app.post("/chat")
def chat(message: str = Form(...), chat_id: str = Form(...), mode: str = Form(...)):
    try:
        print("🔥 CHAT HIT:", message)

        # 🔐 GET API KEY
        api_key = os.environ.get("OPENROUTER_API_KEY")

        if not api_key:
            return {"response": "❌ Missing OpenRouter API key"}

        # 🧠 MODE → MODEL
        if mode == "thinking":
            model = "deepseek/deepseek-chat"
        elif mode == "fast":
            model = "mistralai/mistral-7b-instruct"
        elif mode == "programming":
            model = "deepseek/deepseek-coder"
        else:
            model = "deepseek/deepseek-chat"

        # 🧠 SYSTEM PROMPT
        system_prompt = """
You are CIPHER AI — an elite cybersecurity assistant.

You specialize in:
- penetration testing
- vulnerability analysis
- exploit development
- CTF solving
- recon techniques

Give precise, technical, real-world answers.
"""

        # 🌐 API CALL
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
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

        # 🛑 ERROR HANDLING
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
