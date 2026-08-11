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
    yield
    for line in list(_status_board.all()):
        _status_board.set(line, "OPERATIONAL")


def test_websocket_receives_status_broadcast():
    with client.websocket_connect("/api/v1/disruptions/live") as ws:
        client.post(
            "/api/v1/lines/Yellow/status",
            json={"status": "DELAYED", "delay_seconds": 120, "reason": "rush hour"},
        )
        message = ws.receive_json()

    assert message == {
        "type": "LINE_STATUS_UPDATE",
        "line": "Yellow",
        "status": "DELAYED",
        "delay_seconds": 120,
        "reason": "rush hour",
    }


def test_websocket_only_gets_updates_after_connecting():
    # a status change before connecting shouldn't show up as a queued message
    client.post("/api/v1/lines/Blue/status", json={"status": "CLOSED"})

    with client.websocket_connect("/api/v1/disruptions/live") as ws:
        client.post("/api/v1/lines/Red/status", json={"status": "CLOSED"})
        message = ws.receive_json()

    assert message["line"] == "Red"
