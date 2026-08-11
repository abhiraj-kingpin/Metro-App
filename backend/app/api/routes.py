from __future__ import annotations

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.schemas.disruption import DisruptionHistoryEntry
from app.schemas.line_status import LineStatusResponse, LineStatusUpdate
from app.schemas.query import NaturalQueryRequest, NaturalQueryResponse, UnderstoodIntent
from app.schemas.route import (
    RouteAlert,
    RouteFindRequest,
    RouteFindResponse,
    RouteOption,
    RouteSegmentResponse,
)
from app.schemas.saved_route import SaveRouteRequest, SavedRouteResponse
from app.services import disruption_history, saved_routes as saved_routes_db
from app.services.broadcast import Broadcaster
from app.services.graph_builder import build_graph
from app.services.line_status import LineStatusBoard
from app.services.offline_cache import DEFAULT_DB_PATH, export_to_sqlite
from app.services.query_parser import parse_query
from app.services.routing_engine import (
    RouteConstraints,
    RouteNotFoundError,
    find_k_shortest_paths,
)

router = APIRouter(prefix="/api/v1")

# loaded once at startup, not per-request
_graph = build_graph()
_status_board = LineStatusBoard(known_lines=set(_graph.line_colors))
_broadcaster = Broadcaster()


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
async def set_line_status(line_name: str, body: LineStatusUpdate) -> LineStatusResponse:
    try:
        updated = _status_board.set(line_name, body.status, body.delay_seconds, body.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    disruption_history.record(line_name, updated.status, updated.delay_seconds, updated.reason)
    await _broadcaster.broadcast({
        "type": "LINE_STATUS_UPDATE",
        "line": line_name,
        "status": updated.status,
        "delay_seconds": updated.delay_seconds,
        "reason": updated.reason,
    })
    return LineStatusResponse(
        line=line_name, status=updated.status, delay_seconds=updated.delay_seconds, reason=updated.reason
    )


@router.get("/disruptions/history", response_model=list[DisruptionHistoryEntry])
def get_disruption_history(line: str | None = None, limit: int = 50) -> list[DisruptionHistoryEntry]:
    return [DisruptionHistoryEntry(**row) for row in disruption_history.history(line, limit)]


@router.websocket("/disruptions/live")
async def disruptions_live(websocket: WebSocket) -> None:
    # in-process stand-in for the spec's RabbitMQ/Redis pub-sub -- pushes
    # every status change to whoever's connected, no history/replay
    await _broadcaster.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # not expecting client messages, just keeping the socket open
    except WebSocketDisconnect:
        _broadcaster.disconnect(websocket)


@router.post("/offline/export")
def export_offline_cache() -> dict:
    # snapshots the current graph to a .db a client could download once
    # and route against with zero server contact afterward
    export_to_sqlite(_graph, DEFAULT_DB_PATH)
    return {
        "path": str(DEFAULT_DB_PATH),
        "size_kb": round(DEFAULT_DB_PATH.stat().st_size / 1024, 1),
        "station_count": len(_graph.station_lines),
        "line_count": len(_graph.line_colors),
    }


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
    constraints = RouteConstraints(
        avoid_lines=frozenset(request.preferences.avoid_lines) | _closed_lines(status),
        max_transfers=request.preferences.max_transfers,
    )
    try:
        results = find_k_shortest_paths(
            _graph, request.from_station, request.to_station,
            constraints, k=request.preferences.alternatives, line_delays=_delays(status),
        )
    except RouteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return RouteFindResponse(routes=[_to_route_option(r, status) for r in results])


@router.post("/routes/save", response_model=SavedRouteResponse)
def save_route(request: SaveRouteRequest) -> SavedRouteResponse:
    if not _graph.has_station(request.from_station):
        raise HTTPException(status_code=404, detail=f"Unknown station: {request.from_station}")
    if not _graph.has_station(request.to_station):
        raise HTTPException(status_code=404, detail=f"Unknown station: {request.to_station}")
    return SavedRouteResponse(
        **saved_routes_db.save_route(request.user_id, request.from_station, request.to_station)
    )


@router.get("/routes/saved", response_model=list[SavedRouteResponse])
def get_saved_routes(user_id: str) -> list[SavedRouteResponse]:
    return [SavedRouteResponse(**r) for r in saved_routes_db.list_routes(user_id)]


@router.post("/query/natural", response_model=NaturalQueryResponse)
def query_natural(request: NaturalQueryRequest) -> NaturalQueryResponse:
    parsed = parse_query(request.query, set(_graph.station_lines), set(_graph.line_colors))
    understood = UnderstoodIntent(
        from_station=parsed.from_station, to_station=parsed.to_station, avoid_lines=parsed.avoid_lines
    )
    if not parsed.matched:
        raise HTTPException(
            status_code=422,
            detail=f"couldn't confidently pick both stations out of that query -- got {understood.model_dump()}",
        )

    status = _status_board.all()
    constraints = RouteConstraints(
        avoid_lines=frozenset(parsed.avoid_lines) | _closed_lines(status),
    )
    try:
        results = find_k_shortest_paths(
            _graph, parsed.from_station, parsed.to_station, constraints, k=3, line_delays=_delays(status),
        )
    except RouteNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return NaturalQueryResponse(
        understood=understood, routes=[_to_route_option(r, status) for r in results]
    )


def _closed_lines(status) -> set[str]:
    return {line for line, s in status.items() if s.status == "CLOSED"}


def _delays(status) -> dict[str, int]:
    return {line: s.delay_seconds for line, s in status.items() if s.status == "DELAYED"}


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
