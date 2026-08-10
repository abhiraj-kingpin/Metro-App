# Delhi Metro Navigator Pro

Real-time Delhi Metro navigation — placement portfolio project.

This repo currently contains a **lean MVP backend**: a FastAPI service with
a genuine Dijkstra-based routing engine over real Delhi Metro network
topology. The full target architecture (RAG, live tracking, offline sync,
mobile app, Kubernetes) is documented but not yet built — see
[`docs/ROADMAP.md`](docs/ROADMAP.md) for what's real vs. planned, and
[`docs/PROJECT_SPEC.md`](docs/PROJECT_SPEC.md) for the full original spec.

## What works today

- `POST /api/v1/routes/find` — shortest-route finding between any two of
  ~140 real Delhi Metro stations across 5 lines (Yellow, Blue, Violet,
  Pink, Magenta), with `avoid_lines` and `max_transfers` preferences.
- `GET /api/v1/stations`, `GET /api/v1/stations/{name}`, `GET /api/v1/lines`
- Interactive API docs at `/docs` once running.

## Quickstart

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# run the server
uvicorn main:app --reload
# -> http://127.0.0.1:8000/docs

# run the tests
pytest -v
```

Example request:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/routes/find `
  -ContentType "application/json" `
  -Body '{"from_station":"Samaypur Badli","to_station":"Dwarka Sector 21"}'
```

## Project structure

```
backend/
  main.py                    # FastAPI entrypoint
  app/
    api/routes.py            # /api/v1 endpoints
    services/
      graph_builder.py       # builds the (station, line) routing graph
      routing_engine.py      # Dijkstra with avoid_lines / max_transfers
    schemas/route.py         # request/response models
    data/metro_data.json     # real DMRC topology, placeholder timings
  tests/                     # pytest unit + API tests
docs/
  PROJECT_SPEC.md            # full original enterprise-scale spec
  ROADMAP.md                 # what's built vs. stubbed, suggested next steps
```

## Data accuracy note

Station names, line order, and interchange points reflect the real DMRC
network. **Distances and travel times are flat placeholder averages**, not
sourced from DMRC timetables — see `metro_data.json`'s `_note` field before
treating any ETA as real.
