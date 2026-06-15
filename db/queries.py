from datetime import datetime, timedelta, timezone

from .models import get_connection

CACHE_TTL_MINUTES = 30


def get_cached_comparisons(product_url: str) -> list[dict]:
    """Return cached results for *product_url* if they are < 30 minutes old."""
    cutoff = (
        datetime.now(timezone.utc) - timedelta(minutes=CACHE_TTL_MINUTES)
    ).strftime("%Y-%m-%dT%H:%M:%S")

    conn = get_connection()
    rows = conn.execute(
        """
        SELECT * FROM price_comparisons
        WHERE product_url = ?
          AND timestamp   >= ?
        ORDER BY price ASC NULLS LAST
        """,
        (product_url, cutoff),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_comparisons(product_url: str, results: list[dict]) -> None:
    """Replace all stored rows for *product_url* with *results*."""
    conn = get_connection()
    conn.execute("DELETE FROM price_comparisons WHERE product_url = ?", (product_url,))
    conn.executemany(
        """
        INSERT INTO price_comparisons
            (product_url, merchant, name, price, regular_price, currency,
             match_type, variant_notes, source_url, availability, brand, mpn,
             condition)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                product_url,
                r.get("merchant"),
                r.get("name"),
                r.get("price"),
                r.get("regular_price"),
                r.get("currency", "INR"),
                r.get("match_type"),
                r.get("variant_notes"),
                r.get("source_url"),
                r.get("availability"),
                r.get("brand"),
                r.get("mpn"),
                r.get("condition", "new"),
            )
            for r in results
        ],
    )
    conn.commit()
    conn.close()
