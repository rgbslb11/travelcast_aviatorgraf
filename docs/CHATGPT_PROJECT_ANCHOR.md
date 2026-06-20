# CHATGPT PROJECT ANCHOR
# TravelCast AviatorGraf Prep — Context for ChatGPT Project Sessions

**Last updated:** 2026-06-20

---

## What This Project Is

TravelCast AviatorGraf Prep is an internal broadcast-preparation console for aviation weather, airport status, FAA operational data, and highway weather impact. It is used by wxSense / TravelCast producers and meteorologists to prepare graphics packages before broadcast.

**Not a public-facing app.** Internal prep tool only.

---

## Technology Stack

- **Frontend:** Plain HTML + CSS + vanilla JavaScript. No React, Next.js, Vite, TypeScript, or build tools.
- **Database:** Supabase (PostgreSQL). Frontend uses anon/public key only via Supabase client.
- **Backend:** Local Python pull scripts that use a service-role key (from `.env`, never in browser).
- **Runs locally:** `python -m http.server 8080` — no Node.js required.
- **Demo mode:** Works offline with static demo data when Supabase is not connected.

---

## Brand and Product Hierarchy

```
wxSense (network umbrella)
├── TravelCast             — travel, aviation, road, and ops product
│   └── AviatorGraf        — the graphics prep console we are building
├── StormGlass Live        — severe-weather override product
└── WxSense Lab            — experimentation (nothing airs without review)
```

---

## What Is Already Built (as of 2026-06-20)

- 71-airport Supabase board (live, verified 2026-06-09)
- FAA NAS Status live pull
- AviationWeather.gov METAR / TAF / SIGMET / AIRMET / CWA live pull
- NWS forecast proxy pull (labeled as proxy, not FAA operational truth)
- ATCSCC Operations Plan + Advisories live pull
- RouteCast (6 airline route pairs, origin→destination status monitoring)
- Source Health monitoring (freshness/aging/stale/no_runs states)
- Batch broadcast export: airport dashboard JSON, GeoJSON, GRLevelX-style placefile, individual airport broadcast packages
- Graphics Queue
- Operator runbooks and broadcast guardrails

---

## What Is Planned Next (Phases A–E)

### Phase A — Anchor + Deduplication Register (CURRENT — docs only)
Consolidate 9 uploaded planning files. No code changes. Create 5 anchor docs.

### Phase B — Operator Packaging + Aviation Maturity
1. Static runway reference table (OurAirports / FAA AIS data for 71 airports)
2. Windows .bat launch helpers (`start_app.bat`, `refresh_data_live.bat`, etc.)
3. TAF timeline parser + PIREP maturity

### Phase C — NWS CAP/WEA + RouteCast Intelligence Expansion
1. NWS CAP/WEA public alert ontology (tornado warnings, severe thunderstorm warnings, alert polygons, WEA text extraction)
2. RouteCast corridor geometry + ATCSCC playbook matching (upgrade RouteCast from status-only to corridor-based intelligence)

### Phase D — AviaImpact + RoadCast Products
1. AviaImpact Score: 0/5–5/5 airport aviation flight-impact score
2. RoadCast: 0/5–5/5 highway corridor weather-impact score (50 corridors)

### Phase E — Hosted Production + wxSense Graphics Expansion
1. wxSense broadcast graphics HTML templates (airport card, route card, hazard card, ops board)
2. Production RLS hardening + public read models
3. Hosted Python worker + scheduler

---

## Three Distinct Route/Road/Impact Products

| Product | Scope | Status |
|---------|-------|--------|
| **RouteCast** | Airline origin→destination route pair monitoring | BUILT |
| **RoadCast** | Highway corridor weather-impact scoring (0/5–5/5) | Planned Phase D |
| **AviaImpact** | Airport aviation flight-impact scoring (0/5–5/5) | Planned Phase D |

**These are separate products.** Do not merge their logic, tables, labels, or scoring formulas.

---

## Source Doctrine (Hard Rules — Never Violate)

| Source | Role | How to Label |
|--------|------|-------------|
| FAA NAS / ATCSCC | Operational traffic-management truth | "Current Operational Impact — FAA NAS / ATCSCC" |
| AviationWeather.gov | Aviation weather truth (METAR, TAF, SIGMET, AIRMET, CWA) | "Aviation Weather Truth — AviationWeather.gov" |
| NWS / api.weather.gov | Forecast weather-impact proxy only | "Forecast Weather Impact — NWS forecast proxy" |
| NWS CAP / WEA | Public alert and warning truth | "Public Alert Truth — NWS CAP / Alerts" |
| FAA / OurAirports / BTS | Static reference data | "Static reference — FAA / OurAirports" |
| Baron / OpenWeather / Synoptic | Enrichment / archive / development only | "Commercial / Enrichment" |

**NWS forecast proxy is NEVER an official FAA delay forecast.** Always label correctly.

---

## Hard Safety Rules

These are non-negotiable product honesty rules:

- RouteCast is NOT an official FAA route forecast
- AviaImpact must NOT claim ground stop, exact delay minutes, or runway closure unless sourced from FAA/ATCSCC/official data
- RoadCast must NOT claim road closure unless an official DOT/state source confirms it
- WEA text must be NWS CAP-provided only — TravelCast must never generate, rewrite, or simulate WEA messages
- NWS alerts must not be labeled as FAA delay data
- Empty state (no data) is always better than invented data

---

## AviaImpact Score Formula (Planned Phase D)

```
AviaImpact =
  Terminal Weather Score      × 0.30
+ Convective / Hazard Score   × 0.20
+ FAA / NAS Constraint Score  × 0.20
+ Airport Exposure Score      × 0.10
+ Time-of-Day / Bank Score    × 0.10
+ Route / Airspace Exposure   × 0.10

Scale: 0/5 (No Impact) → 5/5 (Severe Aviation Impact)
Hard override: FAA ground stop = force 5/5
Hard override: GDP active = minimum 4/5
```

---

## RoadCast Score Formula (Planned Phase D)

```
RoadCast =
  Forecasted Weather Score   × 0.40
+ Heavy Truck Route Score    × 0.10
+ Day-of-Week Score          × 0.10
+ Holiday / Vacation Score   × 0.15
+ Average Traffic Score      × 0.15
+ Route Danger Score         × 0.10

Scale: 0/5 (No Impact) → 5/5 (Extreme Danger)
Hard override: Official closure = force 5/5
Hard override: Chain law / traction law = minimum 4/5
```

---

## Current Phase Status

| Phase | Description | Status |
|-------|-------------|--------|
| Phases 1–14 Step 2 | Core build (airports, pull engine, exports, RouteCast, etc.) | COMPLETE |
| Phase A | Anchor + Dedup Register (docs only) | IN PROGRESS — 2026-06-20 |
| Phase B | Operator Packaging + Aviation Maturity | PENDING GARY APPROVAL |
| Phase C | NWS CAP/WEA + RouteCast Expansion | FUTURE |
| Phase D | AviaImpact + RoadCast | FUTURE |
| Phase E | Hosted Production + Graphics | FUTURE |

---

## Key Constraints for All Future Sessions

- Do not commit `.env`, `js/config.js`, or generated `data/exports/` files
- Do not call real source APIs from browser JavaScript
- Do not put service-role keys in frontend
- After every code phase: run `audit_no_secrets.py`, `audit_source_doctrine.py`, `audit_file_tree.py`
- Update `TASKS.md`, `ACCEPTANCE_CRITERIA.md`, `audit/day_one_readiness_report.md` after each phase
- Do not commit until Gary reviews
