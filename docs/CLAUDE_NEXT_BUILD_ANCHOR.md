# CLAUDE CODE NEXT BUILD ANCHOR
# TravelCast AviatorGraf Prep — Session Context for Claude Code

**Last updated:** 2026-06-20
**Last completed phase:** Phase 14 Step 2 — commit `6696589`
**Next phase:** Phase B (Operator Packaging + Aviation Maturity) — requires Gary approval

---

## What This App Is

TravelCast AviatorGraf Prep is an internal broadcast-prep console for aviation, weather, airport, and route information. It is a local HTML/CSS/vanilla JavaScript app backed by Supabase.

- Frontend runs locally: `python -m http.server 8080`
- Frontend reads Supabase views only; no real-time API calls from the browser
- Backend: local Python pull scripts using `.env` (service-role key never in browser)
- 71 focus airports, 11 regions, equal refresh cadence

---

## Non-Negotiable Rules (Enforce Every Session)

- No React, Next.js, Vite, Tailwind, TypeScript, or build system
- No secrets in frontend code (no service-role key, no Baron/OpenWeather/FAA API keys)
- No `.env` committed
- No `js/config.js` committed (it is local-only with real Supabase credentials)
- No generated `data/exports/` files committed
- No invented aviation, weather, road, closure, alert, delay, route, or impact data
- Use official/provided/licensed data doctrine only
- Demo fallback must remain available at all times
- Every user-visible operational card must show a source label and freshness state

---

## Source Doctrine (Non-Negotiable)

| Lane | Truth Role | Required Label |
|------|-----------|----------------|
| FAA NAS / ATCSCC | Operational traffic-management truth | Current Operational Impact — FAA NAS / ATCSCC |
| AviationWeather.gov | Aviation weather truth | Aviation Weather Truth — AviationWeather.gov |
| NWS / api.weather.gov | Forecast weather-impact proxy ONLY | Forecast Weather Impact — NWS forecast proxy |
| NWS CAP / WEA | Public alert and warning truth | Public Alert Truth — NWS CAP / Alerts |
| FAA / BTS / OurAirports | Static reference | Static reference — FAA / OurAirports |
| Baron / OpenWeather / Synoptic | Enrichment / fallback ONLY | Commercial / Enrichment |

NWS forecast impact must NEVER be labeled as FAA operational delay data.

---

## Current Build State

### What is built and working
- 71-airport Supabase board (live mode verified 2026-06-09)
- FAA NAS Status pull (`pull_faa_nas_status.py`)
- AviationWeather METAR/TAF/hazards pull
- NWS forecast proxy pull
- ATCSCC Ops Plan + advisories pull
- RouteCast (6 starter routes, text-matching enrichment)
- Source Health (freshness/aging/stale/no_runs + mission-critical alerting)
- Batch broadcast export: `dashboard.json`, `airports.geojson`, `active_events.placefile`, `{IATA}_broadcast.json`, `manifest.json`
- `pull_all.py` with `--export` / `--export-limit N` / `--export-all` flags
- Graphics Queue
- Operator runbooks, troubleshooting, source-failure playbook, broadcast guardrails, command reference

### What is NOT built yet (Phase B–E)
- Static runway reference (separate from live FAA/NAS runway config)
- Windows .bat launch helpers
- TAF timeline parser / PIREP maturity
- NWS CAP/WEA public alert ontology
- RouteCast corridor geometry + ATCSCC playbook matching
- AviaImpact scoring engine
- RoadCast scoring engine
- wxSense broadcast graphics templates
- Production RLS / hosted worker

---

## Key File Locations

```
travelcast_aviatorgraf/
├── index.html                          — main app
├── js/
│   ├── config.js                       — LOCAL ONLY, never commit
│   └── modules/                        — frontend modules
├── scripts/
│   ├── pull/
│   │   ├── pull_all.py                 — master pull orchestrator
│   │   ├── pull_faa_nas_status.py
│   │   ├── pull_aviation_weather.py
│   │   ├── pull_nws_forecast.py
│   │   ├── pull_atcscc_ops_plan.py
│   │   └── pull_atcscc_advisories.py
│   ├── export/
│   │   └── export_broadcast_batch.py   — batch exporter (71 airports)
│   └── audit/
│       ├── audit_no_secrets.py
│       ├── audit_source_doctrine.py
│       └── audit_file_tree.py
├── data/
│   ├── raw/                            — raw API payloads (not committed)
│   ├── exports/                        — generated exports (not committed)
│   └── demo/                           — demo mode fallback data
├── sql/                                — SQL migrations and grants
├── docs/                               — planning and operational docs
└── audit/
    └── day_one_readiness_report.md     — authoritative audit log
```

---

## Phase A–E Register (Quick Reference)

| Phase | Description | Status |
|-------|-------------|--------|
| A | Anchor + Deduped Build Register (docs only) | CURRENT — 2026-06-20 |
| B | Operator Packaging + Aviation Maturity (runway ref, .bat helpers, TAF/PIREP) | PENDING GARY APPROVAL |
| C | NWS CAP/WEA + RouteCast Intelligence Expansion | FUTURE |
| D | AviaImpact + RoadCast Products | FUTURE |
| E | Hosted Production + wxSense Graphics Expansion | FUTURE |

Full details: `docs/NEXT_BUILD_REGISTER.md`

---

## Standard Audit Commands (Run After Every Phase)

```
python scripts/audit/audit_no_secrets.py
python scripts/audit/audit_source_doctrine.py
python scripts/audit/audit_file_tree.py
python scripts/pull/pull_all.py --dry-run
python -m py_compile scripts/pull/*.py
```

---

## Commit Rules

- Do NOT commit `.env`
- Do NOT commit `js/config.js`
- Do NOT commit `data/exports/` files
- Do NOT commit `data/raw/` files
- After every phase: update `TASKS.md`, `ACCEPTANCE_CRITERIA.md`, `audit/day_one_readiness_report.md`
- Suggest commit message; wait for Gary confirmation before committing

---

## Product Distinctions (Keep These Separate)

| Product | Scope | Status |
|---------|-------|--------|
| RouteCast | Airline origin→destination route pair monitoring | BUILT |
| RoadCast | Highway corridor weather-impact scoring (0/5–5/5) | Phase D |
| AviaImpact | Airport aviation flight-impact scoring (0/5–5/5) | Phase D |

These are three distinct products. Do not merge their logic, tables, or labels.

---

## Planning Document Index

| Document | Purpose |
|----------|---------|
| `docs/NEXT_BUILD_REGISTER.md` | Full A–E phase register |
| `docs/PHASE_A_DEDUPLICATION_REGISTER.md` | Classification of all 9 source files |
| `docs/TRAVELCAST_PRODUCT_HIERARCHY.md` | Brand/product architecture, distinctions |
| `docs/CLAUDE_NEXT_BUILD_ANCHOR.md` | This file — Claude Code session anchor |
| `docs/CHATGPT_PROJECT_ANCHOR.md` | ChatGPT project context anchor |
| `docs/DAY_ONE_OPERATOR_RUNBOOK.md` | Local operator procedures |
| `docs/COMMAND_REFERENCE.md` | Pull commands, audit commands, export commands |
| `docs/BROADCAST_USE_GUARDRAILS.md` | On-air content rules |
| `audit/day_one_readiness_report.md` | Phase-by-phase audit log (authoritative) |
