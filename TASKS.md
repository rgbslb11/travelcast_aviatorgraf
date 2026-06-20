# TASKS.md — TravelCast Build Tasks

## Phase 1 — Project foundation

- [x] Create file tree.
- [x] Create `CLAUDE.md`.
- [x] Create `README.md`.
- [x] Create `.gitignore`.
- [x] Create `.env.example`.
- [x] Create `js/config.js`.

## Phase 2 — Demo mode

- [x] Create demo airport data.
- [x] Create DEN detail data.
- [x] Create sample overlay data.
- [x] Create source system sample data.

## Phase 3 — UI shell

- [x] Create `index.html`.
- [x] Create CSS files.
- [x] Add tab navigation.
- [x] Add mode banner.

## Phase 4 — Core JavaScript

- [x] Create Supabase client.
- [x] Create app state.
- [x] Create utilities.
- [x] Implement demo fallback.

## Phase 5 — Airport board

- [x] Render airport table.
- [x] Add impact badges.
- [x] Add freshness badges.
- [x] Add row actions.

## Phase 6 — Airport detail

- [x] Render selected airport.
- [x] Generate graphics copy.
- [x] Add export actions.

## Phase 7 — Exporters

- [x] Dashboard JSON.
- [x] Broadcast package JSON.
- [x] GeoJSON.
- [x] Placefile.

## Phase 8 — Graphics queue

- [x] localStorage persistence.
- [x] Add/remove/mark ready/mark used.
- [x] Export queue items.

## Phase 9 — Live Supabase layer

- [x] Create airport master CSV template.
- [x] Create airport loader scaffold.
- [x] Create pull script scaffolds.
- [x] Create live SQL views.
- [x] Create source health view.

## Phase 10 — Audit

- [x] Run no-secret audit script scaffold.
- [x] Run JSON/GeoJSON audit script scaffold.
- [x] Run file tree audit script scaffold.
- [x] Run doctrine audit script scaffold.
- [x] Write readiness report.

## Phase 11 — 71-Airport Product (completed)

- [x] 71 focus airports loaded to Supabase (11 regions).
- [x] Airport Status Board: region filter, search, operational/forecast impact filters.
- [x] Airport Detail: 5 SQL views deployed.
- [x] METAR/TAF parser fixed (variable wind direction).
- [x] pull_all.py --dry-run verified at 71-airport scale.

## Phase 12 — Operational Intelligence Expansion (completed)

- [x] sql/06 migration: 4 tables, 5 views, 6 starter routes.
- [x] Aviation Hazards: SIGMET/AIRMET/CWA ingestion from AviationWeather.gov.
- [x] ATCSCC Operations Plan: auto-discovery + manual --url flag.
- [x] RouteCast: configured-route enrichment from local caches.
- [x] All 3 frontend panels wired to live Supabase views.
- [x] Phase 9 audit passed: Operational Intelligence Audit Passed.

## Phase 13 — Hardening and Runbook (completed)

- [x] docs/DAY_ONE_OPERATOR_RUNBOOK.md
- [x] docs/TROUBLESHOOTING.md
- [x] docs/SOURCE_FAILURE_PLAYBOOK.md
- [x] docs/BROADCAST_USE_GUARDRAILS.md
- [x] docs/COMMAND_REFERENCE.md
- [x] Source Health: mission-critical stale/no_runs alert banner.
- [x] README.md updated to reflect current status.
- [x] All audit checks pass at Phase 10 level.

## Phase 14 — Broadcast Graphics Integration (Step 1 complete)

- [x] scripts/export/export_broadcast_batch.py — batch export script reading v_airport_status_dashboard
- [x] sql/07_grant_export_views.sql — GRANT SELECT on all dashboard views to service_role
- [x] .gitignore: data/exports/ excluded
- [x] audit_file_tree.py: export script added to required list
- [x] Operator: applied sql/07_grant_export_views.sql in Supabase SQL Editor
- [x] Live dry-run: python scripts/export/export_broadcast_batch.py --dry-run --limit 5 — PASSED (71 airports, 5-airport dry-run, LAS active event identified)
- [x] Live run: python scripts/export/export_broadcast_batch.py --limit 5 — PASSED (dashboard.json, airports.geojson, active_events.placefile, LAS_broadcast.json, manifest.json written; source_mode=live; doctrine and NWS proxy notice confirmed in manifest)
- [x] Phase 14 Step 2 — Integrate batch export into pull_all.py as optional post-pull step
  - --export flag triggers export_broadcast_batch.py after pulls complete
  - --export-limit N passes --limit N to export script
  - --export-all passes --all to export script
  - --dry-run --export triggers export in dry-run mode (no files written)
  - export failure does not affect pull_all exit code
  - export_ok reported in pull_all_complete summary event
