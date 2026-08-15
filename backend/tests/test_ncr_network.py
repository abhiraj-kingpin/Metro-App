# Tests for the NMRC Aqua Line + Rapid Metro Gurugram additions, and the
# fixes made to existing DMRC data while verifying against them (see
# metro_data.json's _note for what changed and why).
#
# run with (from backend/): pytest -v

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.graph_builder import build_graph
from app.services.routing_engine import RouteConstraints, RouteNotFoundError, find_shortest_path

graph = build_graph()

AQUA_STATIONS_IN_ORDER = [
    "Noida Sector 51", "Rainbow", "Noida Sector 76", "Noida Sector 101",
    "Noida Sector 81", "NSEZ", "Noida Sector 83", "Noida Sector 137",
    "Noida Sector 142", "Noida Sector 143", "Noida Sector 144", "Noida Sector 145",
    "Noida Sector 146", "Noida Sector 147", "Noida Sector 148", "Knowledge Park II",
    "Pari Chowk", "Alpha 1", "Delta 1", "GNIDA Office", "Depot",
]

RAPID_METRO_STATIONS_IN_ORDER = [
    "Sikanderpur", "DLF Phase 2", "Belvedere Towers", "Cyber City", "Moulsari Avenue",
    "DLF Phase 3", "DLF Phase 1", "Sector 42-43", "Sector 53-54", "Sector 54 Chowk",
    "Sector 55-56",
]


# --- Aqua Line data ---------------------------------------------------

def test_aqua_line_has_exactly_21_operational_stations():
    aqua_stations = {st for st, lines in graph.station_lines.items() if "Aqua" in lines}
    assert len(aqua_stations) == 21
    assert aqua_stations == set(AQUA_STATIONS_IN_ORDER)


def test_aqua_line_stations_are_consecutively_connected():
    for a, b in zip(AQUA_STATIONS_IN_ORDER, AQUA_STATIONS_IN_ORDER[1:]):
        forward = [e for e in graph.adjacency[(a, "Aqua")] if e.to_station == b and not e.is_transfer]
        backward = [e for e in graph.adjacency[(b, "Aqua")] if e.to_station == a and not e.is_transfer]
        assert forward, f"missing Aqua edge {a} -> {b}"
        assert backward, f"missing Aqua edge {b} -> {a}"


def test_aqua_line_endpoints():
    assert AQUA_STATIONS_IN_ORDER[0] == "Noida Sector 51"
    assert AQUA_STATIONS_IN_ORDER[-1] == "Depot"


def test_aqua_line_excludes_future_extension_stations():
    # Knowledge Park V and Boraki are proposed/under-construction extensions,
    # not part of the operational network -- must not be present anywhere
    all_stations = set(graph.station_lines)
    for future_station in ("Knowledge Park V", "Boraki"):
        assert future_station not in all_stations


# --- Rapid Metro data ---------------------------------------------------

def test_rapid_metro_has_exactly_11_operational_stations():
    rm_stations = {st for st, lines in graph.station_lines.items() if "Rapid Metro" in lines}
    assert len(rm_stations) == 11
    assert rm_stations == set(RAPID_METRO_STATIONS_IN_ORDER)


def test_rapid_metro_stations_are_consecutively_connected():
    for a, b in zip(RAPID_METRO_STATIONS_IN_ORDER, RAPID_METRO_STATIONS_IN_ORDER[1:]):
        forward = [e for e in graph.adjacency[(a, "Rapid Metro")] if e.to_station == b and not e.is_transfer]
        backward = [e for e in graph.adjacency[(b, "Rapid Metro")] if e.to_station == a and not e.is_transfer]
        assert forward, f"missing Rapid Metro edge {a} -> {b}"
        assert backward, f"missing Rapid Metro edge {b} -> {a}"


def test_rapid_metro_endpoints():
    assert RAPID_METRO_STATIONS_IN_ORDER[0] == "Sikanderpur"
    assert RAPID_METRO_STATIONS_IN_ORDER[-1] == "Sector 55-56"


def test_rapid_metro_interchanges_with_dmrc_yellow_at_sikanderpur():
    # same-name interchange, not a named pair -- Sikanderpur is one
    # physical complex shared by both lines
    assert graph.lines_at("Sikanderpur") == {"Yellow", "Rapid Metro"}


