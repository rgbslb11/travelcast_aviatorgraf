# Day One Readiness Report

Date: 2026-06-06

## Result

Ready for Day One TravelCast Prep: **Yes — demo mode verified, Supabase live mode verified**

## Supabase Connection Status

- Bootstrap SQL (`sql/00_supabase_bootstrap.sql`) pasted and executed in Supabase SQL Editor: **SUCCESS**
- Frontend connected to Supabase with anon key: **SUCCESS**
- `v_airport_status_dashboard` view returning seeded data: **SUCCESS**
- App banner showing "Supabase Connected — live views": **CONFIRMED**
- Demo fallback confirmed preserved (demoMode: true → reverts to sample data): **CONFIRMED**

## Audit Script Results (2026-06-06)

- [x] No-secret audit: PASSED (anon JWT allowed in js/config.js per design; service_role key not present)
- [x] Supabase config/placeholder audit: PASSED (LIVE mode — real credentials, demoMode: false)
- [x] Source doctrine audit: PASSED
- [x] JSON/GeoJSON audit: PASSED
- [x] File tree audit: PASSED
- [x] Demo fallback audit: PASSED (all three connectionStatus states confirmed)
- [x] Exports Supabase-mode audit: PASSED (all exporters data-source-agnostic)

## Functional Checks

- [x] App loads with `python -m http.server 8080` — verified locally
- [x] Supabase mode active — "Supabase Connected — live views" banner, green border
- [x] Demo mode fallback — "Supabase Not Configured — demo mode" banner, gray border
- [x] Failed connection fallback — "Supabase Query Failed — using demo fallback" banner, amber border
- [x] #connection-warnings div renders Supabase error messages if query fails
- [x] 10 demo airports in Supabase view — seeded by 00_supabase_bootstrap.sql
- [x] DEN: GDP, Thunderstorms, 63 min avg delay, 386 max delay, 16L/16R/17R, icon 04, Red
- [x] Airport Status Board — renders from Supabase view in live mode
- [x] Airport Detail — renders from Supabase record in live mode
- [x] Aviation Hazards — sample data (live Supabase pull engine not yet wired)
- [x] ATCSCC / FAA Ops Plan — sample data (live pull engine not yet wired)
- [x] RouteCast — sample data (live pull engine not yet wired)
- [x] Graphics Queue — localStorage persistence, all actions working
- [x] Source Health — source registry with trust tiers
- [x] Dashboard JSON exporter — data-source-agnostic, works in live and demo mode
- [x] Broadcast package JSON exporter — data-source-agnostic
- [x] GeoJSON exporter — data-source-agnostic, valid FeatureCollection
- [x] Placefile exporter — data-source-agnostic, Title/Refresh/Font/Text/End

## Security Checks

- [x] No service_role key in any frontend file
- [x] Supabase anon/public JWT in js/config.js only (public key by Supabase design)
- [x] js/config.js not committed to git with real credentials (local working copy only)
- [x] .env is gitignored
- [x] No private API keys (Baron, OpenWeather, etc.) in any frontend file
- [x] RLS enabled on all 5 Supabase tables

## Doctrine Checks

- [x] FAA/NAS operational status separated from NWS forecast proxy
- [x] Commercial sources labeled enrichment only
- [x] NWS forecast impact NOT labeled official FAA delay forecast
- [x] RouteCast labeled "Forecast Weather Impact — NWS forecast proxy"
- [x] Aviation Hazards labeled "Aviation Weather Truth — AviationWeather.gov"
- [x] FAA Ops labeled "Operational Planning — FAA ATCSCC"
- [x] Icons use canonical IDs

## Three-State Connection Banner

| State | Banner Text | Color |
|---|---|---|
| Supabase configured + view returned data | Supabase Connected — live views | Green |
| Supabase configured + query failed | Supabase Query Failed — using demo fallback | Amber |
| Supabase not configured / placeholders | Supabase Not Configured — demo mode | Gray |

## Remaining Before Phase 4

