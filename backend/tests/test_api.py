"""Integration tests for the FastAPI HTTP layer.

Run with (from backend/): pytest -v
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_lines():
    resp = client.get("/api/v1/lines")
    assert resp.status_code == 200
    names = {line["name"] for line in resp.json()}
    assert names == {"Yellow", "Blue", "Violet", "Pink", "Magenta"}


def test_station_search():
    resp = client.get("/api/v1/stations", params={"q": "rajiv"})
    assert resp.status_code == 200
    assert any(s["name"] == "Rajiv Chowk" for s in resp.json())


def test_unknown_station_detail_404():
    resp = client.get("/api/v1/stations/Nonexistent Place")
    assert resp.status_code == 404


def test_find_route_success():
    # Chandni Chowk / Barakhamba Road sit right next to the Rajiv Chowk
    # interchange, so the shortest route is a clean single transfer.
    resp = client.post(
        "/api/v1/routes/find",
        json={"from_station": "Chandni Chowk", "to_station": "Barakhamba Road"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_transfers"] == 1
    lines_used = {seg["line"] for seg in body["segments"]}
    assert lines_used == {"Yellow", "Blue"}


def test_find_route_with_avoid_lines_preference():
    resp = client.post(
        "/api/v1/routes/find",
        json={
            "from_station": "Rajiv Chowk",
            "to_station": "Central Secretariat",
            "preferences": {"avoid_lines": ["Yellow"]},
        },
    )
    assert resp.status_code == 200
    lines_used = {seg["line"] for seg in resp.json()["segments"]}
    assert "Yellow" not in lines_used


def test_find_route_unreachable_returns_404():
    resp = client.post(
        "/api/v1/routes/find",
        json={"from_station": "Rajiv Chowk", "to_station": "Nonexistent Place"},
    )
    assert resp.status_code == 404
