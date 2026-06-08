# ACCEPTANCE_CRITERIA.md

The build is accepted only if all required items pass.

**Status as of Phase 10 (2026-06-08): ALL criteria met.**

## Demo mode

- [x] App loads with `python -m http.server 8080`.
- [x] App works without Supabase credentials.
- [x] Airport Status Board renders 10 sample airports in demo mode.
- [x] DEN sample shows GDP, thunderstorms, 63 min average delay, 386 max delay, 16L/16R/17R arrival runways, icon ID 04, red impact.
- [x] Airport Detail renders for DEN.

## Exports

- [x] Dashboard JSON export works — `source_mode`, `generated_at`, `nws_proxy_notice` present.
- [x] Airport broadcast package JSON export works — `source_mode`, `source_labels`, `nws_proxy_notice` present.
- [x] GeoJSON export works and is valid FeatureCollection — `feature_count`, `source_doctrine` present.
- [x] Placefile export works and includes Title, Refresh, Font, Text, End.

## Graphics queue

- [x] Add to Graphics Queue works.
- [x] Queue persists in localStorage.
- [x] Queue item can be removed.
- [x] Queue item can be marked Ready.
- [x] Stale/unknown data shows "Needs Freshness Review" warning.

## Supabase readiness

- [x] `js/config.js` supports Supabase URL and anon key.
- [x] App falls back to demo data if Supabase is not configured.
- [x] No service-role key appears in frontend.
- [x] Missing Supabase views do not crash the app (non-fatal error handling in all modules).

## Operational Intelligence (Phase 8/9)

- [x] Aviation Hazards: live SIGMET/AIRMET/CWA from AviationWeather.gov stored in Supabase.
- [x] ATCSCC / FAA Ops Plan: live advisory ingestion with auto-discovery and --url flag.
- [x] RouteCast: configured routes with origin/dest status enrichment.
- [x] Airport Status Board: operational-impact filters (Red/Amber/No Event/program-type).
- [x] All 3 new panels have demo fallbacks.

## Doctrine

- [x] NWS forecast impact is labeled as forecast proxy ("Forecast Weather Impact — NWS forecast proxy").
- [x] FAA/NAS operational impact is labeled separately ("Current Operational Impact — FAA NAS Status").
- [x] AviationWeather hazards labeled "Aviation Weather Truth — AviationWeather.gov".
- [x] Commercial/enrichment sources are not labeled official.
- [x] TravelCast translation layers do not invent hazards, delays, routes, or advisories.
- [x] Icons use canonical IDs.

## Security

- [x] No private API keys in frontend.
- [x] No service-role key in frontend.
- [x] No real secrets committed.
- [x] `.env` is gitignored.
- [x] `js/config.js` with real credentials is never committed.

## Audit

- [x] `audit/day_one_readiness_report.md` exists.
- [x] Phase 7 verdict: Day-One Local Prep Ready.
- [x] Phase 9 verdict: Operational Intelligence Audit Passed — Local Prep Usable.
- [x] Phase 10 verdict: Hardening and Runbook complete — Product ready for repeatable local operations.

## Runbook / Hardening (Phase 10)

- [x] `docs/DAY_ONE_OPERATOR_RUNBOOK.md` exists with full operator instructions.
- [x] `docs/TROUBLESHOOTING.md` exists with common issues and fixes.
- [x] `docs/SOURCE_FAILURE_PLAYBOOK.md` exists for all 8 source failure scenarios.
- [x] `docs/BROADCAST_USE_GUARDRAILS.md` exists with on-air language rules.
- [x] `docs/COMMAND_REFERENCE.md` exists with all commands.
- [x] Source Health shows mission-critical alert banner for stale/no_runs official sources.