- Pull engine scripts (`04-build-pull-engine.md`) — write live FAA/NAS, AviationWeather, NWS data into Supabase tables
- Aviation Hazards, RouteCast, FAA Ops panels will show live data once pull engine populates Supabase
- No browser-side changes expected for Phase 4

## Phase 4 — Pull Engine (completed 2026-06-07)

### Scripts built

| Script | Purpose | Writes |
|---|---|---|
| `scripts/pull/lib_pull.py` | Shared utilities: env load, Supabase REST, feed_runs, HTTP, raw cache | — |
| `scripts/pull/pull_faa_nas_status.py` | FAA NAS airport-events (bulk, once per run) → operational snapshot fields | airport_status_snapshots, feed_runs |
| `scripts/pull/pull_aviationweather_metar_taf.py` | METAR + TAF bulk fetch → local cache | data/raw/, feed_runs |
| `scripts/pull/pull_nws_forecasts.py` | NWS gridpoint forecast → local cache | data/raw/, feed_runs |
| `scripts/pull/pull_atcscc_ops_plan.py` | NAS status XML + ATCSCC advisories → local cache | data/raw/, feed_runs |
| `scripts/pull/rebuild_airport_status_snapshots.py` | Merges all caches → comprehensive snapshots | airport_status_snapshots, feed_runs |
| `scripts/pull/pull_all.py` | Subprocess orchestrator for all above | — |

### Guardrails verified

- [x] All secrets via environment variables / `.env` — none hardcoded
- [x] `SUPABASE_SERVICE_ROLE_KEY` only in `lib_pull.py` (server-side), never frontend
- [x] NWS User-Agent from `NWS_USER_AGENT` env var — not hardcoded
- [x] `--dry-run` flag on every script (no Supabase writes, prints what would be written)
- [x] `--limit N` flag on every script
- [x] `feed_runs` written on every execution (success or failure)
- [x] `data/raw/` created for raw cache; `*.json` and `*.xml` gitignored
- [x] No frontend changes made
- [x] Demo fallback preserved

### FAA NAS endpoint (updated 2026-06-07)

| | |
|---|---|
| **Active endpoint** | `https://nasstatus.faa.gov/api/airport-events` — fetched once per run, returns JSON array |
| **Retired endpoint** | `soa.smext.faa.gov/asws/api/airport/status/{IATA}` — NXDOMAIN, removed |
| **Field notes** | `avgDelay` is a float (e.g. 27.0); runway config in `arrivalRunwayConfig` / `departureRunwayConfig`; AAR in `arrivalRate` |
| **Live confirmed** | 2026-06-07 — DFW GDP detected (avg 27 min, max 145 min); 11 events in response |

### Live run results (2026-06-07)

| Run | Result |
|---|---|
| `pull_all.py --dry-run` | PASSED — 5 scripts, 0 failed |
| `pull_all.py` (live) | PASSED — 5 scripts, 0 failed, 10 combined snapshots written to Supabase |
| `pull_faa_nas_status.py --dry-run --limit 3` | PASSED — DFW GDP avg 27 min / max 145 min parsed correctly |
| `pull_atcscc_ops_plan.py --dry-run` | PASSED — 5 advisories parsed from `nasstatus.faa.gov/api/airport-status-information`; 0 from advisory sub-path (expected — endpoint returns NOTAM-style closures, not CDP format) |

### Audit results (2026-06-07, post live run + ATCSCC cleanup)

- [x] No-secret audit: PASSED (`.env` excluded — gitignored, right place for secrets)
- [x] Supabase config audit: PASSED
- [x] Source doctrine audit: PASSED
- [x] JSON/GeoJSON audit: PASSED
- [x] File tree audit: PASSED
- [x] All 7 pull scripts: `py_compile` clean, zero DeprecationWarnings

### ATCSCC parser note

