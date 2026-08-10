# Dijkstra over (station, line, transfers_used) states so max_transfers
# can be a hard cap instead of a penalty. find_k_shortest_paths is Yen's
# algorithm layered on top of that for "top 3 routes" instead of just one.
#
# line_delays is separate from RouteConstraints on purpose -- constraints
# are what the rider asked for (avoid this line, at most N transfers),
# delays are live network conditions from line_status.py. Different
# lifetimes, different owners, no reason to tangle them together.

from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from app.services.graph_builder import Edge, MetroGraph, TRANSFER_PENALTY_SECONDS


class RouteNotFoundError(Exception):
    """No path exists between two stations under the given constraints."""


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


State = tuple[str, str, int]  # (station, line, transfers_used)
EdgeKey = tuple  # (from_state, to_station, to_line, is_transfer)


def find_shortest_path(
    graph: MetroGraph,
    start_station: str,
    end_station: str,
    constraints: RouteConstraints | None = None,
    line_delays: dict[str, int] | None = None,
) -> RouteResult:
    constraints = constraints or RouteConstraints()
    line_delays = line_delays or {}
    start_states = _validate_and_seed(graph, start_station, end_station, constraints)

    if start_station == end_station:
        return RouteResult()

    found = _dijkstra(graph, start_states, end_station, constraints, line_delays=line_delays)
    if found is None:
        raise RouteNotFoundError(
            f"No route found between {start_station!r} and {end_station!r} under the given constraints"
        )
    path_states, path_edges, _ = found
    return _build_result(graph, path_states, path_edges, line_delays)


def find_k_shortest_paths(
    graph: MetroGraph,
    start_station: str,
    end_station: str,
    constraints: RouteConstraints | None = None,
    k: int = 3,
    line_delays: dict[str, int] | None = None,
) -> list[RouteResult]:
    constraints = constraints or RouteConstraints()
    line_delays = line_delays or {}
    start_states = _validate_and_seed(graph, start_station, end_station, constraints)

    if start_station == end_station:
        return [RouteResult()]

    first = _dijkstra(graph, start_states, end_station, constraints, line_delays=line_delays)
    if first is None:
        raise RouteNotFoundError(
            f"No route found between {start_station!r} and {end_station!r} under the given constraints"
        )

    accepted = [first]
    seen = {tuple(first[0])}
    candidates: list[tuple[int, int, list[State], list[Edge]]] = []  # (cost, tiebreak, states, edges)
    tiebreak = 0

    while len(accepted) < k:
        prev_states, prev_edges, _ = accepted[-1]

        for i in range(len(prev_states) - 1):
            spur_state = prev_states[i]
            root_states = prev_states[: i + 1]
            root_edges = prev_edges[:i]
            root_block = {s[0] for s in root_states[:-1]}  # can't re-walk earlier stations in this path

            forbidden: set[EdgeKey] = set()
            for path_states, path_edges, _ in accepted:
                if path_states[: i + 1] == root_states and len(path_edges) > i:
                    e = path_edges[i]
                    forbidden.add((path_states[i], e.to_station, e.line, e.is_transfer))

            spur = _dijkstra(
                graph, [spur_state], end_station, constraints,
                forbidden_edges=forbidden, forbidden_stations=root_block, line_delays=line_delays,
            )
            if spur is None:
                continue
            spur_states, spur_edges, _ = spur

            total_states = root_states[:-1] + spur_states
            total_edges = root_edges + spur_edges
            key = tuple(total_states)
            if key in seen:
                continue
            seen.add(key)

            cost = _total_cost(total_states, total_edges, line_delays)
            tiebreak += 1
            heapq.heappush(candidates, (cost, tiebreak, total_states, total_edges))

        if not candidates:
            break
        cost, _, states, edges = heapq.heappop(candidates)
        accepted.append((states, edges, cost))

    return [_build_result(graph, states, edges, line_delays) for states, edges, _ in accepted]


def _validate_and_seed(
    graph: MetroGraph, start_station: str, end_station: str, constraints: RouteConstraints
) -> list[State]:
    if not graph.has_station(start_station):
        raise RouteNotFoundError(f"Unknown station: {start_station!r}")
    if not graph.has_station(end_station):
        raise RouteNotFoundError(f"Unknown station: {end_station!r}")

    start_lines = graph.lines_at(start_station) - constraints.avoid_lines
    if not start_lines:
        raise RouteNotFoundError(
            f"No operating line serves {start_station!r} under the given constraints"
        )
    return [(start_station, line, 0) for line in start_lines]


def _total_cost(path_states: list[State], path_edges: list[Edge], line_delays: dict[str, int]) -> int:
    # delay is charged once per "boarding": the starting line, plus once
    # each time a transfer edge puts you onto a new line
    cost = line_delays.get(path_states[0][1], 0)
    for edge in path_edges:
        cost += edge.duration_seconds
        if edge.is_transfer:
            cost += line_delays.get(edge.line, 0)
    return cost


def _dijkstra(
    graph: MetroGraph,
    start_states: list[State],
    end_station: str,
    constraints: RouteConstraints,
    forbidden_edges: set[EdgeKey] = frozenset(),
    forbidden_stations: set[str] = frozenset(),
    line_delays: dict[str, int] | None = None,
) -> tuple[list[State], list[Edge], int] | None:
    line_delays = line_delays or {}
    dist: dict[State, float] = {}
    prev: dict[State, tuple[State, Edge]] = {}
    pq: list[tuple[float, State]] = []

    for state in start_states:
        if state[0] in forbidden_stations:
            continue
        dist[state] = line_delays.get(state[1], 0)
        heapq.heappush(pq, (dist[state], state))

    best_end_state = None
    while pq:
        cost, state = heapq.heappop(pq)
        if cost > dist.get(state, float("inf")):
            continue  # stale entry, a cheaper route to this state was already found
        station, line, transfers = state

        if station == end_station:
            best_end_state = state
            break

        for edge in graph.adjacency.get((station, line), []):
            if edge.line in constraints.avoid_lines:
                continue
            if edge.to_station in forbidden_stations:
                continue
            if (state, edge.to_station, edge.line, edge.is_transfer) in forbidden_edges:
                continue
            next_transfers = transfers + (1 if edge.is_transfer else 0)
            if next_transfers > constraints.max_transfers:
                continue
            next_state: State = (edge.to_station, edge.line, next_transfers)
            new_cost = cost + edge.duration_seconds
            if edge.is_transfer:
                new_cost += line_delays.get(edge.line, 0)
            if new_cost < dist.get(next_state, float("inf")):
                dist[next_state] = new_cost
                prev[next_state] = (state, edge)
                heapq.heappush(pq, (new_cost, next_state))

    if best_end_state is None:
        return None

    path_states = [best_end_state]
    while path_states[-1] in prev:
        path_states.append(prev[path_states[-1]][0])
    path_states.reverse()
    path_edges = [prev[s][1] for s in path_states[1:]]
    return path_states, path_edges, dist[best_end_state]


def _build_result(
    graph: MetroGraph,
    path_states: list[State],
    path_edges: list[Edge],
    line_delays: dict[str, int] | None = None,
) -> RouteResult:
    line_delays = line_delays or {}
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

    for edge, state in zip(path_edges, path_states[1:]):
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
    delay_time = sum(line_delays.get(s.line, 0) for s in segments)

    return RouteResult(
        segments=segments,
        total_duration_seconds=ride_time + transfer_time + delay_time,
        total_distance_km=round(sum(s.distance_km for s in segments), 2),
        total_transfers=max(len(segments) - 1, 0),
    )
