# run with (from backend/): pytest -v

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.routes import _status_board
from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_status_board():
    # the board is a module-level singleton, tests share it -- put it back
    # to a clean slate after every test so order doesn't matter
    yield
    for line in list(_status_board.all()):
        _status_board.set(line, "OPERATIONAL")


def test_all_lines_start_operational():
    resp = client.get("/api/v1/lines/status")
    assert resp.status_code == 200
    assert all(entry["status"] == "OPERATIONAL" for entry in resp.json())


def test_set_status_updates_board():
    resp = client.post(
        "/api/v1/lines/Yellow/status",
        json={"status": "DELAYED", "delay_seconds": 180, "reason": "signal failure"},
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "line": "Yellow", "status": "DELAYED", "delay_seconds": 180, "reason": "signal failure"
    }


def test_set_status_unknown_line_404():
    resp = client.post("/api/v1/lines/Not A Line/status", json={"status": "CLOSED"})
    assert resp.status_code == 404


def test_set_status_invalid_value_422():
    resp = client.post("/api/v1/lines/Yellow/status", json={"status": "ON_FIRE"})
    assert resp.status_code == 422


def test_closed_line_is_excluded_from_routes():
    client.post("/api/v1/lines/Yellow/status", json={"status": "CLOSED"})
    resp = client.post(
        "/api/v1/routes/find",
        json={"from_station": "Rajiv Chowk", "to_station": "Central Secretariat"},
    )
    assert resp.status_code == 200
    for route in resp.json()["routes"]:
        assert "Yellow" not in {seg["line"] for seg in route["segments"]}


def test_delayed_line_adds_alert_and_extra_time():
    payload = {"from_station": "Rajiv Chowk", "to_station": "Central Secretariat"}
    baseline = client.post("/api/v1/routes/find", json=payload).json()["routes"][0]

    client.post(
        "/api/v1/lines/Yellow/status",
        json={"status": "DELAYED", "delay_seconds": 300, "reason": "signal failure"},
    )
    delayed = client.post("/api/v1/routes/find", json=payload).json()["routes"][0]

    assert delayed["total_duration_seconds"] > baseline["total_duration_seconds"]
    assert any(a["line"] == "Yellow" for a in delayed["alerts"])
