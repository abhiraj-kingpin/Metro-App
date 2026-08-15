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
  and a Save button, the NL query box, a saved-routes list, a line
  status panel that updates live over the WebSocket instead of polling,
  and a Leaflet/OpenStreetMap station map (all 239 sourced coordinates,
  colored by line, interchanges marked distinctly). Leaflet loads via CDN
  with real SRI hashes (verified by hash-comparing the downloaded files,
  not copied blind) — deliberately not React/Vite, to stay consistent
  with the rest of this frontend's no-build-step approach.
- **Station metadata: coordinates (complete, sourced)** — GPS coordinates
  for all 239 stations (`station_metadata` in `metro_data.json`, one
  `source_url` per entry). The 32 Aqua/Rapid Metro entries were checked by
  hand, one Wikipedia page at a time. 205 DMRC entries were fetched by
  `scripts/fetch_station_coordinates.py` via Wikipedia's structured
  coordinates API (not a regex scrape), accepting a match only if the
  returned page title contains every word of the station name. The last 2
  (Pitampura, Mayur Vihar Pocket I) needed Wikidata + a directly-verified
  OpenStreetMap node each, since neither had a usable Wikipedia infobox
  coordinate.
- **Station metadata: platform type/count (near-complete, sourced)** —
  213 of 239 stations have `platform_type`/`platform_count`; the 24
  same-name interchanges (23 + Sikanderpur) instead carry a
  `platforms_by_line` dict, since their platform config genuinely differs
  per line (e.g. Rajiv Chowk: Island platform for Yellow, Side platform
  for Blue — a single flat value would be wrong, not just imprecise).
  `scripts/fetch_platform_data.py` parses each station's raw infobox
  wikitext for the `platform`/`platforms` field (no structured API exists
  for this, unlike coordinates). Only 5 stations are left genuinely
  unresolved: Jama Masjid, Mayur Vihar Pocket I, Yashobhoomi Dwarka Sector
  25 (single-line, no source states a usable type+count), and Dwarka /
  Dwarka Sector 21 (interchanges — one infobox states a bare total of "5"
  platforms with no type or per-line split, the other's field is empty).
  A real bug was caught and fixed mid-pass: the first version of the
  parser only recognized "Platform-1" (hyphenated); Pink Line's circular-
  route articles use "Platform 1" inside a `{{font color|...}}` template
  instead, which the regex didn't match, wrongly routing ~35 clean
  stations to manual review before the fix.
- Fares and train frequency remain deliberately absent everywhere: a fare
  is a function of the origin-destination pair, not a single per-station
  value, so a "fare per station" field would be structurally wrong, not
  just unsourced; frequency/timetable data hasn't been checked against an
  official source.

100 passing tests across routing, line status, offline cache, saved
routes, disruption history, the websocket, the NL parser, and the
Delhi-NCR network additions.

## Topology findings that need a decision (found while sourcing platform data, not acted on)

Digging through real DMRC infobox wikitext for platform data surfaced
several things that suggest this repo's topology has gaps or an outright
error — none of these were touched, since topology changes were out of
scope for that pass, but they're real enough to flag rather than sit on:

- **A Magenta Line extension appears at four stations not in this
  repo's topology**: Haiderpur Badli Mor, Pitampura (Madhuban Chowk),
  Majlis Park, and New Delhi all have infobox platforms explicitly tagged
  for Magenta (sometimes marked "TBC" — to be confirmed / not yet
  operational) alongside the lines this repo does model there. Consistent
  enough across 4 independent stations that it's very likely a real
  Magenta Phase IV extension, not a fluke.
- **Punjabi Bagh West's infobox explicitly tags 2 of its 4 platforms as
  Green Line** — this repo's Green Line has a separate, unconnected
  "Punjabi Bagh" (no "West") station. Worth checking whether these are
  actually the same complex.
- **Likely real error, not just a gap**: research while sourcing platform
  data for "Terminal 1 IGI Airport" turned up that Airport Express does
  not serve Terminal 1 in reality — it serves Terminals 2/3 via a
  different station. This repo currently models "Terminal 1 IGI Airport"
  as an Airport Express + Magenta interchange. That may be wrong, not
  just incomplete. Airport Express's platform data was deliberately left
  unpopulated at this station rather than attached to a possibly-fictitious
  interchange.

None of these were corrected — flagging for a dedicated topology-focused
pass, with the same source-verification rigor as everything else here.

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
Electronic City; Noida Sector 50 renamed Rainbow (2020, dedicated to the
transgender community); Rohini East renamed Rohini. The last two turned up
incidentally while cross-checking coordinates, not from a dedicated pass —
worth keeping in mind that more renames like this probably exist
undiscovered in the remaining data.

**Two more renames found, deliberately NOT applied to the topology:**
while resolving the Pitampura and Mayur Vihar Pocket I coordinate gaps
(a task explicitly scoped to coordinates only, no topology changes),
turned up that both stations have since been officially renamed —
Pitampura → Madhuban Chowk (November 2025) and Mayur Vihar Pocket I →
Shree Ram Mandir Mayur Vihar (February 2026, per India TV News). Station
identity was confirmed (adjacency match for Pitampura/Madhuban Chowk;
name-history match for Mayur Vihar Pocket I) and the coordinate was
attached under the existing station name rather than the new one. If the
topology should reflect the current names, that's a separate, deliberate
edit — flagging it here rather than making the call unilaterally.

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
- Coordinates now cover all 239 stations (see "Station metadata" above).
  Still genuinely absent everywhere: exits, fares, frequencies, and
  platform type/count for the 207 DMRC stations (only Aqua/Rapid Metro
  have that) — none of it fabricated, simply not sourced yet.
- Namo Bharat / Meerut Metro (visible on the DMRC map, NCRTC-operated,
  different mode/ticketing entirely) intentionally excluded — out of
  scope for a Delhi Metro app.

**Data sources:** DMRC's official network map (as supplied, dated August
2026); NMRC's Aqua Line station list (cross-checked, Wikipedia + a second
independent summary, matches the 21-station/Noida Sector 51 starting
point stated in the task brief); Rapid Metro Gurugram's station list and
order (cross-checked twice, both agreed); DMRC rename/extension facts via
news sources (Tribune, PM India press release) and Wikipedia; station-level
GPS data from each station's individual Wikipedia infobox — 32 checked by
hand, 207 fetched via Wikipedia's structured API by
`scripts/fetch_station_coordinates.py`, every entry carries its own
`source_url` in `metro_data.json`.

