import json
import sqlite3
import time
from pathlib import Path

DEFAULT_TTL_SECONDS = 10 * 60

class SessionStore:
    def __init__(self, db_path, ttl_seconds=DEFAULT_TTL_SECONDS):
        self.ttl_seconds = ttl_seconds
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._init_schema()

    def _init_schema(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                phone_number TEXT PRIMARY KEY,
                first_seen_at REAL NOT NULL
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                phone_number TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                expires_at REAL NOT NULL
            )
        """)
        self.conn.commit()

    def is_new_user(self, phone_number):
        cur = self.conn.execute("SELECT 1 FROM users WHERE phone_number = ?", (phone_number,))
        if cur.fetchone() is not None:
            return False
        self.conn.execute("INSERT INTO users (phone_number, first_seen_at) VALUES (?, ?)", (phone_number, time.time()))
        self.conn.commit()
        return True

    def get_session(self, phone_number):
        cur = self.conn.execute("SELECT data, expires_at FROM sessions WHERE phone_number = ?", (phone_number,))
        row = cur.fetchone()
        if row is None:
            return None
        data_json, expires_at = row
        if time.time() > expires_at:
            self.conn.execute("DELETE FROM sessions WHERE phone_number = ?", (phone_number,))
            self.conn.commit()
            return None
        self._touch(phone_number)
        return json.loads(data_json)

    def set_session(self, phone_number, data):
        expires_at = time.time() + self.ttl_seconds
        self.conn.execute("""
            INSERT INTO sessions (phone_number, data, expires_at)
            VALUES (?, ?, ?)
            ON CONFLICT(phone_number) DO UPDATE SET
                data = excluded.data,
                expires_at = excluded.expires_at
        """, (phone_number, json.dumps(data), expires_at))
        self.conn.commit()

    def _touch(self, phone_number):
        self.conn.execute("UPDATE sessions SET expires_at = ? WHERE phone_number = ?", (time.time() + self.ttl_seconds, phone_number))
        self.conn.commit()

    def close(self):
        self.conn.close()
