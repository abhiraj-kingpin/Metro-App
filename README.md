# Delhi Metro Navigator Pro

Route planner for the Delhi Metro network — built as a portfolio project, originally scoped as a much bigger enterprise-style system (see `docs/PROJECT_SPEC.md`). This repo is the part of that spec I've actually built and can stand behind, not a scaffold pretending to be more than it is. `docs/ROADMAP.md` keeps an honest list of what's real vs. still on paper.

## What's actually working

- **Routing engine** — Dijkstra over a real Delhi-NCR network graph (11 lines across DMRC, NMRC, and Rapid Metro Gurugram — 239 stations, genuine interchanges including a cross-operator walkway transfer), returns the top N alternative routes (Yen's algorithm), respects `avoid_lines` and a hard `max_transfers` cap. See `docs/ROADMAP.md`'s "Delhi-NCR Network Coverage" for exactly what's operational vs. excluded.
- **Live disruptions, actually live** — an in-memory board tracks per-line status, pushed out over a WebSocket (`/api/v1/disruptions/live`) to anyone connected. Close a line and routing reroutes around it automatically; delay a line and it shows up as extra ETA plus an alert on affected routes. Verified against a real running server, not just the test client, that a status POST shows up on an open socket in real time.
- **Saved routes** — SQLite-backed, per-`user_id` (a client-supplied string — there's no real auth system, so don't mistake this for verified identity). Saving the same route again bumps a frequency counter instead of piling up duplicate rows.
- **Disruption history** — every status change is logged to SQLite and readable back via `GET /api/v1/disruptions/history` (optionally filtered by line). The spec's DISRUPTIONS table, trimmed to what actually applies.
- **Offline mode** — the graph can be exported to a portable SQLite file and reloaded from it with zero network calls. Verified: same query against the live graph and the reloaded-from-disk graph gives identical results.
- **Natural language input** — a regex/fuzzy-match parser handles "from X to Y" and Hinglish ("X se Y jana hai") phrasing, with typo tolerance. It is explicitly *not* the NVIDIA RAG pipeline described in the spec — I don't have a NeMo API key — but it's a working stand-in with the same interface, so swapping in a real LLM later is a one-file change.
- **Frontend** — a plain HTML/CSS/JS page at `/` (no build step, no framework): route search with station autocomplete and a Save button, the NL query box, a saved-routes list, a recent-disruptions feed, and a line-status panel that updates live over the WebSocket instead of polling.

84 tests, all passing, covering the routing math (including the constraint edge cases), cross-operator routing, the websocket, saved routes, disruption history, station metadata, and the HTTP layer.

## What's not built

The actual NVIDIA RAG integration, the Flutter app, GPS/live train tracking, Kubernetes/AWS deployment, a real Postgres migration. All of that needs either external accounts I don't have (NVIDIA, AWS), hardware/SDKs not in this environment (mobile), or just isn't justified yet at this scale (Postgres, K8s). Details and priority order in `docs/ROADMAP.md`.

## Running it

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

uvicorn main:app --reload
# -> http://127.0.0.1:8000/       (the UI)
# -> http://127.0.0.1:8000/docs   (raw API)

pytest -v
```

Or with Docker (untested in the sandbox this was built in — Docker wasn't installed there, so verify it locally):

```powershell
docker compose -f docker/docker-compose.yml up --build
```

### Try it

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/routes/find `
  -ContentType "application/json" `
  -Body '{"from_station":"Samaypur Badli","to_station":"Dwarka Sector 21"}'

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/query/natural `
  -ContentType "application/json" `
  -Body '{"query":"Rajiv Chowk se Central Secretariat jana hai, Yellow Line se mat nikalna"}'
```

## Endpoints

| Method | Path | What it does |
|---|---|---|
| POST | `/api/v1/routes/find` | top-N routes between two stations, with preferences |
| POST | `/api/v1/query/natural` | plain-text query → parsed intent → routes |
| POST | `/api/v1/routes/save`, GET `/api/v1/routes/saved` | save / list a user's frequent routes |
| GET | `/api/v1/stations`, `/api/v1/stations/{name}` | station lookup / search |
| GET | `/api/v1/lines`, `/api/v1/lines/status` | line list, live status board |
| POST | `/api/v1/lines/{line}/status` | push a status update (stand-in for a real DMRC feed) |
| GET | `/api/v1/disruptions/history` | recent status changes, optional `?line=` filter |
| WS | `/api/v1/disruptions/live` | live push of status updates |
| POST | `/api/v1/offline/export` | snapshot the graph to SQLite |

## Layout

```
backend/
  main.py
  static/                     # the frontend: index.html, app.js, style.css
  app/
    api/routes.py             # every endpoint above lives here
    services/
      graph_builder.py        # JSON -> in-memory graph
      routing_engine.py       # Dijkstra + Yen's k-shortest
      line_status.py          # in-memory disruption board
      broadcast.py            # websocket pub/sub for live status push
      saved_routes.py         # sqlite-backed "routes I use a lot"
      disruption_history.py   # sqlite-backed status-change log
      offline_cache.py        # graph <-> SQLite
      query_parser.py         # regex/fuzzy NL parsing
    schemas/                  # pydantic request/response models
    data/metro_data.json      # the network itself
  tests/
docs/
  PROJECT_SPEC.md             # the original full spec, kept as-is for reference
  ROADMAP.md                  # what's real, what's not, what's next
```

## On the data

Station names, line order, and interchange points reflect the real DMRC network as best I know it. **Travel times and distances are flat placeholder averages**, not DMRC timetable data — check `metro_data.json`'s `_note` field before trusting an ETA for anything real.
