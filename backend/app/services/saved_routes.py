# The spec's user_routes table, minus any real auth -- there isn't one
# yet, so user_id is just whatever string the client sends. Good enough
# to demo "save my usual route" without building a login system first.

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "user_routes.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS saved_routes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    from_station TEXT NOT NULL,
    to_station TEXT NOT NULL,
    frequency_count INTEGER NOT NULL DEFAULT 1,
    saved_at TEXT NOT NULL,
    UNIQUE(user_id, from_station, to_station)
);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(_SCHEMA)
    return conn


def save_route(
    user_id: str, from_station: str, to_station: str, db_path: Path = DEFAULT_DB_PATH
) -> dict:
    # saving the same route again just bumps the frequency count instead
    # of duplicating a row -- that's the whole point of tracking it
    conn = _connect(db_path)
    try:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO saved_routes (user_id, from_station, to_station, frequency_count, saved_at)
            VALUES (?, ?, ?, 1, ?)
            ON CONFLICT(user_id, from_station, to_station)
            DO UPDATE SET frequency_count = frequency_count + 1, saved_at = excluded.saved_at
            """,
            (user_id, from_station, to_station, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT from_station, to_station, frequency_count, saved_at FROM saved_routes "
            "WHERE user_id = ? AND from_station = ? AND to_station = ?",
            (user_id, from_station, to_station),
        ).fetchone()
        return _as_dict(row)
    finally:
        conn.close()


def list_routes(user_id: str, db_path: Path = DEFAULT_DB_PATH) -> list[dict]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT from_station, to_station, frequency_count, saved_at FROM saved_routes "
            "WHERE user_id = ? ORDER BY frequency_count DESC, saved_at DESC",
            (user_id,),
        ).fetchall()
        return [_as_dict(r) for r in rows]
    finally:
        conn.close()


def _as_dict(row: tuple) -> dict:
    return {"from_station": row[0], "to_station": row[1], "frequency_count": row[2], "saved_at": row[3]}
