import base64
import os
import shutil
import requests
from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from pypdf import PdfReader

app = FastAPI()

# 🔑 API KEY (from Railway env)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

knowledge_base = ""

# ---------------- UI ----------------
@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html>
<head>
<title>CIPHER AI</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
body { background: #06090f; color: #00f2ff; font-family: monospace; }
</style>
</head>

<body class="p-6">

<h1 class="text-xl mb-4">CIPHER AI TERMINAL</h1>

<div id="chat" class="mb-4"></div>

<input id="msg" class="w-full p-2 text-black" placeholder="Ask anything..." />
<br><br>

<input type="file" id="img" />
<br><br>

<button onclick="send()" class="bg-cyan-500 px-4 py-2">Send</button>

<script>
async function send() {
    let msg = document.getElementById("msg").value;
    let img = document.getElementById("img").files[0];

    let formData = new FormData();
    formData.append("message", msg);
    if (img) formData.append("image", img);

    let res = await fetch("/chat", {
        method: "POST",
        body: formData
    });

    let data = await res.json();

    document.getElementById("chat").innerHTML += `
        <p>> ${msg}</p>
        <p>${data.reply}</p><hr>
    `;
}
</script>

</body>
</html>
"""
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
    import base64
    import requests
    import os

    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

    if not GROQ_API_KEY:
        return {"reply": "❌ ERROR: API key missing"}

    content = [{"type": "text", "text": message}]

    # 👁️ Vision support
    if image:
        img_bytes = await image.read()
        img_b64 = base64.b64encode(img_bytes).decode()

        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img_b64}"
            }
        })

    system_prompt = f"""
You are CIPHER AI — an advanced cybersecurity assistant.

Use this knowledge if available:
{knowledge_base}

Be technical, clear, and helpful.
"""

    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",  # ✅ WORKING MODEL
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content}
                ],
                "temperature": 0.4
            }
        )

        data = response.json()

        if "choices" not in data:
            return {"reply": f"❌ API ERROR: {data}"}

        reply = data["choices"][0]["message"]["content"]

    except Exception as e:
        return {"reply": f"❌ SERVER ERROR: {str(e)}"}

    return {"reply": reply}
