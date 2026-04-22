from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import os

app = FastAPI()

# ==================================================
# STATIC + TEMPLATE CONFIG
# ==================================================

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


# ==================================================
# HOME ROUTE (100% FIXED)
# ==================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request
        }
    )


# ==================================================
# TEST ROUTE
# ==================================================

@app.get("/ping")
async def ping():
    return {"status": "ok"}
