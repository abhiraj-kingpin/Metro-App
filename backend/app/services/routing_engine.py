"""Shortest-path routing over the metro graph.

Runs Dijkstra's algorithm over an expanded state space of
``(station, line, transfers_used)`` so a "max transfers" preference can be
enforced exactly (as a hard cap on reachable states) rather than merely
penalized. ``avoid_lines`` is enforced by skipping edges on those lines
during relaxation -- equivalent to deleting them from the graph.

Complexity: this is still Dijkstra's usual O(E log V) shape, just over a
larger explicit state space V' = V * L * (max_transfers + 1). For a
metro-sized graph (hundreds of stations, single-digit transfer caps) that
expansion is cheap.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from app.services.graph_builder import Edge, MetroGraph, TRANSFER_PENALTY_SECONDS


class RouteNotFoundError(Exception):
    """Raised when no path exists between two stations under the given constraints."""


@dataclass(frozen=True)
class RouteConstraints:
    avoid_lines: frozenset[str] = frozenset()
    max_transfers: int = 4


@dataclass
class RouteSegment:
    line: str
    line_color: str
    from_station: str
    to_station: str
    stations: list[str]
    stops_count: int
    distance_km: float
    duration_seconds: int


@dataclass
class RouteResult:
    segments: list[RouteSegment] = field(default_factory=list)
    total_duration_seconds: int = 0
    total_distance_km: float = 0.0
    total_transfers: int = 0


# (station, line, transfers_used)
State = tuple[str, str, int]


def find_shortest_path(
    graph: MetroGraph,
    start_station: str,
    end_station: str,
    constraints: RouteConstraints | None = None,
) -> RouteResult:
    constraints = constraints or RouteConstraints()

    if not graph.has_station(start_station):
        raise RouteNotFoundError(f"Unknown station: {start_station!r}")
    if not graph.has_station(end_station):
        raise RouteNotFoundError(f"Unknown station: {end_station!r}")

    if start_station == end_station:
        return RouteResult()

    start_lines = graph.lines_at(start_station) - constraints.avoid_lines
    if not start_lines:
        raise RouteNotFoundError(
            f"No operating line serves {start_station!r} under the given constraints"
        )

    dist: dict[State, float] = {}
    prev: dict[State, tuple[State, Edge]] = {}
    pq: list[tuple[float, State]] = []

    for line in start_lines:
        state: State = (start_station, line, 0)
        dist[state] = 0
        heapq.heappush(pq, (0, state))

    best_end_state: State | None = None

    while pq:
        cost, state = heapq.heappop(pq)
        if cost > dist.get(state, float("inf")):
            continue  # stale queue entry
        station, line, transfers = state

        if station == end_station:
            best_end_state = state
            break

        for edge in graph.adjacency.get((station, line), []):
            if edge.line in constraints.avoid_lines:
                continue
            next_transfers = transfers + (1 if edge.is_transfer else 0)
            if next_transfers > constraints.max_transfers:
                continue
            next_state: State = (edge.to_station, edge.line, next_transfers)
            new_cost = cost + edge.duration_seconds
            if new_cost < dist.get(next_state, float("inf")):
                dist[next_state] = new_cost
                prev[next_state] = (state, edge)
                heapq.heappush(pq, (new_cost, next_state))

    if best_end_state is None:
        raise RouteNotFoundError(
            f"No route found between {start_station!r} and {end_station!r} "
            "under the given constraints"
        )

    return _reconstruct(graph, best_end_state, prev)


def _reconstruct(
    graph: MetroGraph,
    end_state: State,
    prev: dict[State, tuple[State, Edge]],
) -> RouteResult:
    path_states = [end_state]
    while path_states[-1] in prev:
        path_states.append(prev[path_states[-1]][0])
    path_states.reverse()

    edges = [prev[state][1] for state in path_states[1:]]

    segments: list[RouteSegment] = []
    current_line = path_states[0][1]
    current_stations = [path_states[0][0]]
    seg_distance = 0.0
    seg_duration = 0

    def flush() -> None:
        if len(current_stations) < 2:
            return
        segments.append(
            RouteSegment(
                line=current_line,
                line_color=graph.line_colors.get(current_line, "#000000"),
                from_station=current_stations[0],
                to_station=current_stations[-1],
                stations=list(current_stations),
                stops_count=len(current_stations) - 1,
                distance_km=round(seg_distance, 2),
                duration_seconds=seg_duration,
            )
        )

    for edge, state in zip(edges, path_states[1:]):
        if edge.is_transfer:
            flush()
            current_line = state[1]
            current_stations = [state[0]]
            seg_distance = 0.0
            seg_duration = 0
        else:
            current_stations.append(state[0])
            seg_distance += edge.distance_km
            seg_duration += edge.duration_seconds
    flush()

    ride_time = sum(s.duration_seconds for s in segments)
    transfer_time = TRANSFER_PENALTY_SECONDS * max(len(segments) - 1, 0)

    return RouteResult(
        segments=segments,
        total_duration_seconds=ride_time + transfer_time,
        total_distance_km=round(sum(s.distance_km for s in segments), 2),
        total_transfers=max(len(segments) - 1, 0),
    )
