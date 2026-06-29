"""
api.py — FastAPI backend for Checkout Assistant.

Run:  uvicorn api:app --host 0.0.0.0 --port 8000
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from dotenv import load_dotenv
load_dotenv()

from pipeline import run_pipeline

app = FastAPI(title="Checkout Assistant")
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
