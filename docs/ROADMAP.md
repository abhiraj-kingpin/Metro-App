# Roadmap & Scope Decisions

`PROJECT_SPEC.md` describes an enterprise-scale system: Postgres + Redis +
RabbitMQ + FAISS + NVIDIA NeMo + Flutter + Kubernetes. That's the end
state, not where a solo build starts. This file is the honest ledger of
what's actually built vs. what's still just described in the spec.

## Built and tested

- **Network graph** — 8 lines (Yellow, Blue, Violet, Pink, Magenta, Red,
  Airport Express, Green), ~160 real DMRC stations, genuine interchange
  points. Distances/durations are flat placeholder averages, not real
  timetables (see `metro_data.json`'s `_note`).
- **Routing** — Dijkstra over a `(station, line, transfers_used)` state
  graph. `avoid_lines` and a hard `max_transfers` cap are both enforced
  exactly. `find_k_shortest_paths` layers Yen's algorithm on top for top-N
  alternatives.
- **Live disruptions** — in-memory status board per line (OPERATIONAL /
  DELAYED / CLOSED). Closed lines get folded into `avoid_lines`
  automatically; delays are charged once per line-boarding (not per
  station) and show up as both extra ETA and an alert on the route.
- **Offline mode** — graph exports to SQLite and reloads from it with zero
  network calls. Tested that live-graph and reloaded-from-disk routing
  produce identical results.
- **NL query parsing** — regex + fuzzy string matching for "from X to Y"
  and Hinglish phrasing, with typo tolerance. Explicitly a stand-in for
  the spec's NVIDIA NeMo RAG pipeline, not a reimplementation of it — no
  NVIDIA API key available in this environment. Same call signature
  though, so it's a contained swap later.
- **Docker** — a Dockerfile and single-service compose file exist and
  should work, but haven't been build-tested (no Docker in the sandbox
  this was written in). Verify locally before trusting it.
- **Frontend** — a plain HTML/CSS/JS page (no build step) served off
  FastAPI's StaticFiles at `/`: route search with station autocomplete,
  the NL query box, and a live line-status panel with an update form.

41 passing tests across routing, line status, offline cache, and the NL
parser.

## Not built yet, and why

- **Database (Postgres/SQLite as system of record):** nothing needs to
  persist yet — the graph is static and status is in-memory. Worth adding
  once user accounts or saved routes show up.
- **Real NVIDIA NeMo / RAG:** needs an actual API key. The rule-based
  parser is a working placeholder with the same interface.
- **Redis / RabbitMQ / WebSocket push:** the in-memory `LineStatusBoard`
  covers the same shape (status per line, closed/delayed) for a
  single-process demo. Swap it for Redis-backed pub/sub once this needs to
  run across more than one process or survive a restart.
- **Platform-level detail** (platform number, exits, escalators): schema's
  in the original spec, no data source for it yet.
- **GPS / live train positions, voice input, Flutter app:** genuinely
  separate, multi-week efforts. Not started.
- **Kubernetes / AWS:** premature before there's a service worth deploying
  at that scale.

## Suggested next slice

In rough order of payoff for a portfolio demo:

1. Keep pushing the network toward the full 12-line/256-station DMRC map
   (Grey, Orange/Aqua/Rapid Metro still missing) — mechanical, low-risk.
2. Actually build-test the Docker setup and wire it into a one-command
   `run.sh` / `run.ps1`.
3. If an NVIDIA API key becomes available, swap `query_parser.py`'s
   internals for a real NeMo call behind the same `parse_query()` signature.
4. Redis-backed `LineStatusBoard` once there's a second process (a
   background poller, say) that needs to see the same state.
5. A map view on the frontend (even a simple SVG line diagram) instead of
   just text-and-color-chip route cards.

## Git

Pushed regularly to `abhiraj-kingpin/Metro-App` on GitHub as each slice
lands, rather than as one large dump — easier to follow the actual build
order that way.
