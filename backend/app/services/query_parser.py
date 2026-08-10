# This is NOT the NVIDIA NeMo RAG pipeline from the spec -- that needs an
# API key nobody's handed me yet. This is a regex + fuzzy-match stand-in
# that covers "from X to Y" / "X se Y jana hai" phrasing well enough to
# demo end to end, and it's a clean seam to swap in a real LLM call later
# without the caller (the API route) needing to change at all.
#
# Known gap: avoid-line matching only picks up single-word line names
# (Yellow, Blue, ...), not "Airport Express".

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import get_close_matches

_FROM_TO_PATTERNS = [
    re.compile(r"from\s+(?P<from>.+?)\s+to\s+(?P<to>.+?)(?:[.,]|$)", re.I),
    re.compile(r"(?P<from>.+?)\s+se\s+(?P<to>.+?)\s+(?:jana|jaana|tak|jaani)\b", re.I),
]

_AVOID_LINE_PATTERNS = [
    re.compile(r"(?:avoid|without|skip)\s+(?:the\s+)?(?P<line>\w+)\s+line", re.I),
    re.compile(r"(?P<line>\w+)\s+line\s+(?:se\s+)?mat\s+(?:lena|nikalna|jaana)", re.I),
]

_JUNK_WORDS = re.compile(r"\b(station|line|please|jana|jaana|hai|tak)\b", re.I)


@dataclass
class ParsedQuery:
    from_station: str | None
    to_station: str | None
    avoid_lines: list[str] = field(default_factory=list)
    matched: bool = False


def parse_query(text: str, known_stations: set[str], known_lines: set[str]) -> ParsedQuery:
    from_raw, to_raw = _extract_from_to(text)
    from_station = _resolve_station(from_raw, known_stations) if from_raw else None
    to_station = _resolve_station(to_raw, known_stations) if to_raw else None

    return ParsedQuery(
        from_station=from_station,
        to_station=to_station,
        avoid_lines=_extract_avoid_lines(text, known_lines),
        matched=bool(from_station and to_station),
    )


def _extract_from_to(text: str) -> tuple[str | None, str | None]:
    for pattern in _FROM_TO_PATTERNS:
        m = pattern.search(text)
        if m:
            return m.group("from").strip(), m.group("to").strip()
    return None, None


def _extract_avoid_lines(text: str, known_lines: set[str]) -> list[str]:
    found = set()
    for pattern in _AVOID_LINE_PATTERNS:
        for m in pattern.finditer(text):
            candidate = m.group("line").strip().title()
            match = get_close_matches(candidate, known_lines, n=1, cutoff=0.6)
            if match:
                found.add(match[0])
    return sorted(found)


def _resolve_station(raw: str, known_stations: set[str]) -> str | None:
    cleaned = _JUNK_WORDS.sub("", raw).strip()
    if not cleaned:
        return None
    match = get_close_matches(cleaned, known_stations, n=1, cutoff=0.55)
    return match[0] if match else None