# --- operators ---------------------------------------------------

def test_operators_assigned_correctly():
    assert graph.line_operators["Aqua"] == "NMRC"
    assert graph.line_operators["Rapid Metro"] == "RAPID_METRO"
    for dmrc_line in ("Yellow", "Blue", "Violet", "Pink", "Magenta", "Red", "Airport Express", "Green", "Grey"):
        assert graph.line_operators[dmrc_line] == "DMRC"


# --- named (walkway) interchange: Aqua's Sector 51 <-> Blue's Sector 52 ---

def test_named_interchange_is_bidirectional_and_symmetric():
    out_51 = [e for e in graph.adjacency[("Noida Sector 51", "Aqua")] if e.to_station == "Noida Sector 52"]
    out_52 = [e for e in graph.adjacency[("Noida Sector 52", "Blue")] if e.to_station == "Noida Sector 51"]
    assert len(out_51) == 1 and len(out_52) == 1
    assert out_51[0].is_transfer and out_52[0].is_transfer
    assert out_51[0].duration_seconds == out_52[0].duration_seconds == 420


# --- routing across operators ---------------------------------------------------

def test_same_line_aqua_journey():
    result = find_shortest_path(graph, "Noida Sector 51", "Pari Chowk")
    assert result.total_transfers == 0
    assert {s.line for s in result.segments} == {"Aqua"}


def test_same_line_rapid_metro_journey():
    result = find_shortest_path(graph, "Sikanderpur", "Cyber City")
    assert result.total_transfers == 0
    assert result.segments[0].line == "Rapid Metro"


def test_dmrc_to_rapid_metro():
    result = find_shortest_path(graph, "Rajiv Chowk", "Cyber City")
    lines_used = {s.line for s in result.segments}
    assert lines_used == {"Yellow", "Rapid Metro"}
    assert result.total_transfers == 1


def test_rapid_metro_to_dmrc():
    result = find_shortest_path(graph, "Cyber City", "Rajiv Chowk")
    lines_used = {s.line for s in result.segments}
    assert lines_used == {"Yellow", "Rapid Metro"}
    assert result.total_transfers == 1


def test_dmrc_to_aqua():
    result = find_shortest_path(graph, "Rajiv Chowk", "Pari Chowk")
    lines_used = {s.line for s in result.segments}
    assert lines_used == {"Blue", "Aqua"}
    assert result.total_transfers == 1
    assert result.segments[0].to_station == "Noida Sector 52"
    assert result.segments[-1].from_station == "Noida Sector 51"


def test_aqua_to_dmrc():
    result = find_shortest_path(graph, "Pari Chowk", "Rajiv Chowk")
    lines_used = {s.line for s in result.segments}
    assert lines_used == {"Blue", "Aqua"}
    assert result.total_transfers == 1


def test_aqua_to_rapid_metro_is_a_multi_hop_dmrc_route():
    # no direct Aqua<->Rapid Metro interchange exists -- this has to route
    # through DMRC, which is the whole point of the test
    result = find_shortest_path(graph, "Pari Chowk", "Cyber City")
    assert result.segments[0].line == "Aqua"
    assert result.segments[-1].line == "Rapid Metro"
    assert result.total_transfers >= 2


def test_invalid_station_still_raises():
    with pytest.raises(RouteNotFoundError):
        find_shortest_path(graph, "Noida Sector 999", "Pari Chowk")


def test_same_origin_and_destination_on_new_lines():
    result = find_shortest_path(graph, "Pari Chowk", "Pari Chowk")
    assert result.segments == []


def test_avoiding_blue_disconnects_aqua_from_dmrc():
    # Noida Sector 52 (the only bridge to the Aqua walkway) is Blue-only,
    # so avoiding Blue should sever the connection entirely
    constraints = RouteConstraints(avoid_lines=frozenset({"Blue"}))
    with pytest.raises(RouteNotFoundError):
        find_shortest_path(graph, "Pari Chowk", "Rajiv Chowk", constraints)


# --- data integrity ---------------------------------------------------

