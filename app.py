from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
@app.get("/")
def home():
    return FileResponse("index.html")

# Test route
@app.get("/ping")
def ping():
    return {"status": "alive"}

# Chat route (NO DB)
@app.post("/chat")
def chat(message: str = Form(...), chat_id: str = Form(...), mode: str = Form(...)):
    print("🔥 CHAT HIT:", message)
    return {"response": f"✅ Working: {message}"}