**A note on how this slice started (twice):** the user pasted two
successive third-party bundles claiming to solve the missing-data gap.
The first was a complete Node.js "verification system" (its own
Express/SQLite app with a dashboard) whose sample data was fabricated and
dressed up as verified — e.g. "Jawaharlal Nehru Stadium" and "IFFCO Chowk"
listed as Aqua/Rapid Metro stations when they're actually DMRC stations
already in this repo, GPS coordinates marked `"verified": true` with a
"source" that was just a Google Maps URL built from the same number being
"verified." The second, after being asked for "the part that's doable by
code," was a more polished Node scraper whose hardcoded DMRC station list
invented a "Purple Line" that doesn't exist, included "Dum Dum" (a real
station — in Kolkata, not Delhi), and reused the first bundle's fabricated
Aqua Line list relabeled as DMRC Blue Line. Both declined, both with
specific cited evidence rather than a general "looks off." The real
coordinates above were sourced directly afterward, in Python (matching the
existing stack) using this repo's own already-verified station list as
input and Wikipedia's structured API instead of regex scraping.

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
- **Platform type/count** is now sourced for 213/239 stations (see above)
  — what's still genuinely absent is **exits and escalators**, and the
  final 5 unresolved stations' platform data. No source found for exits
  during this pass; fabricating them would just be making facts up.
- **GPS / live train positions, voice input, Flutter app:** genuinely
  separate, multi-week efforts requiring a mobile SDK and/or hardware.
  Not started.
- **Kubernetes / AWS:** premature before there's a service worth deploying
  at that scale.

## Suggested next slice

In rough order of payoff for a portfolio demo:

1. Investigate the topology findings above (possible Magenta Phase IV
   extension at 4 stations, Green/Punjabi Bagh West connection, the
   likely Airport Express/Terminal 1 IGI Airport error) — these came up
   as a side effect of sourcing platform data, not from a dedicated check,
   so a real pass would probably find more.
2. Actually build-test the Docker setup and wire it into a one-command
   `run.sh` / `run.ps1`.
3. If an NVIDIA API key becomes available, swap `query_parser.py`'s
   internals for a real NeMo call behind the same `parse_query()` signature.
4. Push remaining DMRC extensions (Ghaziabad past Dilshad Garden,
   Bahadurgarh past Mundka); decide whether to apply the Madhuban Chowk /
   Shree Ram Mandir Mayur Vihar renames to the topology (deliberately left
   as a flagged, separate decision); do a systematic pass over all 239
   stations specifically looking for more quiet renames, since all 4
   found so far (Rainbow, Rohini, Madhuban Chowk, Shree Ram Mandir Mayur
   Vihar) turned up by accident, not from a dedicated check.
5. Source exits/gates and resolve the 5 remaining platform-data gaps.

## Git

Pushed regularly to `abhiraj-kingpin/Metro-App` on GitHub as each slice
lands, rather than as one large dump — easier to follow the actual build
order that way.