def test_no_duplicate_edges_anywhere():
    for (station, line), edges in graph.adjacency.items():
        seen = set()
        for e in edges:
            key = (e.to_station, e.line, e.is_transfer)
            assert key not in seen, f"duplicate edge from ({station}, {line}) to {key}"
            seen.add(key)


def test_no_orphan_stations():
    for station, lines in graph.station_lines.items():
        has_edge = any(graph.adjacency.get((station, line)) for line in lines)
        assert has_edge, f"{station} has no outgoing edges on any of its lines"


# --- station metadata (coordinates / platform info) ---------------------------------------------------

# rough Delhi-NCR bounding box -- catches gross errors (swapped lat/lng,
# wrong sign, wrong region entirely), not a precision check
NCR_LAT_RANGE = (28.0, 29.0)
NCR_LNG_RANGE = (76.5, 78.0)


def test_every_new_station_has_sourced_metadata():
    for station in AQUA_STATIONS_IN_ORDER + RAPID_METRO_STATIONS_IN_ORDER:
        assert station in graph.station_metadata, f"{station} is missing station_metadata"
        meta = graph.station_metadata[station]
        assert "coordinates" in meta
        assert "source_url" in meta and meta["source_url"].startswith("https://en.wikipedia.org/wiki/")


def test_metadata_coordinates_are_within_ncr():
    for station, meta in graph.station_metadata.items():
        lat, lng = meta["coordinates"]["lat"], meta["coordinates"]["lng"]
        assert NCR_LAT_RANGE[0] <= lat <= NCR_LAT_RANGE[1], f"{station} latitude {lat} looks wrong"
        assert NCR_LNG_RANGE[0] <= lng <= NCR_LNG_RANGE[1], f"{station} longitude {lng} looks wrong"


def test_rainbow_rename_replaced_noida_sector_50():
    assert "Noida Sector 50" not in graph.station_lines
    assert "Rainbow" in graph.station_lines
    assert graph.lines_at("Rainbow") == {"Aqua"}


def test_rohini_rename_replaced_rohini_east():
    assert "Rohini East" not in graph.station_lines
    assert "Rohini" in graph.station_lines
    assert graph.lines_at("Rohini") == {"Red"}


def test_dmrc_stations_now_have_sourced_coordinates():
    # a later pass added coordinates for almost all 207 DMRC stations too,
    # not just the 32 Aqua/Rapid Metro ones from the earlier pass
    for station in ("Rajiv Chowk", "Dwarka Sector 21", "Kashmere Gate"):
        assert station in graph.station_metadata
        assert "coordinates" in graph.station_metadata[station]

    # DMRC entries are coordinates-only -- no platform_type/count for these,
    # unlike the hand-checked Aqua/Rapid Metro entries
    assert "platform_type" not in graph.station_metadata["Rajiv Chowk"]


def test_pitampura_and_mayur_vihar_pocket_i_now_resolved():
    # were the last 2 documented coordinate gaps -- Pitampura's Wikipedia
    # article redirected to a different station (Madhuban Chowk, which
    # Pitampura was renamed to), Mayur Vihar Pocket I had no Wikipedia
    # infobox coordinate under either name. Both resolved via Wikidata,
    # cross-verified against a directly-fetched OSM node each -- see the
    # "note" field on each entry in metro_data.json for the full trail.
    assert "Pitampura" in graph.station_metadata
    assert "Mayur Vihar Pocket I" in graph.station_metadata
    assert graph.has_station("Pitampura")
    assert graph.has_station("Mayur Vihar Pocket I")
    # topology deliberately untouched -- still under their existing names,
    # not renamed to Madhuban Chowk / Shree Ram Mandir Mayur Vihar
    assert graph.lines_at("Pitampura") == {"Red"}
    assert graph.lines_at("Mayur Vihar Pocket I") == {"Pink"}


def test_all_stations_have_metadata_now():
    total = len(graph.station_lines)
    with_metadata = len(graph.station_metadata)
    assert total == with_metadata == 239
    assert with_metadata / total > 0.99


# --- platform data ---------------------------------------------------

