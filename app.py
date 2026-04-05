import base64
import os
import shutil
import requests
from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from pypdf import PdfReader

app = FastAPI()

# ✅ USE CLOUD (GROQ)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

knowledge_base = ""

# ---------------- UI ----------------
@app.get("/", response_class=HTMLResponse)
def home():
    return "<h1>CIPHER AI RUNNING ✅</h1>"

# ---------------- FILE UPLOAD ----------------
@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    global knowledge_base
    filepath = os.path.join(UPLOAD_DIR, file.filename)

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    reader = PdfReader(filepath)
    text = f"\n--- FROM DOCUMENT: {file.filename} ---\n"

    for page in reader.pages:
        text += page.extract_text() or ""

    knowledge_base += text
    return {"status": "Knowledge absorbed"}

# ---------------- CHAT ----------------
@app.post("/chat")
async def chat(message: str = Form(...), image: UploadFile = File(None)):

    img_content = None

    if image:
        content = await image.read()
        img_content = {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64.b64encode(content).decode()}"
            }
        }

    # SYSTEM PROMPT
    system_prompt = f"""
You are CIPHER AI — a cybersecurity research assistant.

Use this knowledge:
{knowledge_base}
"""

    # MESSAGE STRUCTURE
    content = [{"type": "text", "text": message}]
    if img_content:
        content.append(img_content)

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama3-8b-8192",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content}
                ],
                "temperature": 0.4
            }
        )

        result = response.json()
        reply = result["choices"][0]["message"]["content"]

    except Exception as e:
        reply = f"ERROR: {str(e)}"

    return JSONResponse({"reply": reply})
