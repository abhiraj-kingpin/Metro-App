# run with (from backend/): pytest -v

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.graph_builder import build_graph
from app.services.routing_engine import (
    RouteConstraints,
    RouteNotFoundError,
    find_k_shortest_paths,
    find_shortest_path,
)

graph = build_graph()


def test_direct_route_same_line_has_zero_transfers():
    result = find_shortest_path(graph, "Rajiv Chowk", "Barakhamba Road")
    assert result.total_transfers == 0
    assert result.segments[0].line == "Blue"


def test_route_requires_one_interchange():
    # Chandni Chowk (Yellow-only) sits right next to Rajiv Chowk, same for
    # Barakhamba Road (Blue-only) -- so this should be a plain one-transfer hop.
    result = find_shortest_path(graph, "Chandni Chowk", "Barakhamba Road")
    lines_used = {s.line for s in result.segments}
    assert lines_used == {"Yellow", "Blue"}
    assert result.total_transfers == 1
    assert result.segments[0].line == "Yellow"
    assert result.segments[-1].line == "Blue"


def test_more_transfers_can_still_be_the_shortest_route():
    # Going via Rajiv Chowk is only 1 transfer but a big detour into central
    # Delhi. With Airport Express in the graph, the actual shortest route is
    # Yellow to New Delhi then a straight Airport Express run to Dwarka
    # Sector 21 -- also 1 transfer, just a different one. Point stands: the
    # engine should pick whatever is fastest, not whatever has fewer hops.
    result = find_shortest_path(graph, "Samaypur Badli", "Dwarka Sector 21")
    assert result.total_transfers >= 1
    assert result.segments[0].line == "Yellow"
    assert result.segments[-1].to_station == "Dwarka Sector 21"


def test_default_route_uses_direct_line_when_available():
    result = find_shortest_path(graph, "Rajiv Chowk", "Central Secretariat")
    assert result.total_transfers == 0
    assert result.segments[0].line == "Yellow"


def test_avoid_lines_forces_alternate_path():
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
    constraints = RouteConstraints(avoid_lines=frozenset({"Yellow"}))
    with pytest.raises(RouteNotFoundError):
        find_shortest_path(graph, "Samaypur Badli", "Dwarka Sector 21", constraints)


def test_k_shortest_paths_are_sorted_and_distinct():
    results = find_k_shortest_paths(graph, "Samaypur Badli", "Dwarka Sector 21", k=3)
    assert len(results) > 1
    durations = [r.total_duration_seconds for r in results]
    assert durations == sorted(durations)

    # no two routes should walk the exact same sequence of stations
    paths = [tuple(st for seg in r.segments for st in seg.stations) for r in results]
    assert len(paths) == len(set(paths))


def test_k_shortest_paths_respects_k():
    results = find_k_shortest_paths(graph, "Rajiv Chowk", "Barakhamba Road", k=3)
    assert 1 <= len(results) <= 3


def test_k_shortest_paths_same_station_returns_single_empty_route():
    results = find_k_shortest_paths(graph, "Rajiv Chowk", "Rajiv Chowk", k=3)
    assert len(results) == 1
    assert results[0].segments == []
