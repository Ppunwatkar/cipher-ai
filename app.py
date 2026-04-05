import base64
import os
import shutil
import requests
import json
from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from pypdf import PdfReader

app = FastAPI()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

knowledge_base = ""

# ---------------- UI ----------------
@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CIPHER // RESEARCH TERMINAL</title>

<script src="https://cdn.tailwindcss.com"></script>

<style>
body { background-color: #06090f; color: #c9d1d9; font-family: monospace; }
.sidebar { background-color: #0d1117; border-right: 1px solid #30363d; }
.bot-msg { background: #0d1117; border-left: 4px solid #00f2ff; }
.user-msg { background: #161b22; color: #58a6ff; }
</style>
</head>

<body class="min-h-screen flex flex-col md:flex-row">

<aside class="sidebar p-4 w-full md:w-[280px]">
<h1 class="text-cyan-400 text-lg">CIPHER</h1>
</aside>

<main class="flex-1 flex flex-col">

<div id="chat-container" class="flex-1 overflow-y-auto p-4 space-y-4"></div>

<div class="p-4 border-t border-gray-800">
<div class="flex flex-col md:flex-row gap-2">

<input id="msg-input" class="flex-1 p-2 text-black" placeholder="Ask...">

<input type="file" id="img-upload">

<button onclick="sendQuery()" class="bg-cyan-500 px-4 py-2">
Send
</button>

</div>
</div>

</main>

<script>

async function sendQuery() {
    const input = document.getElementById('msg-input');
    const chat = document.getElementById('chat-container');
    const imgInput = document.getElementById('img-upload');

    const message = input.value;
    if (!message && !imgInput.files[0]) return;

    chat.innerHTML += `<div class="text-right user-msg p-2 rounded">${message}</div>`;

    const botDiv = document.createElement("div");
    botDiv.className = "bot-msg p-3 rounded";
    botDiv.innerHTML = `<div id="streaming"></div>`;
    chat.appendChild(botDiv);

    const formData = new FormData();
    formData.append('message', message);
    if (imgInput.files[0]) formData.append('image', imgInput.files[0]);

    input.value = "";
    imgInput.value = "";

    const res = await fetch('/chat', { method: 'POST', body: formData });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();

    let fullText = "";

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        fullText += chunk;

        document.getElementById("streaming").innerHTML = formatResponse(fullText);
        chat.scrollTop = chat.scrollHeight;
    }
}

function formatResponse(text) {
    const codeRegex = /```([\\s\\S]*?)```/g;

    return text.replace(codeRegex, (match, code) => {
        const escaped = code.replace(/</g, "&lt;").replace(/>/g, "&gt;");
        return `
        <div class="bg-black border border-cyan-800 rounded p-3 my-2 relative">
            <button onclick="copyCode(this)" 
                class="absolute top-2 right-2 text-xs bg-cyan-800 px-2 py-1">
                Copy
            </button>
            <pre class="text-xs text-green-400 overflow-x-auto">${escaped}</pre>
        </div>
        `;
    });
}

function copyCode(btn) {
    const code = btn.parentElement.querySelector("pre").innerText;
    navigator.clipboard.writeText(code);
    btn.innerText = "Copied!";
    setTimeout(() => btn.innerText = "Copy", 1500);
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

# ---------------- CHAT (STREAMING) ----------------
@app.post("/chat")
async def chat(message: str = Form(...), image: UploadFile = File(None)):

    content = [{"type": "text", "text": message}]

    if image:
        img_bytes = await image.read()
        img_b64 = base64.b64encode(img_bytes).decode()
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
        })

    system_prompt = f"""
You are CIPHER AI — cybersecurity assistant.
Use this knowledge:
{knowledge_base}
"""

    def stream():
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content}
                ],
                "stream": True
            },
            stream=True
        )

        for line in response.iter_lines():
            if line:
                try:
                    decoded = line.decode().replace("data: ", "")
                    if decoded == "[DONE]":
                        break
                    chunk = json.loads(decoded)
                    token = chunk["choices"][0]["delta"].get("content", "")
                    yield token
                except:
                    pass

    return StreamingResponse(stream(), media_type="text/plain")
