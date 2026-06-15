import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "checkout_assistant.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS price_comparisons (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            product_url   TEXT NOT NULL,
            merchant      TEXT,
            name          TEXT,
            price         REAL,
            regular_price REAL,
            currency      TEXT DEFAULT 'INR',
            match_type    TEXT,
            variant_notes TEXT,
            source_url    TEXT,
            availability  TEXT,
            brand         TEXT,
            mpn           TEXT,
            condition     TEXT DEFAULT 'new',
            timestamp     DATETIME DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
        );

        CREATE INDEX IF NOT EXISTS idx_pc_url_ts
            ON price_comparisons (product_url, timestamp);
    """)
    # Migrate existing DBs that predate the condition column
    existing = {row[1] for row in conn.execute("PRAGMA table_info(price_comparisons)")}
    if "condition" not in existing:
        conn.execute("ALTER TABLE price_comparisons ADD COLUMN condition TEXT DEFAULT 'new'")

    conn.commit()
    conn.close()
