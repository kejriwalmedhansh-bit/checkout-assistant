"""WhatsApp webhook (Meta Graph API).

    GET  /webhook   verification handshake (echoes hub.challenge)
    POST /webhook   receive + dispatch messages, always ack {"status": "ok"}

WhatsApp settings are read lazily inside the service, so these routes import
cleanly even when WhatsApp is not configured.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from ...config import get_settings
from ...services import whatsapp_service

router = APIRouter(tags=["whatsapp"])


@router.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    settings = get_settings()
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == settings.WHATSAPP_VERIFY_TOKEN
    ):
        return PlainTextResponse(params.get("hub.challenge"))
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def receive_message(request: Request) -> dict[str, str]:
    body = await request.json()
    await whatsapp_service.handle_incoming(body)
    return {"status": "ok"}
