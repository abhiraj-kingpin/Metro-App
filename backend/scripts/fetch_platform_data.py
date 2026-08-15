# Fetches platform_type/platform_count for single-line DMRC stations from
# each station's Wikipedia infobox wikitext -- there's no structured API
# property for this (unlike coordinates), so this reads the raw
# "| platform" / "| platforms" template field and parses it directly.
#
# Deliberately conservative: a station only gets a value if exactly one
# platform type ([[Island platform]] or [[Side platform]]) appears in its
# field and at least one "Platform-N" entry can be counted. Anything
# mixed, missing, or oddly formatted goes to needs_review instead of
# being guessed. Interchange (same-name, multi-line) stations are
# EXCLUDED entirely -- their platform data is routinely split by line
# (see Rajiv Chowk: Island for Yellow, Side for Blue) and needs the
# per-line schema handled separately, not this script.
#
# Run with (from backend/): python scripts/fetch_platform_data.py

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "app" / "data" / "metro_data.json"
OUTPUT_FILE = Path(__file__).resolve().parent / "platform_data_fetched.json"
USER_AGENT = "delhi-metro-navigator-research/1.0 (personal portfolio project)"
REQUEST_DELAY_SECONDS = 1.0
MAX_RETRIES = 4

API = "https://en.wikipedia.org/w/api.php"

PLATFORM_FIELD = re.compile(r"^\s*\|\s*platforms?\s*=(.*)$", re.IGNORECASE)
PLATFORM_TYPE = re.compile(r"\[\[(Island platform|Side platform)", re.IGNORECASE)
# "Platform-1" (most lines) and "Platform 1" inside a {{font color|...}}
# template (Pink Line's circular-route articles use this format instead)
PLATFORM_NUMBER = re.compile(r"Platforms?[\s-]+\d+", re.IGNORECASE)


def _api_get(params: dict) -> dict:
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    backoff = 3.0
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < MAX_RETRIES - 1:
                time.sleep(backoff)
                backoff *= 2
                continue
            raise
    raise RuntimeError("unreachable")


def _title_looks_like_station(title: str, station: str) -> bool:
    station_words = {w.lower() for w in re.findall(r"[A-Za-z0-9]+", station)}
    title_lower = title.lower()
    return all(w in title_lower for w in station_words)


def _fetch_wikitext(title: str) -> tuple[str, str] | None:
    data = _api_get({
        "action": "query", "titles": title, "prop": "revisions",
        "rvprop": "content", "rvslots": "main", "format": "json", "redirects": 1,
    })
    page = next(iter(data["query"]["pages"].values()))
    if "revisions" not in page:
        return None
    content = page["revisions"][0]["slots"]["main"]["*"]
    return content, page["title"]


def parse_platform_field(wikitext: str) -> str | None:
    for line in wikitext.split("\n"):
        m = PLATFORM_FIELD.match(line)
        if m:
            return m.group(1)
    return None


def parse_platform_info(field_value: str) -> tuple[str, int] | None:
    types_found = {t.title() for t in PLATFORM_TYPE.findall(field_value)}
    if len(types_found) != 1:
        return None  # 0 = nothing recognizable, 2+ = mixed -- either way, don't guess
    count = len(PLATFORM_NUMBER.findall(field_value))
    if count == 0:
        return None
    platform_type = "ISLAND" if "Island" in next(iter(types_found)) else "SIDE"
    return platform_type, count


def fetch_platform_data(station: str) -> dict | None:
    direct_title = f"{station} metro station"
    result = _fetch_wikitext(direct_title)

    if result is None or not _title_looks_like_station(result[1], station):
        time.sleep(REQUEST_DELAY_SECONDS)
        search = _api_get({
            "action": "query", "list": "search", "srsearch": f"{station} Delhi Metro station",
            "format": "json", "srlimit": 1,
        })
        hits = search["query"]["search"]
        if not hits or not _title_looks_like_station(hits[0]["title"], station):
            return None
        time.sleep(REQUEST_DELAY_SECONDS)
        result = _fetch_wikitext(hits[0]["title"])
        if result is None:
            return None

    wikitext, title = result
    field = parse_platform_field(wikitext)
    if field is None:
        return None
    parsed = parse_platform_info(field)
    if parsed is None:
        return None
    platform_type, count = parsed
    return {
        "platform_type": platform_type,
        "platform_count": count,
        "title": title,
        "raw_field": field.strip(),
    }


def main() -> None:
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    station_lines: dict[str, set[str]] = {}
    for line in raw["lines"]:
        for segment in line["segments"]:
            for station in segment:
                station_lines.setdefault(station, set()).add(line["name"])

    meta = raw.get("station_metadata", {})
    single_line_missing = sorted(
        s for s, lines in station_lines.items()
        if len(lines) == 1 and "platform_type" not in meta.get(s, {})
    )

    confident: dict[str, dict] = {}
    if OUTPUT_FILE.exists():
        prior = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
        confident = prior.get("confident", {})

    todo = [s for s in single_line_missing if s not in confident]
    print(f"{len(single_line_missing)} single-line stations missing platform data, "
          f"{len(confident)} already confident from a prior run, {len(todo)} left to fetch\n")

    needs_review: list[str] = []

    for i, station in enumerate(todo, 1):
        try:
            result = fetch_platform_data(station)
        except Exception as exc:
            print(f"[{i}/{len(todo)}] {station}: ERROR {exc}")
            needs_review.append(station)
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        if result is None:
            print(f"[{i}/{len(todo)}] {station}: no confident parse")
            needs_review.append(station)
        else:
            print(f"[{i}/{len(todo)}] {station}: {result['platform_type']}, "
                  f"{result['platform_count']} platforms ({result['title']})")
            confident[station] = {
                "platform_type": result["platform_type"],
                "platform_count": result["platform_count"],
                "source_url": f"https://en.wikipedia.org/wiki/{result['title'].replace(' ', '_')}",
                "raw_field": result["raw_field"],
            }
        time.sleep(REQUEST_DELAY_SECONDS)

    OUTPUT_FILE.write_text(
        json.dumps({"confident": confident, "needs_review": needs_review}, indent=2), encoding="utf-8"
    )
    print(f"\n{len(confident)} confident matches, {len(needs_review)} need manual review")
    print(f"written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
