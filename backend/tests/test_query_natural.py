# run with (from backend/): pytest -v

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app

client = TestClient(app)


def test_natural_query_resolves_and_routes():
    resp = client.post(
        "/api/v1/query/natural",
        json={"query": "from Chandni Chowk to Barakhamba Road"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["understood"]["from_station"] == "Chandni Chowk"
    assert body["understood"]["to_station"] == "Barakhamba Road"
    assert len(body["routes"]) >= 1


def test_natural_query_applies_avoid_line():
    resp = client.post(
        "/api/v1/query/natural",
        json={"query": "Rajiv Chowk se Central Secretariat jana hai, Yellow Line se mat nikalna"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["understood"]["avoid_lines"] == ["Yellow"]
    for route in body["routes"]:
        assert "Yellow" not in {seg["line"] for seg in route["segments"]}


def test_natural_query_unresolvable_returns_422():
    resp = client.post("/api/v1/query/natural", json={"query": "take me somewhere nice"})
    assert resp.status_code == 422
