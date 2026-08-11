# run with (from backend/): pytest -v

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
    assert names == {"Yellow", "Blue", "Violet", "Pink", "Magenta", "Red", "Airport Express", "Green", "Grey"}


def test_station_search():
    resp = client.get("/api/v1/stations", params={"q": "rajiv"})
    assert resp.status_code == 200
    assert any(s["name"] == "Rajiv Chowk" for s in resp.json())


def test_unknown_station_detail_404():
    resp = client.get("/api/v1/stations/Nonexistent Place")
    assert resp.status_code == 404


def test_find_route_success():
    # Chandni Chowk / Barakhamba Road sit right next to the Rajiv Chowk
    # interchange, so the top route should be a clean single transfer.
    resp = client.post(
        "/api/v1/routes/find",
        json={"from_station": "Chandni Chowk", "to_station": "Barakhamba Road"},
    )
    assert resp.status_code == 200
    routes = resp.json()["routes"]
    assert len(routes) >= 1
    best = routes[0]
    assert best["total_transfers"] == 1
    lines_used = {seg["line"] for seg in best["segments"]}
    assert lines_used == {"Yellow", "Blue"}


def test_find_route_returns_multiple_alternatives():
    resp = client.post(
        "/api/v1/routes/find",
        json={
            "from_station": "Samaypur Badli",
            "to_station": "Dwarka Sector 21",
            "preferences": {"alternatives": 3},
        },
    )
    assert resp.status_code == 200
    routes = resp.json()["routes"]
    assert len(routes) > 1
    # routes should come back cheapest first
    durations = [r["total_duration_seconds"] for r in routes]
    assert durations == sorted(durations)


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
    for route in resp.json()["routes"]:
        lines_used = {seg["line"] for seg in route["segments"]}
        assert "Yellow" not in lines_used


def test_offline_export_endpoint():
    resp = client.post("/api/v1/offline/export")
    assert resp.status_code == 200
    body = resp.json()
    assert body["station_count"] > 0
    assert body["line_count"] == 9


def test_save_and_list_route():
    save = client.post(
        "/api/v1/routes/save",
        json={"user_id": "test-user", "from_station": "Rajiv Chowk", "to_station": "Central Secretariat"},
    )
    assert save.status_code == 200
    assert save.json()["frequency_count"] >= 1

    saved = client.get("/api/v1/routes/saved", params={"user_id": "test-user"})
    assert saved.status_code == 200
    assert any(r["from_station"] == "Rajiv Chowk" for r in saved.json())


def test_save_route_unknown_station_404():
    resp = client.post(
        "/api/v1/routes/save",
        json={"user_id": "test-user", "from_station": "Nowhereville", "to_station": "Rajiv Chowk"},
    )
    assert resp.status_code == 404


def test_find_route_unreachable_returns_404():
    resp = client.post(
        "/api/v1/routes/find",
        json={"from_station": "Rajiv Chowk", "to_station": "Nonexistent Place"},
    )
    assert resp.status_code == 404
