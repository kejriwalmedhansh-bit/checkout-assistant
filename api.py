"""
api.py — FastAPI backend for Checkout Assistant.

Run:  uvicorn api:app --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from dotenv import load_dotenv
load_dotenv()

from pipeline import run_pipeline

app = FastAPI(title="Checkout Assistant")

# Allow the statically-hosted GitHub Pages frontend to call this backend.
# No cookies/auth are used, so a permissive origin policy is safe here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
from whatsapp.webhook import router as whatsapp_router
app.include_router(whatsapp_router)
from v2.routes import router as v2_router
app.include_router(v2_router)
templates = Jinja2Templates(directory="templates")


class SearchRequest(BaseModel):
    query: str


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.post("/search")
async def search(body: SearchRequest):
    """
    Accepts a product URL or text query.
    Returns the full pipeline result as JSON.
    """
    result = run_pipeline(body.query.strip())
    return result


@app.get("/health")
async def health():
    return {"status": "ok"}
