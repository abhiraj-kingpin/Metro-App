# Dumps the live graph into a portable SQLite file and can rebuild an
# equivalent graph purely from that file -- no metro_data.json, no
# network. Once you've got the .db, routing_engine doesn't know or care
# where the graph came from. That's the actual point: this is what a
# mobile client would download once and route against forever after.

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.services.graph_builder import Edge, MetroGraph

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "metro_offline.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS lines (
    name TEXT PRIMARY KEY,
    color TEXT NOT NULL,
    operator TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stations (
    name TEXT PRIMARY KEY,
    lines TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS edges (
    from_station TEXT NOT NULL,
    from_line TEXT NOT NULL,
    to_station TEXT NOT NULL,
    to_line TEXT NOT NULL,
    distance_km REAL NOT NULL,
    duration_seconds INTEGER NOT NULL,
    is_transfer INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_station, from_line);
"""


def export_to_sqlite(graph: MetroGraph, db_path: Path = DEFAULT_DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_SCHEMA)
        conn.execute("DELETE FROM lines")
        conn.execute("DELETE FROM stations")
        conn.execute("DELETE FROM edges")

        conn.executemany(
            "INSERT INTO lines VALUES (?, ?, ?)",
            [(name, color, graph.line_operators.get(name, "DMRC")) for name, color in graph.line_colors.items()],
        )
        conn.executemany(
            "INSERT INTO stations VALUES (?, ?)",
            [(name, ",".join(sorted(lines))) for name, lines in graph.station_lines.items()],
        )

        rows = [
            (from_station, from_line, e.to_station, e.line, e.distance_km, e.duration_seconds, int(e.is_transfer))
            for (from_station, from_line), edges in graph.adjacency.items()
            for e in edges
        ]
        conn.executemany("INSERT INTO edges VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
        conn.commit()
    finally:
        conn.close()


def load_graph_from_sqlite(db_path: Path = DEFAULT_DB_PATH) -> MetroGraph:
    if not db_path.exists():
        raise FileNotFoundError(f"no offline cache at {db_path} -- call export_to_sqlite() first")

    conn = sqlite3.connect(db_path)
    try:
        graph = MetroGraph()
        for name, color, operator in conn.execute("SELECT name, color, operator FROM lines"):
            graph.line_colors[name] = color
            graph.line_operators[name] = operator
        for name, lines_csv in conn.execute("SELECT name, lines FROM stations"):
            graph.station_lines[name] = set(lines_csv.split(","))
        for from_station, from_line, to_station, to_line, dist, dur, is_transfer in conn.execute(
            "SELECT from_station, from_line, to_station, to_line, distance_km, duration_seconds, is_transfer FROM edges"
        ):
            graph.adjacency.setdefault((from_station, from_line), []).append(
                Edge(to_station, to_line, dist, dur, bool(is_transfer))
            )
        return graph
    finally:
        conn.close()
