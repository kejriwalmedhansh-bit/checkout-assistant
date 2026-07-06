import os
import httpx
import asyncio
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import PlainTextResponse
from whatsapp.classifier import classify_input
from whatsapp.session_store import SessionStore

router = APIRouter()

PHONE_NUMBER_ID = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
ACCESS_TOKEN = os.environ["WHATSAPP_ACCESS_TOKEN"]
VERIFY_TOKEN = os.environ["WHATSAPP_VERIFY_TOKEN"]
API_URL = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json"}

store = SessionStore("db/whatsapp_sessions.db")

ONBOARDING_MSG = "Hi! I'm Dealo 👋\n\nSend me a product name or paste a link and I'll find the cheapest way to buy it.\n\nExamples:\n• boAt Airdopes 141\n• https://www.amazon.in/dp/B0ABC123"
NUDGE_MSG = "Send a product name (e.g. 'Samsung Galaxy S24') or paste a product link."
DEAD_END_MSG = "Couldn't find a reliable route for that one yet. Try a different product or paste the link directly."

@router.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == VERIFY_TOKEN:
        return PlainTextResponse(params.get("hub.challenge"))
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/webhook")
async def receive_message(request: Request):
    body = await request.json()
    try:
        entry = body["entry"][0]["changes"][0]["value"]
        messages = entry.get("messages")
        if not messages:
            return {"status": "no_message"}
        msg = messages[0]
        phone = msg["from"]
        msg_type = msg.get("type")
        if msg_type == "interactive":
            reply_id = msg["interactive"]["button_reply"]["id"]
            if reply_id == "see_alternatives":
                asyncio.create_task(handle_alternatives(phone))
            return {"status": "ok"}
        if msg_type != "text":
            await send_text(phone, NUDGE_MSG)
            return {"status": "ok"}
        text = msg["text"]["body"]
        is_new = store.is_new_user(phone)
        if is_new:
            await send_text(phone, ONBOARDING_MSG)
        classification = classify_input(text)
        if classification["type"] == "unparseable":
            if not is_new:
                await send_text(phone, NUDGE_MSG)
            return {"status": "ok"}
        await send_text(phone, "Checking the best way to buy this — one sec ⏳")
        asyncio.create_task(process_and_respond(phone, classification))
    except (KeyError, IndexError):
        pass
    return {"status": "ok"}

async def process_and_respond(phone, classification):
    try:
        from pipeline import run_pipeline
        query = classification.get("query") or classification.get("url")
        result = await asyncio.to_thread(run_pipeline, query)
        routes = result.get("routes", {})
        recommended = routes.get("recommended")
        if not recommended:
            await send_text(phone, DEAD_END_MSG)
            return
        store.set_session(phone, {"routes": routes})
        msg = format_recommended(recommended)
        if routes.get("alternatives"):
            await send_with_alternatives_button(phone, msg)
        else:
            await send_text(phone, msg)
    except Exception as e:
        await send_text(phone, DEAD_END_MSG)
        print(f"[Webhook] Error for {phone}: {e}")

async def handle_alternatives(phone):
    session = store.get_session(phone)
    if not session:
        await send_text(phone, "Session expired — send the product again and I'll re-check.")
        return
    alternatives = session.get("routes", {}).get("alternatives", [])
    if not alternatives:
        await send_text(phone, "No alternative routes found for this one.")
        return
    msg = "Other ways to buy this:\n\n"
    for i, alt in enumerate(alternatives[:3], 1):
        msg += format_alternative(i, alt)
    await send_text(phone, msg.strip())

def format_recommended(route):
    lines = ["*Best way to buy this* ⭐\n"]
    if route.get("merchant"):
        lines.append(f"🏪 {route['merchant']}")
    if route.get("final_cost"):
        lines.append(f"💰 Final cost: ₹{route['final_cost']:,.0f}")
    if route.get("original_price") and route.get("final_cost"):
        savings = route["original_price"] - route["final_cost"]
        if savings > 0:
            lines.append(f"✅ You save: ₹{savings:,.0f}")
    if route.get("steps"):
        lines.append("\n*What to do:*")
        for step in route["steps"]:
            lines.append(f"• {step}")
    if route.get("card_fomo"):
        fomo = route["card_fomo"]
        lines.append(f"\n💳 Have a {fomo.get('card_name')} card? You'd save an extra ₹{fomo.get('actual_saving'):,.0f} at checkout.")
    return "\n".join(lines)

def format_alternative(index, route):
    lines = [f"*Option {index}*"]
    if route.get("merchant"):
        lines.append(f"🏪 {route['merchant']}")
    if route.get("final_cost"):
        lines.append(f"💰 Final cost: ₹{route['final_cost']:,.0f}")
    if route.get("original_price") and route.get("final_cost"):
        savings = route["original_price"] - route["final_cost"]
        if savings > 0:
            lines.append(f"✅ You save: ₹{savings:,.0f}")
    if route.get("reason"):
        lines.append(f"ℹ️ {route['reason']}")
    if route.get("steps"):
        lines.append("*What to do:*")
        for step in route["steps"]:
            lines.append(f"• {step}")
    return "\n".join(lines) + "\n\n"

async def send_text(phone, text):
    payload = {"messaging_product": "whatsapp", "to": phone, "type": "text", "text": {"body": text}}
    async with httpx.AsyncClient() as client:
        await client.post(API_URL, headers=HEADERS, json=payload)

async def send_with_alternatives_button(phone, text):
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": text},
            "action": {"buttons": [{"type": "reply", "reply": {"id": "see_alternatives", "title": "See other ways to buy"}}]}
        }
    }
    async with httpx.AsyncClient() as client:
        await client.post(API_URL, headers=HEADERS, json=payload)
