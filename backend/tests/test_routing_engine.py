"""Unit tests for the Dijkstra-based routing engine.

Run with (from backend/): pytest -v
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.graph_builder import build_graph
from app.services.routing_engine import (
    RouteConstraints,
    RouteNotFoundError,
    find_shortest_path,
)

graph = build_graph()


def test_direct_route_same_line_has_zero_transfers():
    result = find_shortest_path(graph, "Rajiv Chowk", "Barakhamba Road")
    assert result.total_transfers == 0
    assert result.segments[0].line == "Blue"


def test_route_requires_one_interchange():
    # Chandni Chowk (Yellow-only) and Barakhamba Road (Blue-only) sit right
    # next to the Rajiv Chowk interchange on their respective lines, so the
    # shortest path is a straight one-transfer hop through it.
    result = find_shortest_path(graph, "Chandni Chowk", "Barakhamba Road")
    lines_used = {s.line for s in result.segments}
    assert lines_used == {"Yellow", "Blue"}
    assert result.total_transfers == 1
    assert result.segments[0].line == "Yellow"
    assert result.segments[-1].line == "Blue"


def test_more_transfers_can_still_be_the_shortest_route():
    # Samaypur Badli (Yellow-only) -> Dwarka Sector 21 (Blue-only) is a
    # case where going via Rajiv Chowk (1 transfer) is a big detour into
    # central Delhi -- the real shortest route detours via Azadpur -> Pink
    # -> Rajouri Garden -> Blue instead, at the cost of an extra transfer.
    # This is exactly what Dijkstra should do: minimize total time, not
    # transfer count.
    result = find_shortest_path(graph, "Samaypur Badli", "Dwarka Sector 21")
    assert result.total_transfers >= 1
    assert result.segments[0].line == "Yellow"
    assert result.segments[-1].line == "Blue"


def test_default_route_uses_direct_line_when_available():
    # Rajiv Chowk -> Central Secretariat is a direct 2-hop ride on Yellow.
    result = find_shortest_path(graph, "Rajiv Chowk", "Central Secretariat")
    assert result.total_transfers == 0
    assert result.segments[0].line == "Yellow"


def test_avoid_lines_forces_alternate_path():
    # With Yellow avoided, Rajiv Chowk -> Central Secretariat must instead
    # go Blue (to Mandi House) -> Violet (to Central Secretariat).
    constraints = RouteConstraints(avoid_lines=frozenset({"Yellow"}))
    result = find_shortest_path(graph, "Rajiv Chowk", "Central Secretariat", constraints)
    lines_used = {s.line for s in result.segments}
    assert "Yellow" not in lines_used
    assert lines_used == {"Blue", "Violet"}


def test_max_transfers_constraint_raises_when_unsatisfiable():
    constraints = RouteConstraints(max_transfers=0)
    with pytest.raises(RouteNotFoundError):
        find_shortest_path(graph, "Samaypur Badli", "Dwarka Sector 21", constraints)


def test_same_station_returns_empty_route():
    result = find_shortest_path(graph, "Rajiv Chowk", "Rajiv Chowk")
    assert result.segments == []
    assert result.total_transfers == 0


def test_unknown_station_raises():
    with pytest.raises(RouteNotFoundError):
        find_shortest_path(graph, "Nonexistent Station", "Rajiv Chowk")


def test_avoid_only_line_at_origin_raises():
    # Samaypur Badli is served only by Yellow -- avoiding Yellow strands it.
    constraints = RouteConstraints(avoid_lines=frozenset({"Yellow"}))
    with pytest.raises(RouteNotFoundError):
        find_shortest_path(graph, "Samaypur Badli", "Dwarka Sector 21", constraints)
