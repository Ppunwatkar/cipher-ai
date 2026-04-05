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
<link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@300;500&display=swap" rel="stylesheet">

<style>
body { background-color: #06090f; font-family: 'Fira Code', monospace; color: #c9d1d9; }
.cyber-border { border: 1px solid #161b22; }
.neon-text { color: #00f2ff; text-shadow: 0 0 10px rgba(0, 242, 255, 0.3); }
.sidebar { background-color: #0d1117; width: 300px; border-right: 1px solid #30363d; }
.terminal-header { background-color: #161b22; border-bottom: 1px solid #30363d; }
.bot-msg { background: rgba(13, 17, 23, 0.8); border: 1px solid #21262d; border-left: 4px solid #00f2ff; }
.user-msg { background: #161b22; border: 1px solid #30363d; color: #58a6ff; }
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-thumb { background: #30363d; border-radius: 10px; }
</style>
</head>

<body class="h-screen flex overflow-hidden">

<aside class="sidebar flex flex-col p-6 space-y-8">
<div>
<h1 class="text-2xl font-bold neon-text">CIPHER</h1>
<p class="text-[9px] text-gray-500 uppercase">Cybersecurity AI</p>
</div>
</aside>

<main class="flex-1 flex flex-col">

<header class="terminal-header h-12 flex items-center px-6">
RESEARCH TERMINAL
</header>

<div id="chat-container" class="flex-1 overflow-y-auto p-8 space-y-6">
<div class="text-cyan-500 text-xs italic">Ready. Enter query.</div>
</div>

<div class="p-6 border-t border-[#30363d]">
<div class="max-w-5xl mx-auto flex items-center space-x-4">

<div class="flex-1 relative flex items-center">
<span class="absolute left-4 text-cyan-500">></span>

<input id="msg-input"
class="w-full bg-[#06090f] border border-[#30363d] rounded-md pl-10 pr-4 py-3 text-sm"
placeholder="Ask..."
onkeypress="if(event.key==='Enter') sendQuery()">

<input type="file" id="img-upload" class="hidden" accept="image/*">

<button onclick="document.getElementById('img-upload').click()"
class="absolute right-4 text-gray-500">+</button>
</div>

<button onclick="sendQuery()" class="px-6 py-3 border">
Send ►
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

    chat.innerHTML += `<div class="flex justify-end">
        <div class="user-msg px-4 py-2 rounded text-xs">${message}</div>
    </div>`;

    const botDiv = document.createElement("div");
    botDiv.className = "bot-msg p-4 rounded-lg text-sm max-w-5xl";
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

    system_prompt = f"You are CIPHER AI. Use knowledge: {knowledge_base}"

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
                    yield chunk["choices"][0]["delta"].get("content", "")
                except:
                    pass

    return StreamingResponse(stream(), media_type="text/plain")
