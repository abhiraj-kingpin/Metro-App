# Roadmap & Scope Decisions

The full spec (`PROJECT_SPEC.md`) describes an enterprise-scale system:
Postgres + Redis + RabbitMQ + FAISS + NVIDIA NeMo + Flutter + Kubernetes.
That's the *end state*, not a sane place to start. This file tracks what's
actually built, what's stubbed, and why — so scope creep vs. real progress
stays visible.

## What exists right now (Phase 0: lean MVP)

- `backend/` — a real, runnable FastAPI service.
- `app/data/metro_data.json` — real DMRC network topology (5 lines: Yellow,
  Blue, Violet, Pink, Magenta; ~140 unique stations with genuine interchange
  points). **Not real:** per-segment distance/duration, which are flat
  placeholder averages (see the file's `_note` field and
  `graph_builder.py`'s constants) — not scraped DMRC timetables.
- `app/services/graph_builder.py` + `routing_engine.py` — an actual
  Dijkstra variant over a `(station, line, transfers_used)` state graph,
  supporting `avoid_lines` and a hard `max_transfers` cap. This is real
  algorithm work, not a stub.
- `POST /api/v1/routes/find`, `GET /api/v1/stations`, `GET /api/v1/lines` —
  working endpoints, covered by pytest (`tests/test_routing_engine.py`,
  `tests/test_api.py`).

## What's explicitly stubbed / not started

- **Database:** no Postgres/SQLite yet — topology is loaded straight from
  JSON into memory at process start. Fine for a static graph; revisit once
  real-time line status needs persistence.
- **Real-time (Redis, RabbitMQ, WebSocket disruptions):** not started.
  Phase 4 in the original spec.
- **RAG / NVIDIA NeMo / Hindi NLU:** not started. Needs an actual NVIDIA
  API key or local model before it can be more than pseudo-code — flag
  this when picked up.
- **Platform-level detail** (platform number, exits, escalators): schema
  exists in the spec, no data or endpoint yet.
- **Offline SQLite sync, GPS/live tracking, voice input, Flutter app:**
  not started.
- **Docker / Kubernetes / AWS deployment:** not started — premature before
  there's a service worth deploying at that scale.

## Suggested next slice

Pick one, in roughly this order of payoff-per-effort for a portfolio demo:

1. Expand `metro_data.json` toward the full 12-line/256-station network
   (mechanical, low risk, makes the algorithm demo more impressive).
2. K-shortest-routes (return top 3, not just 1) — natural extension of the
   existing Dijkstra code.
3. A thin `avoid_lines`/`max_transfers`-aware CLI or minimal web page to
   demo routing without needing `/docs` Swagger UI.
4. Real-time line status as an in-memory (then Redis-backed) overlay that
   the routing engine consults — this is the natural bridge into Phase 4
   without needing the full WebSocket/RabbitMQ stack yet.

## GitHub

This directory is a fresh git repo (`git init` was run as part of scaffolding
Phase 0) with no remote configured. Push to GitHub when ready — the spec's
"50+ meaningful commits" target is easiest to hit by committing each roadmap
slice above separately rather than in one big dump.
