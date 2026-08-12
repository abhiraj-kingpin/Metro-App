# run with (from backend/): pytest -v

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.graph_builder import build_graph
from app.services.query_parser import parse_query

graph = build_graph()
STATIONS = set(graph.station_lines)
LINES = set(graph.line_colors)


def test_parses_simple_english_from_to():
    result = parse_query("I want to go from Chandni Chowk to Barakhamba Road", STATIONS, LINES)
    assert result.from_station == "Chandni Chowk"
    assert result.to_station == "Barakhamba Road"
    assert result.matched


def test_parses_hinglish_from_to():
    result = parse_query("Dwarka Sector 21 se Rajiv Chowk jana hai", STATIONS, LINES)
    assert result.from_station == "Dwarka Sector 21"
    assert result.to_station == "Rajiv Chowk"
    assert result.matched


def test_extracts_avoid_line_english():
    result = parse_query("from Rajiv Chowk to Central Secretariat, avoid Yellow line", STATIONS, LINES)
    assert result.avoid_lines == ["Yellow"]


def test_extracts_avoid_line_hinglish():
    result = parse_query(
        "Rajiv Chowk se Central Secretariat jana hai, Yellow Line se mat nikalna", STATIONS, LINES
    )
    assert "Yellow" in result.avoid_lines


def test_handles_minor_typos_via_fuzzy_match():
    result = parse_query("from Rajiv Chwok to Barakhamba Road", STATIONS, LINES)
    assert result.from_station == "Rajiv Chowk"


def test_unrecognizable_stations_leave_matched_false():
    result = parse_query("from Nowhereville to Somewhereton", STATIONS, LINES)
    assert not result.matched


def test_no_from_to_pattern_leaves_both_none():
    result = parse_query("what time does the metro close", STATIONS, LINES)
    assert result.from_station is None
    assert result.to_station is None
    assert not result.matched


def test_handles_case_and_spacing_variations():
    result = parse_query("from noida sector 51 to  pari chowk", STATIONS, LINES)
    assert result.from_station == "Noida Sector 51"
    assert result.to_station == "Pari Chowk"
    assert result.matched
