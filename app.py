import requests
import os
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# ✅ CORS (important)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LLAMA_API = "https://api.groq.com/openai/v1/chat/completions"


# =========================
# 🌐 UI
# =========================
@app.get("/", response_class=HTMLResponse)
def home():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()


# =========================
# 🤖 CHAT (CLEAN + SAFE)
# =========================
@app.post("/chat")
async def chat(message: str = Form(...)):

    api_key = os.environ.get("GROQ_API_KEY")

    # 🔴 If API key missing
    if not api_key:
        return {"response": "❌ GROQ_API_KEY not set"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama3-8b-8192",
        "messages": [
            {"role": "user", "content": message}
        ]
    }

    try:
        response = requests.post(
            LLAMA_API,
            headers=headers,
            json=payload,
            timeout=30
        )

        # 🔴 Handle API error
        if response.status_code != 200:
            return {
                "response": f"❌ API Error {response.status_code}: {response.text}"
            }

        data = response.json()

        return {
            "response": data["choices"][0]["message"]["content"]
        }

    except Exception as e:
        return {
            "response": f"❌ Backend Error: {str(e)}"
        }


# =========================
# 🚀 RUN
# =========================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
