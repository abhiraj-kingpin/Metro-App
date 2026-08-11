# Append-only log of every line status change -- the spec's DISRUPTIONS
# table, trimmed to the columns that actually apply here (no station_ids,
# no severity classification, since nothing produces those yet). Written
# once per status update, read back for a history view.
#
# Plain sqlite3 on purpose, same as offline_cache.py and saved_routes.py
# -- introducing an ORM for one more table would be more machinery than
# the problem needs.

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "disruption_history.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS disruption_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    line TEXT NOT NULL,
    status TEXT NOT NULL,
    delay_seconds INTEGER NOT NULL DEFAULT 0,
    reason TEXT,
    recorded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_disruption_history_line ON disruption_history(line);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA)
    return conn


def record(
    line: str, status: str, delay_seconds: int, reason: str | None, db_path: Path = DEFAULT_DB_PATH
) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO disruption_history (line, status, delay_seconds, reason, recorded_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (line, status, delay_seconds, reason, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def history(line: str | None = None, limit: int = 50, db_path: Path = DEFAULT_DB_PATH) -> list[dict]:
    conn = _connect(db_path)
    try:
        query = "SELECT line, status, delay_seconds, reason, recorded_at FROM disruption_history"
        params: tuple = ()
        if line:
            query += " WHERE line = ?"
            params = (line,)
        query += " ORDER BY id DESC LIMIT ?"
        rows = conn.execute(query, (*params, limit)).fetchall()
        return [
            {"line": r[0], "status": r[1], "delay_seconds": r[2], "reason": r[3], "recorded_at": r[4]}
            for r in rows
        ]
    finally:
        conn.close()
