"""Shared FastAPI dependencies.

Dealo is stateless — no database, no auth — so the only shared dependency is
access to settings.
"""
from __future__ import annotations

from ..config import Settings, get_settings

__all__ = ["get_settings", "Settings"]
