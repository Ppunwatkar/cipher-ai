@app.post("/chat")
async def chat(
    request: Request,
    message: str = Form(...),
    chat_id: str = Form(...),
    mode: str = Form(...),
    db: Session = Depends(get_db)
):
    print("📩 Incoming message:", message)
    print("📌 Chat ID:", chat_id)

    mode = mode.lower().strip()

    # =========================
    # GET OR CREATE CHAT
    # =========================
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()

    if not chat:
        print("🆕 Creating new chat")

        chat = models.Chat(
            id=chat_id,
            user_id=1,
            title="New Chat"
        )
        db.add(chat)
        db.commit()
        db.refresh(chat)

    # =========================
    # LOAD HISTORY FROM DB
    # =========================
    history = db.query(models.Message)\
        .filter(models.Message.chat_id == chat_id)\
        .order_by(models.Message.id.desc())\
        .limit(6).all()

    history_messages = [
        {"role": m.role, "content": m.content}
        for m in reversed(history)
    ]

    messages = [
        {"role": "system", "content": get_prompt(mode)},
        *history_messages,
        {"role": "user", "content": message}
    ]

    # =========================
    # MODEL ROUTING
    # =========================
    if mode == "fast":
        data = call_groq(messages)
        tag = "⚡ [FAST-GROQ]"
    else:
        model = get_model(mode)
        data = call_openrouter(messages, model)
        tag = f"🧠 [{model.split('/')[-1]}]"

    if "error" in data:
        print("⚠️ OpenRouter failed, using Groq fallback")
        data = call_groq(messages)
        tag = "⚡ [FALLBACK-GROQ]"

    try:
        reply = data["choices"][0]["message"]["content"]
    except Exception as e:
        print("❌ AI ERROR:", data)
        return {"response": f"❌ ERROR:\n{data}"}

    reply = f"{tag}\n{reply}"

    # =========================
    # SAVE TO DATABASE
    # =========================
    print("💾 Saving messages to DB")

    user_msg = models.Message(
        chat_id=chat_id,
        role="user",
        content=message
    )

    bot_msg = models.Message(
        chat_id=chat_id,
        role="assistant",
        content=reply
    )

    db.add(user_msg)
    db.add(bot_msg)
    db.commit()

    print("✅ Saved successfully")

    return {"response": reply}
