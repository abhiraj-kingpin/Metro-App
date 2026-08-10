"""Pydantic request/response models for the route-finding endpoint.

This is a trimmed-down version of the full API_DOCUMENTATION.md contract in
docs/PROJECT_SPEC.md: platform-level detail, live disruption alerts, and
GPS-based ETA are not part of this lean-MVP slice yet (see docs/ROADMAP.md).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class RoutePreferences(BaseModel):
    max_transfers: int = 4
    avoid_lines: list[str] = Field(default_factory=list)


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


class RouteFindResponse(BaseModel):
    segments: list[RouteSegmentResponse]
    total_duration_seconds: int
    total_distance_km: float
    total_transfers: int
    eta_minutes: int
