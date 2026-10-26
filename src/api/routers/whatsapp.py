"""WhatsApp webhook (Meta Graph API).

    GET  /webhook   verification handshake (echoes hub.challenge)
    POST /webhook   receive + dispatch messages, always ack {"status": "ok"}
    GET  /wa/price-card.jpg   picture on one price-list carousel card

WhatsApp settings are read lazily inside the service, so these routes import
cleanly even when WhatsApp is not configured.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, Response

from ...config import get_settings
from ...services import price_list, whatsapp_service

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


@router.get("/wa/price-card.jpg")
def price_card(
    m: str = Query(..., max_length=60),
    h: str = Query("", max_length=80),
    p: int = Query(..., ge=1, le=100_000_000),
    b: int = Query(..., ge=1, le=100_000_000),
    x: int = Query(..., ge=1, le=100_000_000),
    r: int = Query(0, ge=0, le=20),
    c: str = Query("", max_length=60),
) -> Response:
    """Meta fetches this when it shows a price-list card (a plain def, so
    the logo download and drawing run off the event loop)."""
    if not (b <= p <= x):
        raise HTTPException(status_code=400, detail="price out of range")
    jpeg = price_list.render_price_card(m, h, p, b, x, r, c)
    return Response(jpeg, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
