from __future__ import annotations

from pydantic import BaseModel


class SaveRouteRequest(BaseModel):
    user_id: str
    from_station: str
    to_station: str


class SavedRouteResponse(BaseModel):
    from_station: str
    to_station: str
    frequency_count: int
    saved_at: str
