"""Builds an in-memory routing graph from the static metro topology data.

Graph model
-----------
A rider's next move (which platform, which direction) depends on *which
line* they're currently riding, not just which station they're standing
in. So the graph is built over ``(station, line)`` states rather than bare
stations:

- Consecutive stations on the same line get a same-line edge in each
  direction (weight = ride time).
- Any station served by more than one line gets a same-station "transfer"
  edge between every pair of those lines (weight = a fixed penalty).

routing_engine.py then runs Dijkstra over this state graph.

Data caveat: distances/durations below are flat placeholder averages, not
real DMRC timetable data -- see data/metro_data.json's "_note" field.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "metro_data.json"

# Placeholder averages used until real DMRC schedule/GIS data is wired in.
AVG_INTERSTATION_KM = 1.2
AVG_INTERSTATION_SECONDS = 135
TRANSFER_PENALTY_SECONDS = 180


@dataclass(frozen=True)
class Edge:
    to_station: str
    line: str
    distance_km: float
    duration_seconds: int
    is_transfer: bool = False


@dataclass
class MetroGraph:
    line_colors: dict[str, str] = field(default_factory=dict)
    # (station, line) -> outgoing edges
    adjacency: dict[tuple[str, str], list[Edge]] = field(default_factory=dict)
    # station -> set of lines serving it
    station_lines: dict[str, set[str]] = field(default_factory=dict)

    def lines_at(self, station: str) -> set[str]:
        return self.station_lines.get(station, set())

    def has_station(self, station: str) -> bool:
        return station in self.station_lines


def _add_edge(graph: MetroGraph, station: str, line: str, edge: Edge) -> None:
    graph.adjacency.setdefault((station, line), []).append(edge)


def build_graph(data_path: Path = DATA_FILE) -> MetroGraph:
    raw = json.loads(data_path.read_text(encoding="utf-8"))
    graph = MetroGraph()

    for line in raw["lines"]:
        name, color = line["name"], line["color"]
        graph.line_colors[name] = color

        for segment in line["segments"]:
            for station in segment:
                graph.station_lines.setdefault(station, set()).add(name)

            for a, b in zip(segment, segment[1:]):
                _add_edge(
                    graph, a, name,
                    Edge(b, name, AVG_INTERSTATION_KM, AVG_INTERSTATION_SECONDS),
                )
                _add_edge(
                    graph, b, name,
                    Edge(a, name, AVG_INTERSTATION_KM, AVG_INTERSTATION_SECONDS),
                )

    # Transfer edges: any station served by >1 line gets a same-station
    # hop between every ordered pair of lines it touches.
    for station, lines in graph.station_lines.items():
        for line_a in lines:
            for line_b in lines:
                if line_a == line_b:
                    continue
                _add_edge(
                    graph, station, line_a,
                    Edge(station, line_b, 0.0, TRANSFER_PENALTY_SECONDS, is_transfer=True),
                )

    return graph
