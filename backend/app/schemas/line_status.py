from __future__ import annotations

from pydantic import BaseModel


class LineStatusUpdate(BaseModel):
    status: str  # OPERATIONAL | DELAYED | CLOSED
    delay_seconds: int = 0
    reason: str | None = None


class LineStatusResponse(BaseModel):
    line: str
    status: str
    delay_seconds: int
    reason: str | None = None
