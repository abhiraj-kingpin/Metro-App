from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.route import (
    RouteFindRequest,
    RouteFindResponse,
    RouteOption,
    RouteSegmentResponse,
)
from app.services.graph_builder import build_graph
from app.services.routing_engine import (
    RouteConstraints,
    RouteNotFoundError,
    find_k_shortest_paths,
)

router = APIRouter(prefix="/api/v1")

# loaded once at startup, not per-request
_graph = build_graph()


@router.get("/lines")
def list_lines() -> list[dict]:
    return [{"name": name, "color": color} for name, color in sorted(_graph.line_colors.items())]


@router.get("/stations")
def list_stations(q: str | None = None) -> list[dict]:
    names = sorted(_graph.station_lines)
    if q:
        needle = q.lower()
        names = [n for n in names if needle in n.lower()]
    return [{"name": name, "lines": sorted(_graph.station_lines[name])} for name in names]


@router.get("/stations/{station_name}")
def get_station(station_name: str) -> dict:
    if not _graph.has_station(station_name):
        raise HTTPException(status_code=404, detail=f"Unknown station: {station_name}")
    return {"name": station_name, "lines": sorted(_graph.lines_at(station_name))}


@router.post("/routes/find", response_model=RouteFindResponse)
def find_route(request: RouteFindRequest) -> RouteFindResponse:
    constraints = RouteConstraints(
        avoid_lines=frozenset(request.preferences.avoid_lines),
        max_transfers=request.preferences.max_transfers,
    )
    try:
        results = find_k_shortest_paths(
            _graph, request.from_station, request.to_station,
            constraints, k=request.preferences.alternatives,
        )
    except RouteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    routes = [
        RouteOption(
            segments=[
                RouteSegmentResponse(
                    from_station=s.from_station,
                    to_station=s.to_station,
                    line=s.line,
                    line_color=s.line_color,
                    stations=s.stations,
                    stops_count=s.stops_count,
                    distance_km=s.distance_km,
                    duration_seconds=s.duration_seconds,
                )
                for s in result.segments
            ],
            total_duration_seconds=result.total_duration_seconds,
            total_distance_km=result.total_distance_km,
            total_transfers=result.total_transfers,
            eta_minutes=round(result.total_duration_seconds / 60),
        )
        for result in results
    ]
    return RouteFindResponse(routes=routes)
