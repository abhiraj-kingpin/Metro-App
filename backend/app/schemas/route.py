from __future__ import annotations

from pydantic import BaseModel, Field


class RoutePreferences(BaseModel):
    max_transfers: int = 4
    avoid_lines: list[str] = Field(default_factory=list)
    alternatives: int = Field(default=3, ge=1, le=5)


class RouteFindRequest(BaseModel):
    from_station: str
    to_station: str
    preferences: RoutePreferences = Field(default_factory=RoutePreferences)


class RouteSegmentResponse(BaseModel):
    from_station: str
    to_station: str
    line: str
    line_color: str
    stations: list[str]
    stops_count: int
    distance_km: float
    duration_seconds: int


class RouteOption(BaseModel):
    segments: list[RouteSegmentResponse]
    total_duration_seconds: int
    total_distance_km: float
    total_transfers: int
    eta_minutes: int


class RouteFindResponse(BaseModel):
    routes: list[RouteOption]
