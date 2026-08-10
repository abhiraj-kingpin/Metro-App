from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.route import RouteOption


class NaturalQueryRequest(BaseModel):
    query: str


class UnderstoodIntent(BaseModel):
    from_station: str | None
    to_station: str | None
    avoid_lines: list[str] = Field(default_factory=list)


class NaturalQueryResponse(BaseModel):
    understood: UnderstoodIntent
    routes: list[RouteOption]
