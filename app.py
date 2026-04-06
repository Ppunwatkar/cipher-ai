import base64
import requests
import json
from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse

app = FastAPI()

LLAMA_API = "http://localhost:8080/v1/chat/completions"

@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>CIPHER AI v2</title>

<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@300;500&display=swap" rel="stylesheet">

<style>
body {
    background:#05080e;
    font-family:'Fira Code', monospace;
    color:#c9d1d9;
}

/* GRID BACKGROUND */
body::before {
    content:"";
    position:fixed;
    width:100%;
    height:100%;
    background-image: linear-gradient(rgba(0,255,255,0.03) 1px, transparent 1px),
                      linear-gradient(90deg, rgba(0,255,255,0.03) 1px, transparent 1px);
    background-size: 40px 40px;
    z-index:-1;
}

/* SIDEBARS */
.sidebar { width:240px; background:#0d1117; border-right:1px solid #30363d; }
.tools { width:220px; background:#0d1117; border-left:1px solid #30363d; }

/* TEXT */
.neon { color:#00f2ff; text-shadow:0 0 10px rgba(0,242,255,0.6); }

/* MESSAGES */
.bot-msg { background:#0d1117; border-left:3px solid #00f2ff; padding:10px; }
.user-msg { background:#161b22; color:#58a6ff; padding:8px; }

/* CODE */
.code { background:black; border:1px solid cyan; padding:10px; margin-top:10px; position:relative; }
.copy { position:absolute; right:10px; top:5px; font-size:10px; }

/* CHAT LIST */
.chat-item { cursor:pointer; padding:6px; border-radius:4px; }
.chat-item:hover { background:#161b22; }

/* TOOL BUTTON */
.tool-btn { background:#161b22; border:1px solid #30363d; padding:5px; font-size:11px; width:100%; margin-top:5px; }
.tool-btn:hover { background:#1f2937; }

/* IMAGE */
.preview { max-height:120px; margin-top:5px; border:1px solid #30363d; }
</style>
</head>

<body class="flex h-screen overflow-hidden">

<!-- LEFT SIDEBAR -->
<div class="sidebar p-4 flex flex-col">
<h2 class="neon text-sm mb-4">CHATS</h2>
<button onclick="createNewChat()" class="tool-btn">+ New Chat</button>
<div id="chatList" class="mt-3 text-xs overflow-y-auto"></div>
</div>

<!-- MAIN -->
<div class="flex-1 flex flex-col">

<div class="p-3 border-b border-gray-700 text-xs flex justify-between">
<span class="neon">CIPHER TERMINAL</span>
<span class="text-green-400">LIVE</span>
</div>

<div id="chat" class="flex-1 overflow-y-auto p-6 space-y-4"></div>

<div class="p-4 border-t border-gray-700 flex gap-2">
<input id="msg" class="flex-1 bg-black border px-3 py-2 text-sm"
placeholder="Type command..."
onkeypress="if(event.key==='Enter') send()">

<input type="file" id="img" class="hidden" accept="image/*">

<button onclick="document.getElementById('img').click()" class="border px-3">+</button>
<button onclick="send()" class="border px-4">Send</button>
</div>

</div>

<!-- RIGHT PANEL -->
<div class="tools p-4 text-xs">
<h2 class="neon mb-3">TOOLS</h2>

<button class="tool-btn" onclick="quick('Run nmap scan on target')">NMAP</button>
<button class="tool-btn" onclick="quick('Perform SQL injection test')">SQLMAP</button>
<button class="tool-btn" onclick="quick('Do reconnaissance on domain')">RECON</button>
<button class="tool-btn" onclick="quick('Find vulnerabilities in system')">SCAN</button>
</div>

<script>

// 🧠 STATE
let chats = {};
let currentChat = null;

// 🚀 INIT
function init() {
    createNewChat();
}

// 🆕 NEW CHAT
function createNewChat() {
    currentChat = "chat_" + Date.now();
    chats[currentChat] = [];
    renderChatList();
    renderMessages();
}

// 📜 CHAT LIST
function renderChatList() {
    const list = document.getElementById("chatList");
    list.innerHTML = "";

    Object.keys(chats).forEach(id => {
        const el = document.createElement("div");
        el.className = "chat-item";
        el.innerText = id;

        el.onclick = () => {
            currentChat = id;
            renderMessages();
        };

        list.appendChild(el);
    });
}

// 💬 RENDER
function renderMessages() {
    const chat = document.getElementById("chat");
    chat.innerHTML = "";

    if (!chats[currentChat]) return;

    chats[currentChat].forEach(msg => {
        const wrap = document.createElement("div");
        wrap.className = msg.role === "user" ? "text-right" : "";

        const bubble = document.createElement("div");
        bubble.className = msg.role === "user"
            ? "user-msg inline-block px-3 py-2"
            : "bot-msg";

        bubble.innerHTML = msg.content;
        wrap.appendChild(bubble);
        chat.appendChild(wrap);
    });

    scrollBottom();
}

// ⚡ TOOL
function quick(text) {
    document.getElementById("msg").value = text;
}

// 🚀 SEND
async function send() {
    const input = document.getElementById("msg");
    const img = document.getElementById("img");
    const chatBox = document.getElementById("chat");

    if (!input.value && !img.files[0]) return;

    if (!currentChat) createNewChat();

    let userHTML = input.value;

    if (img.files[0]) {
        const preview = URL.createObjectURL(img.files[0]);
        userHTML += `<br><img src="${preview}" class="preview">`;
    }

    chats[currentChat].push({ role: "user", content: userHTML });
    renderMessages();

    const wrap = document.createElement("div");
    const bubble = document.createElement("div");
    bubble.className = "bot-msg";

    const stream = document.createElement("div");
    bubble.appendChild(stream);
    wrap.appendChild(bubble);
    chatBox.appendChild(wrap);

    scrollBottom();

    const form = new FormData();
    form.append("message", input.value);
    if (img.files[0]) form.append("image", img.files[0]);

    input.value = "";
    img.value = "";

    const res = await fetch("/chat", { method: "POST", body: form });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();

    let text = "";

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        text += decoder.decode(value);
        stream.innerHTML = format(text);
        scrollBottom();
    }

    chats[currentChat].push({ role: "bot", content: text });
}

// 📜 FORMAT
function format(text) {
    return text.replace(/```([\\s\\S]*?)```/g, (_, code) => `
        <div class="code">
            <button class="copy" onclick="copy(this)">Copy</button>
            <pre>${escapeHTML(code)}</pre>
        </div>
    `);
}

// 📋 COPY
function copy(btn) {
    const code = btn.parentElement.querySelector("pre").innerText;
    navigator.clipboard.writeText(code);
    btn.innerText = "Copied";
}

// 🔐 ESCAPE
function escapeHTML(text) {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

// ⬇️ SCROLL
function scrollBottom() {
    const chat = document.getElementById("chat");
    chat.scrollTop = chat.scrollHeight;
}

// START
init();

</script>

</body>
</html>
"""

@app.post("/chat")
async def chat(message: str = Form(...), image: UploadFile = File(None)):

    img_b64 = ""
    if image:
        content = await image.read()
        img_b64 = base64.b64encode(content).decode("utf-8")

    payload = {
        "messages": [{
            "role": "user",
            "content": [{"type": "text", "text": message}]
        }],
        "temperature": 0.3,
        "stream": True
    }

    if img_b64:
        payload["messages"][0]["content"].append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
        })

    def stream():
        try:
            response = requests.post(LLAMA_API, json=payload, stream=True)
            for line in response.iter_lines():
                if line:
                    try:
                        decoded = line.decode()
                        if decoded.startswith("data: "):
                            decoded = decoded.replace("data: ", "")
                        if decoded == "[DONE]":
                            break
                        chunk = json.loads(decoded)
                        yield chunk["choices"][0]["delta"].get("content", "")
                    except:
                        pass
        except:
            yield "❌ Model not responding"

    return StreamingResponse(stream(), media_type="text/plain")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
