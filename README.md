# TravelCast AviatorGraf Prep

A local-first, static-hostable TravelCast / wxSense graphics-preparation console and Claude Code automation pack.

## What this is

**TravelCast AviatorGraf Prep** is an internal mini-application for preparing aviation, weather, airport, route, and FAA/NAS information for broadcast-ready graphics.

It starts in demo mode and can later connect to Supabase views.

## What this is not

- Not a public consumer weather app.
- Not an official FAA/NWS product.
- Not a flight-specific dispatch or clearance system.
- Not a place to store secrets in frontend code.

## How to run locally

```bash
cd TravelCast-aviatorgraf-prep
python -m http.server 8080
```

Open:

```text
http://localhost:8080
```

## Hosted-domain posture

This app uses relative paths and static files so it can later be hosted on a domain. For production hosting, configure Supabase RLS, use public anon key only in the browser, and publish generated exports through Supabase Storage, a backend route, or CDN.

## Demo mode

Demo mode is enabled by default in:

```text
js/config.js
```

Demo data lives in:

```text
js/sampleData/
data/
```

## Supabase configuration

Edit:

```text
js/config.js
```

Replace:

```js
supabaseUrl: "REPLACE_WITH_SUPABASE_URL",
supabaseAnonKey: "REPLACE_WITH_SUPABASE_ANON_KEY",
demoMode: true
```

with your project values and set `demoMode: false`.

Only the Supabase public anon key belongs in frontend code. The service-role key must never be used in browser code.

## Where information lives

- Project doctrine: `CLAUDE.md`, `SOURCE_DOCTRINE.md`, `README.md`, `docs/`
- Frontend public config: `js/config.js`
- Secret placeholders: `.env.example`
- Real secrets: never committed; backend/server only
- Demo data: `js/sampleData/` and `data/`
- Supabase schema assumptions: `sql/`
- Exported sample files: `data/exports/`
- Audit results: `audit/`
- Runtime graphics queue: browser `localStorage`
- Production generated exports: Supabase Storage/backend endpoint/CDN later

## Claude Code automation pack

The project includes:

```text
CLAUDE.md
PRODUCT_SPEC.md
DATA_CONTRACT.md
SOURCE_DOCTRINE.md
ACCEPTANCE_CRITERIA.md
TASKS.md
ROADMAP.md
.claude/commands/
prompts/
templates/
scripts/audit/
scripts/setup/
```

Recommended Claude Code sequence:

```text
Read CLAUDE.md, PRODUCT_SPEC.md, DATA_CONTRACT.md, SOURCE_DOCTRINE.md, ACCEPTANCE_CRITERIA.md, and TASKS.md.
Execute .claude/commands/01-bootstrap.md.
Execute .claude/commands/02-build-demo-app.md.
Execute .claude/commands/07-run-audit.md and fix blockers.
Execute .claude/commands/03-build-supabase-layer.md.
Execute .claude/commands/04-build-pull-engine.md.
Execute .claude/commands/05-build-views.md.
Execute .claude/commands/06-build-exporters.md.
Execute .claude/commands/07-run-audit.md.
```

## Source doctrine

- FAA NAS Status / ATCSCC = operational traffic-management truth.
- AviationWeather.gov = aviation weather truth.
- NWS/api.weather.gov = public forecast, alerts, and forecast-impact proxy.
- FAA/BTS/OurAirports = static runway reference.
- Baron/OpenWeather/Open-Meteo/Synoptic/IEM = enrichment, archive, fallback, or development sources only.

## Export outputs

The demo app exports:

- Dashboard JSON
- Airport broadcast package JSON
- GeoJSON FeatureCollection
- GRLevelX-style placefile text

## Current status

**Phase 9 — Operational Intelligence Audit: PASSED**

- Day-One Local Prep Ready (Phase 7 audit passed)
- Operational Intelligence Local Prep Usable (Phase 9 audit passed)
- 71 focus airports seeded and live in Supabase
- Aviation Hazards (SIGMET/AIRMET/CWA), ATCSCC Operations Plan, and RouteCast all live
- All 8 export paths verified
- 6/6 pull scripts pass dry-run at 71-airport scale
- Phase 10 hardening/runbook complete

See `audit/day_one_readiness_report.md` for full audit history.

## Operator documentation

- `docs/DAY_ONE_OPERATOR_RUNBOOK.md` — step-by-step operations guide
- `docs/COMMAND_REFERENCE.md` — all commands
- `docs/TROUBLESHOOTING.md` — common issues and fixes
- `docs/SOURCE_FAILURE_PLAYBOOK.md` — what to do when each source fails
- `docs/BROADCAST_USE_GUARDRAILS.md` — what this tool's output may and may not claim on-air

## Day One checklist

- [x] App runs locally.
- [x] Demo mode works.
- [x] Airport Status Board renders — 71 airports, filters verified.
- [x] Airport Detail renders.
- [x] Aviation Hazards renders live SIGMETs/AIRMETs/CWAs.
- [x] ATCSCC / FAA Ops Plan renders.
- [x] RouteCast renders 6 starter routes.
- [x] Graphics Queue works — all 6 actions.
- [x] JSON export works — source_mode verified.
- [x] GeoJSON export works — feature_count verified.
- [x] Placefile export works.
- [x] Source Health renders with live feed-run telemetry.
- [x] No secrets exist in frontend files.
