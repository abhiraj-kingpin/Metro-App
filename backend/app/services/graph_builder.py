# Builds the routing graph from metro_data.json. Nodes are (station, line)
# pairs, not bare stations, since you can't switch lines without walking
# across a platform. Interchanges = same-station edge with a time penalty.
#
# distance_km / duration_seconds are placeholder averages, not real DMRC
# numbers -- see the _note field in metro_data.json.

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "metro_data.json"

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
    adjacency: dict[tuple[str, str], list[Edge]] = field(default_factory=dict)  # (station, line) -> edges
    station_lines: dict[str, set[str]] = field(default_factory=dict)  # station -> lines serving it

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
                _add_edge(graph, a, name, Edge(b, name, AVG_INTERSTATION_KM, AVG_INTERSTATION_SECONDS))
                _add_edge(graph, b, name, Edge(a, name, AVG_INTERSTATION_KM, AVG_INTERSTATION_SECONDS))

    # any station touched by 2+ lines gets a transfer edge between every pair of them
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