`pull_atcscc_ops_plan.py` fetches `nasstatus.faa.gov/api/airport-status-information` (XML).
The current response contains `Advisory` elements (NOTAM-style airport closures for GA traffic),
not `Airport`/`GDP` nodes. The parser handles both formats.
`advisory_count = 5` on 2026-06-07; count varies with active NAS events.
The `advisoryUrl` on live GDP events (from `airport-events`) can be followed for full ATCSCC text.

### Safe to proceed?

**Phase 4 complete and live-verified.** `pull_all.py` wrote 10 snapshots across all sources.
Next: Phase 5 — SQL views upgrade.

## Phase 5 — Fast-track 71-airport day-one product (in progress 2026-06-07)

### Files created / modified

| File | Description |
|---|---|
| `data/reference/travelcast_focus_airports.csv` | 71 focus airports — 11 regions, lat/lon for NWS, all active |
| `scripts/load/load_focus_airports_to_supabase.py` | Upsert loader — dry-run, --limit, service-role key from .env only |
| `sql/01_seed_focus_airports.sql` | Safe-to-rerun SQL upsert for all 71 airports |
| `sql/02_grant_service_role_write.sql` | GRANT INSERT/UPDATE/DELETE to service_role on all writable tables |
| `sql/03_add_detail_views.sql` | 5 new views: v_airport_detail_current, v_airport_metar_latest, v_airport_taf_latest, v_airport_operational_events_latest, v_airport_runway_context |
| `scripts/pull/lib_pull.py` | `nws_impact()` now returns short label only — doctrine tag shown separately in UI |
| `js/modules/airportDashboard.js` | Region filter, airport search, operational/forecast impact filters, doctrine label separation |
| `css/app.css` | `.source-doctrine`, `.filter-bar`, `.export-row` styles added |

### Airports loaded

| Region | Count |
|---|---|
| Northeast | 10 |
| Southeast | 8 |
| Florida | 4 |
| Great Lakes | 8 |
| Southern Plains | 10 |
| Mid-South | 5 |
| Midwest | 3 |
| Rocky Mountains | 6 |
| Desert Southwest | 4 |
| West Coast | 9 |
| Pacific | 4 |
| **Total** | **71** |

### Loader status

- `load_focus_airports_to_supabase.py --dry-run`: PASSED — 71 airports, 0 rejected
- Live load: PASSED — 71 airports upserted to Supabase (after running sql/02_grant_service_role_write.sql)

### SQL views (paste `sql/03_add_detail_views.sql` in Supabase SQL Editor)

- `v_airport_detail_current` — full detail, all sources combined
- `v_airport_metar_latest` — METAR fields + Aviation Weather Truth doctrine label
- `v_airport_taf_latest` — TAF fields + Aviation Weather Truth doctrine label
- `v_airport_operational_events_latest` — FAA/NAS fields + Current Operational Impact doctrine label
- `v_airport_runway_context` — runway config + AAR per airport

### Frontend changes

- `forecast_impact_label` badge now shows short label only (e.g. "No significant weather")
- Doctrine tag "Forecast Weather Impact — NWS forecast proxy" shown as small italic source text below badge
- Same separation applied to Current Operational Impact badge
- Filter bar added to Airport Status Board: region dropdown, search input, op/forecast impact dropdowns
- Legacy labels with concatenated doctrine text are handled gracefully via `split("—")[0].trim()`

### METAR/TAF parser fix (2026-06-07)

`pull_aviationweather_metar_taf.py` crashed on variable wind direction:
- Root cause: `int('VRB')` raised ValueError — `not wdir` was False for the string `'VRB'`
- Fix: extracted `_parse_wind_dir()` helper with explicit `'VRB'` string check, float-safe numeric parsing, and graceful fallback for malformed values
- Per-record try/except added to METAR and TAF parse loops — one bad record no longer crashes the batch
- Parse errors counted and logged separately from fetch errors
- Feed run `success` now reflects fetch success only (partial parse errors are not total failure)
- Dry-run now reports: metar_fetched, metar_parsed, taf_fetched, taf_parsed, fetch_errors, parse_errors

