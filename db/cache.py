"""
cache.py — SQLite disk-based cache for SerpAPI search results.
"""

import json
import sqlite3
from pathlib import Path

CACHE_PATH = Path(__file__).resolve().parent / "cache.db"


def init_cache() -> None:
    with sqlite3.connect(CACHE_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS search_cache (
                query TEXT PRIMARY KEY,
                results TEXT,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def _normalize(query: str) -> str:
    return query.strip().lower()


def get_cached(query: str, max_age_hours: int = 24) -> list | None:
    norm_query = _normalize(query)
    with sqlite3.connect(CACHE_PATH) as conn:
        row = conn.execute(
            "SELECT results FROM search_cache WHERE query = ? "
            "AND cached_at >= datetime('now', ?)",
            (norm_query, f"-{max_age_hours} hours"),
        ).fetchone()

    if row is None:
        return None

    return json.loads(row[0])


def save_cache(query: str, results: list) -> None:
    norm_query = _normalize(query)
    with sqlite3.connect(CACHE_PATH) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO search_cache (query, results, cached_at) "
            "VALUES (?, ?, CURRENT_TIMESTAMP)",
            (norm_query, json.dumps(results)),
        )
