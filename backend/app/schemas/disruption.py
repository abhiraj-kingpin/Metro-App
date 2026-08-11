from __future__ import annotations

from pydantic import BaseModel


class DisruptionHistoryEntry(BaseModel):
    line: str
    status: str
    delay_seconds: int
    reason: str | None
    recorded_at: str