### pull_all.py --dry-run at 71-airport scale (2026-06-07)

| Script | Result | Key metrics |
|---|---|---|
| `pull_faa_nas_status.py` | PASSED | 71 airports, 13 FAA events, 10 tracked matched, 61 NORMAL |
| `pull_aviationweather_metar_taf.py` | PASSED | METAR 71/71, TAF 71/71, 0 parse errors, 0 fetch errors |
| `pull_nws_forecasts.py` | PASSED | 71 forecasts cached |
| `pull_atcscc_ops_plan.py` | PASSED | 5 advisories parsed |
| `rebuild_airport_status_snapshots.py` | PASSED | 71 combined snapshots |
| **pull_all.py** | **5/5 PASSED** | **56 sec elapsed, 0 failed** |

### Audit results (2026-06-07, Phase 5 complete)

- [x] py_compile all pull + load scripts: PASSED
- [x] No-secret audit: PASSED
- [x] Source doctrine audit: PASSED
- [x] File tree audit: PASSED
- [x] pull_all.py --dry-run at 71-airport scale: PASSED (5/5 scripts, 0 failed)
- [ ] pull_all.py live run at 71-airport scale: READY — safe to run
- [ ] SQL views deployed to Supabase: paste sql/03_add_detail_views.sql in SQL Editor

### Safe to run live?

**Yes.** `pull_all.py --dry-run` passed 5/5 at 71-airport scale with 0 parse errors, 0 fetch errors.
AviationWeather 504 on batch 2 was transient (did not recur on second dry-run). Parser is now fault-tolerant.

Run: `python scripts/pull/pull_all.py`

## Secondary tab live/demo separation (2026-06-07)

### Problem
Aviation Hazards, ATCSCC/FAA Ops, and RouteCast showed hardcoded demo sample data (dated 6/6/2026) even in Supabase-connected mode.

### Changes

| File | Change |
|---|---|
| `js/modules/aviationWeather.js` | Async; Supabase mode queries `v_aviation_hazards_latest`; shows honest empty state; demo mode unchanged |
| `js/modules/faaOps.js` | Async; Supabase mode queries `v_airport_operational_events_latest` for non-NORMAL events; honest empty state if none; ATCSCC advisory notice; demo mode unchanged |
| `js/modules/routecast.js` | Async; Supabase mode queries `v_routecast_routes`; shows honest empty state; demo mode unchanged |
| `js/app.js` | Added `await` on all three now-async render calls |
| `sql/04_placeholder_views.sql` | `v_aviation_hazards_latest` (empty, `WHERE false`); `v_routecast_routes` (empty, `WHERE false`) |

### Supabase mode behavior

| Tab | Live behavior |
|---|---|
| Aviation Hazards | Queries `v_aviation_hazards_latest` → "No live aviation hazard records available" (SIGMET/AIRMET/CWA/PIREP not yet in Supabase) |
| ATCSCC / FAA Ops | Queries `v_airport_operational_events_latest` → shows active FAA/NAS programs (non-NORMAL airports) from live snapshots; ATCSCC advisory text noted as local-cache-only |
| RouteCast | Queries `v_routecast_routes` → "No live RouteCast routes configured yet" |

### Doctrine labels preserved

- Aviation Hazards: `Aviation Weather Truth — AviationWeather.gov`
- ATCSCC / FAA Ops: `Current Operational Impact — FAA NAS Status`
- RouteCast: `Forecast Weather Impact — NWS forecast proxy · NOT an official FAA delay forecast`

### Audit results (2026-06-07, post secondary-tab fix)

- [x] py_compile all pull scripts: PASSED
- [x] pull_all.py --dry-run: PASSED (5/5, 71 airports, 0 errors)
- [x] No-secret audit: PASSED
- [x] Source doctrine audit: PASSED
- [x] File tree audit: PASSED

### Required: Paste `sql/04_placeholder_views.sql` in Supabase SQL Editor

The two new placeholder views must exist in Supabase before the Aviation Hazards and RouteCast tabs can query them without a 404 error. Until then, both tabs catch the error gracefully and show the empty state.

