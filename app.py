import base64
import os
import shutil
import requests
from fastapi import FastAPI, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from pypdf import PdfReader

app = FastAPI()

# Configuration
LLAMA_API = "http://localhost:8082/v1/chat/completions"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Persistent State
knowledge_base = ""
stored_docs = []

@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
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
            <h1 class="text-2xl font-bold neon-text tracking-tighter">CIPHER</h1>
            <p class="text-[9px] text-gray-500 uppercase tracking-widest">Cybersecurity AI // Lab Mode</p>
        </div>

        <div class="space-y-4 text-[10px] uppercase">
            <div class="flex justify-between"><span>Local Engine</span><span class="text-green-500">● Active</span></div>
            <div class="flex justify-between"><span>Groq Cloud</span><span class="text-cyan-400">● Ready</span></div>
            <div class="flex justify-between"><span>Restrictions</span><span class="text-red-500">● None</span></div>
            <div class="flex justify-between"><span>Mode</span><span class="text-gray-400 font-bold">Auto-Route</span></div>
        </div>

        <div class="flex-1 flex flex-col">
            <label class="text-[10px] text-gray-500 uppercase mb-4 font-bold tracking-widest">Knowledge Base</label>
            <div id="drop-zone" class="border-2 border-dashed border-gray-800 rounded-lg p-8 flex flex-col items-center justify-center text-center cursor-pointer hover:border-cyan-900 transition-all">
                <svg class="h-8 w-8 text-gray-600 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" stroke-width="2"></path></svg>
                <p class="text-[10px] text-gray-500">DROP PDF / TXT / MD</p>
            </div>
            <input type="file" id="pdf-upload" class="hidden" onchange="uploadFile()">
            <button onclick="document.getElementById('pdf-upload').click()" class="mt-4 w-full py-2 border border-cyan-800 text-cyan-500 text-[10px] uppercase hover:bg-cyan-950">Upload & Store</button>
            
            <div class="mt-8">
                <label class="text-[10px] text-gray-500 uppercase font-bold tracking-widest">Stored Documents</label>
                <div id="doc-list" class="mt-4 space-y-2">
                    </div>
            </div>
        </div>
    </aside>

    <main class="flex-1 flex flex-col">
        <header class="terminal-header h-12 flex items-center px-6 justify-between">
            <div class="flex space-x-4 items-center">
                <span class="text-[10px] text-gray-500 font-bold">RESEARCH TERMINAL</span>
                <span class="text-[9px] border border-green-900 text-green-600 px-2 py-0.5 rounded">LAB-SCOPED</span>
                <span class="text-[9px] border border-cyan-900 text-cyan-600 px-2 py-0.5 rounded">LLAMA 3.1 8B</span>
                <span class="text-[9px] border border-pink-900 text-pink-600 px-2 py-0.5 rounded">UNRESTRICTED</span>
            </div>
        </header>

        <div id="chat-container" class="flex-1 overflow-y-auto p-8 space-y-6">
            <div class="text-cyan-500 text-xs italic">Ready. Enter query.</div>
        </div>

        <div class="p-6 bg-[#0d1117] border-t border-[#30363d]">
            <div class="max-w-5xl mx-auto flex items-center space-x-4">
                <div class="flex-1 relative flex items-center">
                    <span class="absolute left-4 text-cyan-500">></span>
                    <input type="text" id="msg-input" 
                           class="w-full bg-[#06090f] border border-[#30363d] rounded-md pl-10 pr-4 py-3 text-sm focus:outline-none focus:border-cyan-500" 
                           placeholder="Ask about exploits, malware, CTFs, payloads, recon..."
                           onkeypress="if(event.key === 'Enter') sendQuery()">
                    
                    <input type="file" id="img-upload" class="hidden" accept="image/*" onchange="previewImg()">
                    <button onclick="document.getElementById('img-upload').click()" class="absolute right-4 text-gray-500 hover:neon-text">
                        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 4v16m8-8H4" stroke-width="2"></path></svg>
                    </button>
                </div>
                <button onclick="sendQuery()" class="bg-[#161b22] border border-[#30363d] text-[10px] font-bold px-6 py-3 rounded hover:bg-cyan-950 hover:text-cyan-400 uppercase">Send ►</button>
            </div>
            <div id="img-label" class="hidden text-[9px] text-cyan-600 mt-2 ml-10 italic">SENSITIVE TOPICS → LOCAL MODEL</div>
        </div>
    </main>

    <script>
        async function uploadFile() {
            const file = document.getElementById('pdf-upload').files[0];
            const formData = new FormData();
            formData.append('file', file);
            
            const res = await fetch('/upload', { method: 'POST', body: formData });
            const data = await res.json();
            
            const docList = document.getElementById('doc-list');
            docList.innerHTML += `<div class="text-[10px] bg-[#161b22] p-2 rounded flex justify-between border border-gray-800">
                <span class="text-cyan-700">${file.name}</span>
                <span class="text-red-900 cursor-pointer">×</span>
            </div>`;
        }

        function previewImg() {
            document.getElementById('img-label').classList.remove('hidden');
        }

        async function sendQuery() {
            const input = document.getElementById('msg-input');
            const chat = document.getElementById('chat-container');
            const imgInput = document.getElementById('img-upload');
            const message = input.value;
            if (!message && !imgInput.files[0]) return;

            chat.innerHTML += `<div class="flex justify-end"><div class="user-msg px-4 py-2 rounded text-xs">${message}</div></div>`;
            
            const formData = new FormData();
            formData.append('message', message);
            if (imgInput.files[0]) formData.append('image', imgInput.files[0]);

            input.value = '';
            document.getElementById('img-label').classList.add('hidden');
            
            const res = await fetch('/chat', { method: 'POST', body: formData });
            const data = await res.json();

            chat.innerHTML += `
                <div class="bot-msg p-4 rounded-lg text-sm max-w-5xl">
                    <p class="text-[10px] text-green-500 font-bold mb-2 uppercase tracking-widest">CIPHER 🔒 Local (Private)</p>
                    <div class="leading-relaxed text-gray-300 whitespace-pre-wrap">${data.reply}</div>
                </div>`;
            chat.scrollTop = chat.scrollHeight;
            imgInput.value = '';
        }
    </script>
</body>
</html>
"""

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    global knowledge_base
    filepath = os.path.join(UPLOAD_DIR, file.filename)
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    reader = PdfReader(filepath)
    text = f"\\n--- FROM DOCUMENT: {file.filename} ---\\n"
    for page in reader.pages:
        text += page.extract_text() or ""
    knowledge_base += text
    return {"status": "Knowledge absorbed"}

@app.post("/chat")
async def chat(message: str = Form(...), image: UploadFile = File(None)):
    img_b64 = ""
    if image:
        content = await image.read()
        img_b64 = base64.b64encode(content).decode("utf-8")

    # Construct the internal prompt including knowledge base
    prompt = f"<|im_start|>system\\nYou are CIPHER, an elite cybersecurity research AI. Use this context: {knowledge_base}<|im_end|>\\n<|im_start|>user\\n{message}<|im_end|>\\n<|im_start|>assistant"

    payload = {
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": prompt}
        ]}],
        "temperature": 0.3
    }
    
    if img_b64:
        payload["messages"][0]["content"].append({
            "type": "image_url", 
            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
        })

    try:
        response = requests.post(LLAMA_API, json=payload)
        reply = response.json()["choices"][0]["message"]["content"]
    except:
        reply = "ERROR: Local engine (llama-server) is not responding. Check port 8080."

    return JSONResponse({"reply": reply})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
