# Fetches GPS coordinates for real DMRC stations from Wikipedia's
# structured coordinates API (prop=coordinates) -- not a regex scrape of
# rendered HTML. Station names come from this repo's own metro_data.json,
# not an invented list. Anything the title-match check isn't confident
# about goes into "needs_review" rather than getting written as fact.
#
# Run with (from backend/): python scripts/fetch_station_coordinates.py

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "app" / "data" / "metro_data.json"
OUTPUT_FILE = Path(__file__).resolve().parent / "dmrc_coordinates_fetched.json"
USER_AGENT = "delhi-metro-navigator-research/1.0 (personal portfolio project)"
REQUEST_DELAY_SECONDS = 1.0
MAX_RETRIES = 4

API = "https://en.wikipedia.org/w/api.php"


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
    # every token in the station name (including sector numbers -- those
    # matter, "Sector 8" and "Sector 21" must not get confused) has to
    # show up in the matched title
    station_words = {w.lower() for w in re.findall(r"[A-Za-z0-9]+", station)}
    title_lower = title.lower()
    return all(w in title_lower for w in station_words)


def fetch_coordinates(station: str) -> dict | None:
    direct_title = f"{station} metro station"
    data = _api_get({
        "action": "query", "titles": direct_title, "prop": "coordinates",
        "format": "json", "redirects": 1,
    })
    page = next(iter(data["query"]["pages"].values()))
    if "coordinates" in page and _title_looks_like_station(page["title"], station):
        return {
            "lat": page["coordinates"][0]["lat"], "lng": page["coordinates"][0]["lon"],
            "title": page["title"], "method": "direct",
        }

    time.sleep(REQUEST_DELAY_SECONDS)
    search = _api_get({
        "action": "query", "list": "search", "srsearch": f"{station} Delhi Metro station",
        "format": "json", "srlimit": 1,
    })
    hits = search["query"]["search"]
    if not hits or not _title_looks_like_station(hits[0]["title"], station):
        return None

    title = hits[0]["title"]
    time.sleep(REQUEST_DELAY_SECONDS)
    data = _api_get({"action": "query", "titles": title, "prop": "coordinates", "format": "json"})
    page = next(iter(data["query"]["pages"].values()))
    if "coordinates" not in page:
        return None
    return {
        "lat": page["coordinates"][0]["lat"], "lng": page["coordinates"][0]["lon"],
        "title": page["title"], "method": "search-fallback",
    }


def main() -> None:
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    already_have = set(raw.get("station_metadata", {}))

    all_stations: set[str] = set()
    for line in raw["lines"]:
        for segment in line["segments"]:
            all_stations.update(segment)

    # resumable: a prior run's confident matches don't need re-fetching,
    # and a prior run's failures (rate limits included) get retried
    confident: dict[str, dict] = {}
    if OUTPUT_FILE.exists():
        prior = json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
        confident = prior.get("confident", {})

    todo = sorted(all_stations - already_have - set(confident))
    print(
        f"{len(all_stations)} total stations, {len(already_have)} already sourced, "
        f"{len(confident)} confident from a prior run, {len(todo)} left to fetch\n"
    )

    needs_review: list[str] = []

    for i, station in enumerate(todo, 1):
        try:
            result = fetch_coordinates(station)
        except Exception as exc:
            print(f"[{i}/{len(todo)}] {station}: ERROR {exc}")
            needs_review.append(station)
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        if result is None:
            print(f"[{i}/{len(todo)}] {station}: no confident match")
            needs_review.append(station)
        else:
            print(
                f"[{i}/{len(todo)}] {station}: {result['lat']:.4f}, {result['lng']:.4f} "
                f"({result['method']}, {result['title']})"
            )
            confident[station] = {
                "coordinates": {"lat": result["lat"], "lng": result["lng"]},
                "source_url": f"https://en.wikipedia.org/wiki/{result['title'].replace(' ', '_')}",
            }
        time.sleep(REQUEST_DELAY_SECONDS)

    OUTPUT_FILE.write_text(
        json.dumps({"confident": confident, "needs_review": needs_review}, indent=2), encoding="utf-8"
    )
    print(f"\n{len(confident)} confident matches, {len(needs_review)} need manual review")
    print(f"written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
