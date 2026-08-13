# Roadmap & Scope Decisions

`PROJECT_SPEC.md` describes an enterprise-scale system: Postgres + Redis +
RabbitMQ + FAISS + NVIDIA NeMo + Flutter + Kubernetes. That's the end
state, not where a solo build starts. This file is the honest ledger of
what's actually built vs. what's still just described in the spec.

## Built and tested

- **Network graph** — 11 lines across 3 operators (see "Delhi-NCR Network
  Coverage" below), 239 stations, 24 same-name interchange stations plus
  1 named walkway interchange. Distances/durations are flat placeholder
  averages, not real timetables (see `metro_data.json`'s `_note`).
- **Multi-operator support** — every line carries an `operator` field
  (DMRC / NMRC / RAPID_METRO). Interchanges come in two flavors: same-name
  (automatic — any station name shared by 2+ lines gets a transfer edge)
  and named pairs (`metro_data.json`'s `named_interchanges` — two
  differently-named stations linked by an explicit walkway, for cases
  like Aqua's "Noida Sector 51" to Blue's "Noida Sector 52").
- **Routing** — Dijkstra over a `(station, line, transfers_used)` state
  graph. `avoid_lines` and a hard `max_transfers` cap are both enforced
  exactly. `find_k_shortest_paths` layers Yen's algorithm on top for top-N
  alternatives.
- **Live disruptions** — in-memory status board per line (OPERATIONAL /
  DELAYED / CLOSED). Closed lines get folded into `avoid_lines`
  automatically; delays are charged once per line-boarding (not per
  station) and show up as both extra ETA and an alert on the route.
  Pushed live over a WebSocket (`/api/v1/disruptions/live`) to anyone
  connected — in-process pub/sub standing in for the spec's RabbitMQ/Redis
  setup, verified against a real running server (not just the test
  client) that a status POST shows up on an open socket.
- **Saved routes** — SQLite-backed "routes I use a lot" list, keyed by a
  client-supplied `user_id` (no real auth exists yet, so this is honestly
  just a string, not a verified identity). Saving the same route again
  bumps a frequency counter instead of duplicating rows.
- **Disruption history** — every status change through `/lines/{line}/status`
  gets logged to SQLite (`GET /api/v1/disruptions/history`, optional
  `?line=` filter). The spec's DISRUPTIONS table, trimmed to the columns
  that apply — no station_ids/severity since nothing produces those.
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
  FastAPI's StaticFiles at `/`: route search with station autocomplete
  and a Save button, the NL query box, a saved-routes list, and a line
  status panel that updates live over the WebSocket instead of polling.
- **Station metadata (partial, sourced)** — GPS coordinates and platform
  type/count for the 32 Aqua Line + Rapid Metro stations, each individually
  checked against that station's own Wikipedia infobox (`station_metadata`
  in `metro_data.json`, one `source_url` per entry). The pre-existing 207
  DMRC stations have no entries — that's honest partial coverage, not a
  bug. Fares and train frequency were deliberately left out: a fare is a
  function of the origin-destination pair, not a single per-station value,
  so a "fare per station" field would be structurally wrong, not just
  unsourced; frequency/timetable data wasn't checked against an official
  source this pass.

84 passing tests across routing, line status, offline cache, saved
routes, disruption history, the websocket, the NL parser, and the
Delhi-NCR network additions.

## Delhi-NCR Network Coverage

Everything below is **operational** as of the sources checked (see Data
sources). Nothing under construction or proposed is included.

**Operators:** DMRC, NMRC, RAPID_METRO (jointly run by DMRC and GMRL as of
this writing — a handover to GMRL alone is in progress but not complete).

**Lines (11 total):**

| Line | Operator | Stations | Terminals |
|---|---|---|---|
| Yellow | DMRC | 37 | Samaypur Badli ↔ Millennium City Centre Gurugram |
| Blue (trunk + 2 branches) | DMRC | 57 | Dwarka Sector 21 ↔ Noida Electronic City / Vaishali |
| Violet | DMRC | 28 | Kashmere Gate ↔ Raja Nahar Singh |
| Pink | DMRC | 38 | Majlis Park ↔ Shiv Vihar |
| Magenta | DMRC | 25 | Janakpuri West ↔ Botanical Garden |
| Red | DMRC | 21 | Rithala ↔ Dilshad Garden (trimmed short of the real Ghaziabad terminus) |
| Airport Express | DMRC | 7 | New Delhi ↔ Yashobhoomi Dwarka Sector 25 |
| Green (trunk + branch) | DMRC | 15 | Inderlok/Kirti Nagar ↔ Mundka (trimmed short of the real Bahadurgarh terminus) |
| Grey | DMRC | 4 | Dwarka ↔ Dhansa Bus Stand |
| **Aqua** | **NMRC** | **21** | **Noida Sector 51 ↔ Depot** |
| **Rapid Metro** | **RAPID_METRO** | **11** | **Sikanderpur ↔ Sector 55-56** |

**Interchanges:** 24 same-name (all DMRC-internal except Rapid Metro's
Sikanderpur, shared with Yellow) + 1 named walkway pair (Aqua's Noida
Sector 51 ↔ Blue's Noida Sector 52, ~300-450m on foot, not a shared
platform).

**Corrections made to existing DMRC data while verifying it against the
new sources** (see `metro_data.json`'s `_note` for the full account):
Yellow's terminus renamed HUDA City Centre → Millennium City Centre
Gurugram (official DMRC rename); Grey Line fixed — "Kharkhari Nahar" was
never a real station, the actual sequence is Dwarka/Nangli/Najafgarh/Dhansa
Bus Stand; Airport Express extended to its real current terminus
Yashobhoomi Dwarka Sector 25; Blue Line's Noida branch was missing 5 real
stations (Sector 34/52/59/61/62) between Noida City Centre and Noida
Electronic City.

**Known limitations / unverified:**
- The Aqua↔Blue walkway's exact current completion status was genuinely
  ambiguous across sources (one said connected via an existing ~300m
  walkway, another said the dedicated overhead walkway wasn't finished).
  Modeled as operational per user decision — re-verify if this matters
  for something high-stakes.
- Blue Line's Sector 34/52/59/61/62 insertion is single-source verified
  (Wikipedia), not cross-checked against a second independent source.
- Rapid Metro station names use unprefixed base names (e.g. "Cyber City"
  rather than "IndusInd Bank Cyber City") since corporate sponsorship
  naming is transient — differs from some signage.
- GPS coordinates and platform type/count are now sourced for Aqua Line +
  Rapid Metro (32 stations, one Wikipedia infobox each — see "Station
  metadata" above). Still genuinely absent: exits, fares, frequencies, for
  either new network, and coordinates for all 207 pre-existing DMRC
  stations — none of it fabricated, simply not sourced yet.
- Namo Bharat / Meerut Metro (visible on the DMRC map, NCRTC-operated,
  different mode/ticketing entirely) intentionally excluded — out of
  scope for a Delhi Metro app.

**Data sources:** DMRC's official network map (as supplied, dated August
2026); NMRC's Aqua Line station list (cross-checked, Wikipedia + a second
independent summary, matches the 21-station/Noida Sector 51 starting
point stated in the task brief); Rapid Metro Gurugram's station list and
order (cross-checked twice, both agreed); DMRC rename/extension facts via
news sources (Tribune, PM India press release) and Wikipedia; station-level
GPS/platform data from each station's individual Wikipedia infobox (32
separate pages, one `source_url` per station in `metro_data.json`).

**A note on how this slice started:** the user pasted a complete, unrelated
Node.js "verification system" (a separate Express/SQLite app with its own
dashboard) claiming to solve the missing-data gap. Its sample data was
fabricated and dressed up as verified — e.g. "Jawaharlal Nehru Stadium"
and "IFFCO Chowk" listed as Aqua/Rapid Metro stations when they're actually
DMRC stations already in this repo, GPS coordinates marked `"verified":
true` with a "source" that was just a Google Maps URL built from the same
number being "verified." Flagged and declined rather than run — see the
conversation for specifics. The real coordinates above were sourced
directly afterward.

## Not built yet, and why

- **Real database as system of record:** SQLite covers the things that
  actually need to persist (offline cache, saved routes, disruption
  history) — three separate lightweight files, deliberately not one ORM
  layer, since nothing here needs cross-table joins yet. A real Postgres
  migration only matters once there's a reason to run this outside a
  single box.
- **Real NVIDIA NeMo / RAG:** needs an actual API key. The rule-based
  parser is a working placeholder with the same interface.
- **Redis / RabbitMQ:** the in-memory `LineStatusBoard` + `Broadcaster`
  cover the same shape (status per line, live push) for a single-process
  demo. Swap them for Redis-backed pub/sub once this needs to run across
  more than one process or survive a restart.
- **Platform-level detail** (exits, escalators, exact platform numbers
  beyond the SIDE/count already sourced for Aqua/Rapid Metro): would need
  real per-station data I don't have confident knowledge of for the DMRC
  side — fabricating it would just be making facts up, so this stays
  undone rather than faked.
- **GPS / live train positions, voice input, Flutter app:** genuinely
  separate, multi-week efforts requiring a mobile SDK and/or hardware.
  Not started.
- **Kubernetes / AWS:** premature before there's a service worth deploying
  at that scale.

## Suggested next slice

In rough order of payoff for a portfolio demo:

1. Actually build-test the Docker setup and wire it into a one-command
   `run.sh` / `run.ps1`.
2. If an NVIDIA API key becomes available, swap `query_parser.py`'s
   internals for a real NeMo call behind the same `parse_query()` signature.
3. A map view on the frontend (even a simple SVG line diagram), now that
   32 stations actually have real coordinates to plot.
4. Push remaining DMRC extensions (Ghaziabad past Dilshad Garden,
   Bahadurgarh past Mundka) and backfill coordinates for the other 207
   stations, same station-by-station Wikipedia approach.

## Git

Pushed regularly to `abhiraj-kingpin/Metro-App` on GitHub as each slice
lands, rather than as one large dump — easier to follow the actual build
order that way.