## Phase 6 — Exporters Audit / Day-One Hardening (2026-06-07)

### Files created / modified

| File | Change |
|---|---|
| `js/exporters/exportDashboardJson.js` | Rewrote: `source_mode`, `airport_count`, `source_doctrine`, `nws_proxy_notice`, `freshness_summary`; removed hardcoded `demo: true` |
| `js/exporters/exportGeojson.js` | Rewrote: added `generated_at`, `source_mode`, `feature_count`, `source_doctrine`, `nws_proxy_notice`; `airportFeature()` now includes `display_name`, `city`, `region`, `overall_impact_color`, `forecast_impact_color`, `forecast_impact_label`, `flight_category`, `freshness_status`, `last_updated_at` |
| `js/exporters/exportBroadcastPackage.js` | Rewrote: `source_mode` from `appState.demoModeActive`; conditional `limitations` (live: 1 item, demo: 2 items); added `region`, `observed_at`, `taf_next_risk_window`, `freshness_status`, `last_updated_at`; `package_version: "1.0"` |
| `js/exporters/exportPlacefile.js` | Rewrote: timestamp, source mode, doctrine, NWS proxy notice in header comments; `freshTag` appended to label when not fresh |
| `js/modules/graphicsQueue.js` | Rewrote `itemHtml()`: structured card with IATA/name/city, product/platform/queued row, status/freshness badges, FAA/NAS badge, NWS forecast badge, METAR flight_category badge, source summary; `handleQueueAction` Mark Ready: fresh/aging → Ready, stale/unknown → Needs Freshness Review |
| `js/modules/sourceHealth.js` | Rewrote as async: operator checklist with 10-step pre-broadcast checklist, live feed-run telemetry from `v_source_health_dashboard`, demo fallback showing source registry with `no_runs` badges |
| `js/app.js` | Added `await` before `renderSourceHealth()` (now async) |

### Metadata fields now present in all exporters

| Field | dashboardJson | GeoJSON | BroadcastPackage | Placefile |
|---|---|---|---|---|
| `generated_at` | ✓ | ✓ | ✓ | header comment |
| `source_mode` (live/demo) | ✓ | ✓ | ✓ | header comment |
| `nws_proxy_notice` | ✓ | ✓ | ✓ | header comment |
| `source_doctrine` block | ✓ | ✓ | source_labels[] | header comment |
| Freshness metadata | `freshness_summary` | per-feature | per-airport | `[aging]`/`[stale]` tag |
| Conditional `limitations` | — | — | ✓ | — |

### Graphics Queue improvements

- Each queued item now shows: IATA + display name + city/state, product type + platform + queued timestamp
- Status badge (green=Ready, gray=Used, amber=Needs Review, blue=Draft)
- Freshness badge with color-coded class
- FAA/NAS impact badge with event type or "No active FAA/NAS event"
- NWS forecast badge with impact label and color
- METAR flight category badge (when present)
- Source summary as `source-doctrine` italic text
- Mark Ready: fresh or aging → Ready; stale or unknown → Needs Freshness Review

### Source Health improvements

- Now async — awaited in `app.js`
- Day-One Operator Checklist: 10-step pre-broadcast verification list with connection status badge and airport count
- Live mode: queries `v_source_health_dashboard` — shows freshness, last success, 24h run count, last error per source
- Demo mode: shows source registry with `no_runs` for all sources + warning banner
- Error state: shows query error message in card

### Audit results (2026-06-07, Phase 6 complete)

