"""Application factory — assembles the FastAPI app from all routers.

Run with:  uvicorn src.application:app --reload

Dealo is a stateless pre-checkout purchase optimization engine: no database, no
auth. Everything (search cache, WhatsApp sessions) lives in process memory.
"""
from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routers import health, redirect, search, vouchers, whatsapp
from .config import get_settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="Dealo Backend",
        description="Pre-checkout purchase optimization engine for Indian e-commerce.",
        version="0.2.0",
    )

    settings = get_settings()
    allow_all = "*" in settings.cors_origins_list
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if allow_all else settings.cors_origins_list,
        # Can't send credentials with a wildcard origin; only enable when explicit.
        allow_credentials=not allow_all,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(search.router)
    app.include_router(vouchers.router)
    app.include_router(whatsapp.router)
    app.include_router(health.router)
    app.include_router(redirect.router)

    @app.get("/")
    async def root() -> dict[str, Any]:
        return {
            "service": "dealo-backend",
            "version": "0.2.0",
            "endpoints": [
                "POST /search",
                "POST /routes",
                "GET /products/{product_token}",
                "GET /vouchers",
                "GET /vouchers/{slug}",
                "GET /webhook",
                "POST /webhook",
                "GET /health",
                "GET /go",
            ],
        }

    @app.get("/health")
    async def health_root() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
