"""Backward-compatible entrypoint.

The app is now assembled in ``src.application``. This module re-exports it so
that ``uvicorn src.api.app:app`` keeps working. Prefer ``src.application:app``.
"""
from __future__ import annotations

from ..application import app

__all__ = ["app"]
