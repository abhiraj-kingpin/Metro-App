# run with (from backend/): pytest -v

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.saved_routes import list_routes, save_route


def test_save_then_list(tmp_path):
    db_path = tmp_path / "user_routes.db"
    save_route("abhiraj", "Rajiv Chowk", "Central Secretariat", db_path)

    rows = list_routes("abhiraj", db_path)
    assert len(rows) == 1
    assert rows[0]["from_station"] == "Rajiv Chowk"
    assert rows[0]["frequency_count"] == 1


def test_saving_the_same_route_twice_bumps_frequency_not_row_count(tmp_path):
    db_path = tmp_path / "user_routes.db"
    save_route("abhiraj", "Rajiv Chowk", "Central Secretariat", db_path)
    save_route("abhiraj", "Rajiv Chowk", "Central Secretariat", db_path)

    rows = list_routes("abhiraj", db_path)
    assert len(rows) == 1
    assert rows[0]["frequency_count"] == 2


def test_different_users_dont_see_each_others_routes(tmp_path):
    db_path = tmp_path / "user_routes.db"
    save_route("abhiraj", "Rajiv Chowk", "Central Secretariat", db_path)

    assert list_routes("someone_else", db_path) == []


def test_most_frequent_route_sorts_first(tmp_path):
    db_path = tmp_path / "user_routes.db"
    save_route("abhiraj", "Rajiv Chowk", "Central Secretariat", db_path)
    save_route("abhiraj", "Dwarka Sector 21", "Vaishali", db_path)
    save_route("abhiraj", "Dwarka Sector 21", "Vaishali", db_path)

    rows = list_routes("abhiraj", db_path)
    assert rows[0]["from_station"] == "Dwarka Sector 21"
    assert rows[0]["frequency_count"] == 2
