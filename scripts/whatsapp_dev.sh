#!/usr/bin/env bash
# One-command WhatsApp dev loop: starts the backend + an ngrok tunnel if they
# aren't already running, self-tests the webhook handshake through the
# tunnel, and prints exactly what to paste into the Meta dashboard.
#
# What this script CANNOT do (needs your own Meta/WhatsApp login):
#   - paste the Callback URL + verify token into Meta's Configuration page
#   - confirm your test-recipient phone number is still approved
#   - regenerate WHATSAPP_ACCESS_TOKEN in .env when it expires (~24h)
set -euo pipefail
cd "$(dirname "$0")/.."

PORT=8000
UVICORN_LOG=/tmp/dealo_uvicorn_dev.log
NGROK_LOG=/tmp/dealo_ngrok_dev.log

# --- 1. backend ---------------------------------------------------------
if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[1/6] Backend already running on :$PORT"
else
  echo "[1/6] Starting backend on :$PORT..."
  nohup ./react/.venv/bin/uvicorn src.application:app --reload --port "$PORT" \
    > "$UVICORN_LOG" 2>&1 &
  for _ in $(seq 1 30); do
    curl -s -o /dev/null "http://localhost:$PORT/health" && break
    sleep 1
  done
  curl -sf -o /dev/null "http://localhost:$PORT/health" \
    || { echo "Backend failed to start — see $UVICORN_LOG"; exit 1; }
fi

# --- 2. ngrok tunnel -----------------------------------------------------
if pgrep -f "ngrok http $PORT" >/dev/null 2>&1; then
  echo "[2/6] ngrok already running for :$PORT"
else
  echo "[2/6] Starting ngrok tunnel..."
  nohup ngrok http "$PORT" --log=stdout > "$NGROK_LOG" 2>&1 &
  sleep 2
fi

# --- 3. read the public URL out of ngrok's local API ---------------------
echo "[3/6] Waiting for ngrok tunnel URL..."
PUBLIC_URL=""
for _ in $(seq 1 20); do
  PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels \
    | python3.11 -c "import json,sys; t=json.load(sys.stdin).get('tunnels',[]); print(t[0]['public_url'] if t else '')" 2>/dev/null || true)
  [ -n "$PUBLIC_URL" ] && break
  sleep 1
done
[ -n "$PUBLIC_URL" ] || { echo "Could not read ngrok tunnel URL — check $NGROK_LOG"; exit 1; }

# --- 4. verify token (never print WHATSAPP_ACCESS_TOKEN or other secrets) -
VERIFY_TOKEN=$(grep -E '^WHATSAPP_VERIFY_TOKEN=' .env 2>/dev/null | cut -d= -f2-)
VERIFY_TOKEN=${VERIFY_TOKEN:-dealo_webhook_2026}
echo "[4/6] Verify token loaded"

# --- 5. self-test the webhook handshake through the tunnel ---------------
echo "[5/6] Self-testing webhook handshake..."
CHALLENGE_RESPONSE=$(curl -s "$PUBLIC_URL/webhook?hub.mode=subscribe&hub.verify_token=$VERIFY_TOKEN&hub.challenge=selftest")
if [ "$CHALLENGE_RESPONSE" != "selftest" ]; then
  echo "Self-test FAILED — webhook did not echo back the challenge (got: $CHALLENGE_RESPONSE)"
  exit 1
fi
echo "      Self-test passed."

# --- 6. print what to paste into Meta -------------------------------------
echo ""
echo "[6/6] Paste these into Meta → your app → WhatsApp → Configuration:"
echo ""
echo "  Callback URL:  $PUBLIC_URL/webhook"
echo "  Verify Token:  $VERIFY_TOKEN"
echo ""
echo "If messages stop arriving, check in the Meta dashboard:"
echo "  - your phone number is still an approved test recipient"
echo "  - WHATSAPP_ACCESS_TOKEN in .env hasn't expired (dev tokens last ~24h)"
