from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.line_status import LineStatusResponse, LineStatusUpdate
from app.schemas.route import (
    RouteAlert,
    RouteFindRequest,
    RouteFindResponse,
    RouteOption,
    RouteSegmentResponse,
)
from app.services.graph_builder import build_graph
from app.services.line_status import LineStatusBoard
from app.services.routing_engine import (
    RouteConstraints,
    RouteNotFoundError,
    find_k_shortest_paths,
)

router = APIRouter(prefix="/api/v1")

# loaded once at startup, not per-request
_graph = build_graph()
_status_board = LineStatusBoard(known_lines=set(_graph.line_colors))


@router.get("/lines")
def list_lines() -> list[dict]:
    return [{"name": name, "color": color} for name, color in sorted(_graph.line_colors.items())]


@router.get("/lines/status")
def get_all_line_status() -> list[LineStatusResponse]:
    return [
        LineStatusResponse(line=line, status=s.status, delay_seconds=s.delay_seconds, reason=s.reason)
        for line, s in sorted(_status_board.all().items())
    ]


@router.post("/lines/{line_name}/status")
def set_line_status(line_name: str, body: LineStatusUpdate) -> LineStatusResponse:
    try:
        updated = _status_board.set(line_name, body.status, body.delay_seconds, body.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return LineStatusResponse(
        line=line_name, status=updated.status, delay_seconds=updated.delay_seconds, reason=updated.reason
    )


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
    status = _status_board.all()
    closed = {line for line, s in status.items() if s.status == "CLOSED"}
    delays = {line: s.delay_seconds for line, s in status.items() if s.status == "DELAYED"}

    constraints = RouteConstraints(
        avoid_lines=frozenset(request.preferences.avoid_lines) | closed,
        max_transfers=request.preferences.max_transfers,
    )
    try:
        results = find_k_shortest_paths(
            _graph, request.from_station, request.to_station,
            constraints, k=request.preferences.alternatives, line_delays=delays,
        )
    except RouteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    routes = [_to_route_option(result, status) for result in results]
    return RouteFindResponse(routes=routes)


def _to_route_option(result, status) -> RouteOption:
    lines_used = {s.line for s in result.segments}
    alerts = [
        RouteAlert(
            type="DELAY",
            line=line,
            message=f"{line} Line is running with a {status[line].delay_seconds // 60}-minute delay"
            + (f" ({status[line].reason})" if status[line].reason else ""),
        )
        for line in lines_used
        if status[line].status == "DELAYED" and status[line].delay_seconds > 0
    ]
    return RouteOption(
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
        alerts=alerts,
    )
