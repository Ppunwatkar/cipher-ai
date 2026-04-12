import os
import requests
from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ROOT
@app.get("/")
def home():
    return FileResponse("index.html")

# HEALTH
@app.get("/ping")
def ping():
    return {"status": "alive"}

# CHAT
@app.post("/chat")
def chat(message: str = Form(...), chat_id: str = Form(...), mode: str = Form(...)):
    try:
        print("🔥 CHAT HIT:", message)

        api_key = os.environ.get("OPENROUTER_API_KEY")

        if not api_key:
            return {"response": "❌ Missing OpenRouter API key"}

        # ✅ SINGLE STABLE MODEL
        model = "mistralai/mistral-7b-instruct"

        # =========================
        # 🧠 MODE-BASED PROMPT
        # =========================
        if mode == "programming":
            system_prompt = """
You are CIPHER AI in PROGRAMMING mode.

You are an expert hacker and developer.
- Always return clean working code
- Use proper formatting
- Add explanation only if needed
- Focus on exploit scripts, automation, tools
"""
        elif mode == "fast":
            system_prompt = """
You are CIPHER AI in FAST mode.

- Give short, direct answers
- No unnecessary explanation
"""
        else:
            system_prompt = """
You are CIPHER AI — elite cybersecurity assistant.

- Give deep, technical explanations
- Focus on pentesting, vulnerabilities, CTFs
"""

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

        if "choices" not in data:
            return {"response": f"❌ API Error: {data.get('error', data)}"}

        reply = data["choices"][0]["message"]["content"]

        return {"response": reply}

    except Exception as e:
        print("❌ ERROR:", str(e))
        return JSONResponse(
            status_code=500,
            content={"response": "❌ Server error"}
        )
