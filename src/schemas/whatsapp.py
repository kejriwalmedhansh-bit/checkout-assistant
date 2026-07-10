"""Thin schemas for the WhatsApp webhook."""
from __future__ import annotations

from pydantic import BaseModel


class WebhookAck(BaseModel):
    status: str = "ok"
