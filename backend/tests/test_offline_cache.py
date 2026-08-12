# run with (from backend/): pytest -v

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.graph_builder import build_graph
from app.services.offline_cache import export_to_sqlite, load_graph_from_sqlite
from app.services.routing_engine import find_shortest_path

live_graph = build_graph()


def test_export_and_reload_produces_equivalent_graph(tmp_path):
    db_path = tmp_path / "offline.db"
    export_to_sqlite(live_graph, db_path)
    offline_graph = load_graph_from_sqlite(db_path)

    assert offline_graph.station_lines == live_graph.station_lines
    assert offline_graph.line_colors == live_graph.line_colors
    assert offline_graph.line_operators == live_graph.line_operators


def test_offline_graph_routes_the_same_as_live(tmp_path):
    db_path = tmp_path / "offline.db"
    export_to_sqlite(live_graph, db_path)
    offline_graph = load_graph_from_sqlite(db_path)

    online = find_shortest_path(live_graph, "Chandni Chowk", "Barakhamba Road")
    offline = find_shortest_path(offline_graph, "Chandni Chowk", "Barakhamba Road")

    assert online.total_duration_seconds == offline.total_duration_seconds
    assert [s.line for s in online.segments] == [s.line for s in offline.segments]


def test_missing_cache_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_graph_from_sqlite(tmp_path / "does_not_exist.db")