def _platform_coverage():
    with_platform = 0
    for station, lines in graph.station_lines.items():
        meta = graph.station_metadata.get(station, {})
        if len(lines) == 1:
            if "platform_type" in meta:
                with_platform += 1
        else:
            if "platforms_by_line" in meta or "platform_type" in meta:
                with_platform += 1
    return with_platform


def test_single_line_platform_data_spot_checks():
    # a mix of stations resolved by the automated script vs by the
    # font-color-template regex fix vs disambiguated-title retries
    checks = {
        "Kohat Enclave": ("SIDE", 2),
        "Shivaji Stadium": ("ISLAND", 2),
        "Chandni Chowk": ("ISLAND", 2),  # needed the (Delhi) disambiguation suffix
        "Lal Quila": ("ISLAND", 2),  # Wikipedia title is actually "Lal Qila"
        "Qutub Minar": ("SIDE", 2),  # Wikipedia title is actually "Qutab Minar"
    }
    for station, (ptype, count) in checks.items():
        meta = graph.station_metadata[station]
        assert meta["platform_type"] == ptype, station
        assert meta["platform_count"] == count, station


def test_single_line_platform_coverage_is_near_complete():
    single_line = [s for s, lines in graph.station_lines.items() if len(lines) == 1]
    resolved = [s for s in single_line if "platform_type" in graph.station_metadata.get(s, {})]
    unresolved = sorted(set(single_line) - set(resolved))
    # exactly the 3 stations no source had usable platform data for
    assert unresolved == ["Jama Masjid", "Mayur Vihar Pocket I", "Yashobhoomi Dwarka Sector 25"]


def test_interchange_platform_data_uses_per_line_schema():
    meta = graph.station_metadata["Rajiv Chowk"]
    assert "platform_type" not in meta  # no single value applies at an interchange
    assert meta["platforms_by_line"] == {
        "Yellow": {"platform_type": "ISLAND", "platform_count": 2},
        "Blue": {"platform_type": "SIDE", "platform_count": 2},
    }


def test_three_way_interchange_platform_data():
    meta = graph.station_metadata["Kashmere Gate"]
    by_line = meta["platforms_by_line"]
    assert set(by_line) == {"Yellow", "Red", "Violet"}
    assert by_line["Yellow"] == {"platform_type": "ISLAND", "platform_count": 2}
    assert by_line["Red"] == {"platform_type": "SIDE", "platform_count": 2}
    assert by_line["Violet"] == {"platform_type": "ISLAND", "platform_count": 2}


def test_sikanderpur_platforms_split_by_operator():
    # was a flat, ambiguous value before this pass (sourced from the
    # Rapid Metro page only, never verified for the DMRC Yellow side) --
    # now properly split and both sides independently verified
    by_line = graph.station_metadata["Sikanderpur"]["platforms_by_line"]
    assert by_line["Yellow"] == {"platform_type": "SIDE", "platform_count": 2}
    assert by_line["Rapid Metro"] == {"platform_type": "SIDE", "platform_count": 2}


def test_dwarka_stations_honestly_unresolved():
    # Dwarka's infobox states a bare total ("5") with no type or per-line
    # breakdown; Dwarka Sector 21's platform field is entirely empty --
    # neither has a trustworthy per-line value, so neither was populated
    assert "platforms_by_line" not in graph.station_metadata.get("Dwarka", {})
    assert "platforms_by_line" not in graph.station_metadata.get("Dwarka Sector 21", {})


def test_terminal_1_igi_airport_only_has_magenta_data():
    # Airport Express deliberately not populated here -- research for this
    # task found Airport Express doesn't actually serve Terminal 1 in
    # reality (it serves Terminals 2/3 via a different station), meaning
    # this repo's Airport Express+Magenta interchange at this name may
    # itself be a topology error. Not fixed here (out of scope), but not
    # populated with unverifiable data either.
    by_line = graph.station_metadata["Terminal 1 IGI Airport"]["platforms_by_line"]
    assert by_line == {"Magenta": {"platform_type": "ISLAND", "platform_count": 2}}
    assert "Airport Express" not in by_line


def test_platform_coverage_is_near_complete_overall():
    total = len(graph.station_lines)
    covered = _platform_coverage()
    assert covered / total > 0.85
