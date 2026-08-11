# run with (from backend/): pytest -v

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.disruption_history import history, record


def test_record_then_read_back(tmp_path):
    db_path = tmp_path / "history.db"
    record("Yellow", "DELAYED", 180, "signal failure", db_path)

    rows = history(db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["line"] == "Yellow"
    assert rows[0]["status"] == "DELAYED"


def test_filters_by_line(tmp_path):
    db_path = tmp_path / "history.db"
    record("Yellow", "DELAYED", 180, None, db_path)
    record("Blue", "CLOSED", 0, "track maintenance", db_path)

    rows = history(line="Blue", db_path=db_path)
    assert len(rows) == 1
    assert rows[0]["line"] == "Blue"


def test_most_recent_first(tmp_path):
    db_path = tmp_path / "history.db"
    record("Yellow", "DELAYED", 60, "first", db_path)
    record("Yellow", "OPERATIONAL", 0, "resolved", db_path)

    rows = history(line="Yellow", db_path=db_path)
    assert rows[0]["reason"] == "resolved"
    assert rows[1]["reason"] == "first"


def test_limit_is_respected(tmp_path):
    db_path = tmp_path / "history.db"
    for i in range(5):
        record("Yellow", "DELAYED", i, f"event {i}", db_path)

    rows = history(line="Yellow", limit=2, db_path=db_path)
    assert len(rows) == 2
