import requests
import json
import os
from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse

app = FastAPI()

LLAMA_API = "https://api.groq.com/openai/v1/chat/completions"

# =========================
# 🌐 UI
# =========================
@app.get("/", response_class=HTMLResponse)
def home():
    return open("index.html").read()


# =========================
# 🤖 CHAT (FIXED)
# ========================
@app.post("/chat")
async def chat(message: str = Form(...)):

    headers = {
        "Authorization": f"Bearer {os.environ.get('GROQ_API_KEY')}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama3-8b-8192",
        "messages": [
            {"role": "user", "content": message}
        ]
    }

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload
    )

    data = response.json()

    return {
        "response": data["choices"][0]["message"]["content"]
    }

    def stream():
        try:
            response = requests.post(
                LLAMA_API,
                headers=headers,
                json=payload,
                stream=True,
                timeout=60
            )

            # 🔥 SHOW ERROR IF API FAILS
            if response.status_code != 200:
                yield f"❌ API Error {response.status_code}: {response.text}"
                return

            full_text = ""

            for line in response.iter_lines():
                if not line:
                    continue

                decoded = line.decode("utf-8")

                # remove "data: "
                if decoded.startswith("data: "):
                    decoded = decoded[6:]

                if decoded.strip() == "[DONE]":
                    break

                try:
                    data = json.loads(decoded)

                    delta = data.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content")

                    if content:
                        full_text += content
                        yield content

                except Exception:
                    yield f"\n⚠️ Parse Error: {decoded}\n"

            # 🔥 FALLBACK (IMPORTANT)
            if not full_text:
                yield "⚠️ No response from model. Check API key / model."

        except Exception as e:
            yield f"❌ Backend Error: {str(e)}"

    return StreamingResponse(stream(), media_type="text/plain")


# =========================
# 🚀 RUN (RAILWAY SAFE)
# =========================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
