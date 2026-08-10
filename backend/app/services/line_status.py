# In-memory stand-in for what would eventually be a Redis-backed board fed
# by DMRC polling / WebSocket pushes. Same idea, just no moving parts yet:
# a dict, a lock, done. Swap the internals for Redis later without
# touching anything that calls this.

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock

VALID_STATUSES = {"OPERATIONAL", "DELAYED", "CLOSED"}


@dataclass
class LineStatus:
    status: str = "OPERATIONAL"
    delay_seconds: int = 0
    reason: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class LineStatusBoard:
    def __init__(self, known_lines: set[str]):
        self._lock = Lock()
        self._board: dict[str, LineStatus] = {line: LineStatus() for line in known_lines}

    def all(self) -> dict[str, LineStatus]:
        with self._lock:
            return dict(self._board)

    def get(self, line: str) -> LineStatus:
        with self._lock:
            return self._board.get(line, LineStatus())

    def set(self, line: str, status: str, delay_seconds: int = 0, reason: str | None = None) -> LineStatus:
        if status not in VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(VALID_STATUSES)}, got {status!r}")
        if line not in self._board:
            raise KeyError(f"unknown line: {line!r}")
        entry = LineStatus(status=status, delay_seconds=max(delay_seconds, 0), reason=reason)
        with self._lock:
            self._board[line] = entry
        return entry

    def closed_lines(self) -> set[str]:
        with self._lock:
            return {line for line, s in self._board.items() if s.status == "CLOSED"}

    def delay_seconds_by_line(self) -> dict[str, int]:
        with self._lock:
            return {
                line: s.delay_seconds
                for line, s in self._board.items()
                if s.status == "DELAYED" and s.delay_seconds > 0
            }