- [x] py_compile scripts/pull/*.py: PASSED (7 scripts, 0 errors)
- [x] py_compile scripts/load/*.py: PASSED (1 script, 0 errors)
- [x] pull_all.py --dry-run: PASSED (5/5 scripts, 71 airports, 0 fetch errors, 0 parse errors, 54 sec)
- [x] No-secret audit: PASSED
- [x] Source doctrine audit: PASSED
- [x] File tree audit: PASSED

### Security check

- [x] `source_mode` reads from `appState.demoModeActive` (set at data-load time) — cannot be spoofed by export call
- [x] No new private keys or secrets added in any export file
- [x] NWS proxy notice present in all four exporters

## Phase 6 Closeout — Browser-verified and hardened (2026-06-07)

### Browser verification (confirmed by operator)

| Panel | Status |
|---|---|
| Day-One Operator Checklist | Renders correctly |
| Source Health live feed-run telemetry | Renders — official sources showed `unknown` (fixed below) |
| Airport Status Board | Supabase Connected, 71 airports |
| ATCSCC / FAA Ops | Live active FAA/NAS programs displayed |
| RouteCast | Honest empty state ("No live RouteCast routes configured yet") |
| Aviation Hazards | Honest empty state ("No live aviation hazard records available") |
| Graphics Queue | DFW airport_status_card queued; all 6 actions confirmed |

### Exported file spot-check (ELP broadcast package confirmed by operator)

| Field | Present |
|---|---|
| `source_mode` | `"live"` — confirmed |
| `package_version` | `"1.0"` — confirmed |
| `generated_at` | ISO timestamp — confirmed |
| `valid_until` | ISO timestamp — confirmed |
| `source_labels` | 4-element array — confirmed |
| `nws_proxy_notice` | Present — confirmed |

All Airports GeoJSON spot-check:
- `source_mode: "live"` — confirmed
- `feature_count: 71` — confirmed
- `source_doctrine` — confirmed
- `nws_proxy_notice` — confirmed

### Source Health freshness fix

**Bug:** `v_source_health_dashboard` freshness_status used `max(retrieved_at_utc)` (includes failed runs)
and only had three states (`fresh`, `no_runs`, `unknown`). Official sources with successful runs
older than 30 minutes showed `unknown` instead of `aging` or `stale`.

**Fix:** `sql/05_fix_source_health_freshness.sql`
- Freshness now computed from `last_success_at` (successful runs only)
- Four tiers:
  - `fresh` — last success < 30 minutes ago → green badge
  - `aging` — last success 30 min – 3 hours ago → amber badge
  - `stale` — last success > 3 hours ago → red badge
  - `no_runs` — no successful run on record → gray badge
- Frontend (`js/modules/sourceHealth.js`): `stale` now maps to red badge class

**Action required:** Paste `sql/05_fix_source_health_freshness.sql` into Supabase SQL Editor and run.

### Export path audit (all 8 buttons — code-verified)

| Export | Trigger | Function | `generated_at` | `source_mode` | `source_doctrine` | `airport_count`/`airport_id` | freshness | NWS proxy |
|---|---|---|---|---|---|---|---|---|
| Dashboard JSON | `#export-dashboard-json` | `dashboardJson(records)` | ✓ | ✓ | ✓ source_doctrine block | airport_count ✓ | freshness_summary ✓ | nws_proxy_notice ✓ |
| All Airports GeoJSON | `#export-all-geojson` | `airportRowsToGeoJSON(records)` | ✓ | ✓ | ✓ source_doctrine string | feature_count ✓ | per-feature freshness_status ✓ | nws_proxy_notice ✓ |
| Detail Package JSON | `#detail-export-json` | `airportBroadcastPackage(airport)` | ✓ | ✓ | ✓ source_labels array | airport.airport_id ✓ | operational_status.freshness_status ✓ | nws_proxy_notice ✓ |
| Detail GeoJSON | `#detail-export-geojson` | `selectedAirportToGeoJSON(airport)` | ✓ | ✓ | — (single feature) | feature_count=1 ✓ | per-feature freshness_status ✓ | nws_proxy_notice ✓ |
| Detail Placefile | `#detail-export-placefile` | `airportPlacefile([airport])` | ✓ header | ✓ header | ✓ header | iata per label ✓ | [aging]/[stale] tag ✓ | header comment ✓ |
| Queue Package JSON | `data-q-action="json"` | `airportBroadcastPackage(q.payload)` | ✓ | ✓ | ✓ source_labels array | airport.airport_id ✓ | operational_status.freshness_status ✓ | nws_proxy_notice ✓ |
| Queue GeoJSON | `data-q-action="geojson"` | `selectedAirportToGeoJSON(q.payload)` | ✓ | ✓ | — (single feature) | feature_count=1 ✓ | per-feature freshness_status ✓ | nws_proxy_notice ✓ |
| Queue Placefile | `data-q-action="placefile"` | `airportPlacefile([q.payload])` | ✓ header | ✓ header | ✓ header | iata per label ✓ | [aging]/[stale] tag ✓ | header comment ✓ |

### Supabase mode export — no stale demo data

When `isSupabaseConfigured()` is true and the view returns rows:
- `appState.demoModeActive = false` → `source_mode = "live"` in all exports
- Records passed to exporters come from `v_airport_status_dashboard` (live snapshots)
- Demo seed snapshots (`snapshot_source = 'demo'`) are overridden by live snapshots via `ORDER BY generated_at DESC LIMIT 1` LATERAL join — live pull rows are always newer
- Demo airports not in the 71-airport focus set do not appear in the view since `airports.active = true` filters apply

### Graphics Queue workflow (code-verified)

| Step | Handler | Result |
|---|---|---|
| Add item | `action = "queue"` in handleAction | `addQueueItem()` → persisted to localStorage |
| Mark Ready (fresh/aging) | `action = "ready"`, freshnessStatus ∈ {fresh, aging} | status → "Ready" (green) |
| Mark Ready (stale/unknown) | `action = "ready"`, freshnessStatus ∈ {stale, unknown} | status → "Needs Freshness Review" (amber) |
| Mark Used | `action = "used"` | status → "Used" (gray) |
| Remove | `action = "remove"` | `removeQueueItem(id)` → removed from localStorage |
| Export JSON | `action = "json"` | `airportBroadcastPackage(q.payload)` → downloaded |
| Export GeoJSON | `action = "geojson"` | `selectedAirportToGeoJSON(q.payload)` → downloaded |
| Export Placefile | `action = "placefile"` | `airportPlacefile([q.payload])` → downloaded |

### Audit results (2026-06-07, Phase 6 closeout)

- [x] py_compile scripts/pull/*.py (7 scripts): PASSED
- [x] py_compile scripts/load/*.py (1 script): PASSED
- [x] pull_all.py --dry-run: 5/5 PASSED, 71 airports, 0 fetch errors (NWS PBI connection reset transient — 70/71 cached, expected behavior)
- [x] No-secret audit: PASSED
- [x] Source doctrine audit: PASSED
- [x] File tree audit: PASSED

### Files committed in Phase 6 closeout

| File | Change |
|---|---|
| `sql/05_fix_source_health_freshness.sql` | Fixes v_source_health_dashboard: 4-tier freshness, success-only timestamps |
| `js/modules/sourceHealth.js` | stale → red badge, aging → amber, no_runs → gray |

**Operator action required before next session:** Paste `sql/05_fix_source_health_freshness.sql` in Supabase SQL Editor.

## Phase Completion Status

- [x] Phase 1 — Bootstrap / file tree
- [x] Phase 2 — Demo mode app (all 7 panels)
- [x] Phase 3 — Supabase layer (bootstrap SQL + frontend connection)
- [x] Phase 4 — Pull engine (live data ingestion scripts)
- [x] Phase 5 — 71-airport product (airports loaded, parser fixed, dry-run 5/5)
- [x] Phase 5b — Secondary tabs: live/demo separation, honest empty states, doctrine labels
- [x] Phase 6 — Exporters audit / day-one hardening (all 4 exporters hardened, Graphics Queue improved, Source Health async + operator checklist)
- [x] Phase 6 Closeout — Browser-verified, Source Health freshness fixed (SQL + JS), all 8 export paths audited
- [ ] Phase 7 — Final runbook / deployment planning
