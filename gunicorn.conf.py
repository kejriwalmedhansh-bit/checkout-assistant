"""Gunicorn config for the Dealo FastAPI backend.

UvicornWorker bridges ASGI (FastAPI) with Gunicorn's process model.
The app is fully in-memory and stateless *per process*: the search cache and
WhatsApp session store live in worker memory and are NOT shared across workers.
We therefore run a single worker so sessions/cache stay coherent.

Bind honors $PORT (Render/Heroku inject it), defaulting to 8000 locally.
"""
import os

workers = 1
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
graceful_timeout = 30
keepalive = 5
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# Log to stdout/stderr so the platform log collector picks them up.
accesslog = "-"
errorlog = "-"
loglevel = "info"
