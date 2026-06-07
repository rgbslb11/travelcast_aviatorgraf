# CLAUDE.md — TravelCast AviatorGraf Prep Build Agent Instructions

You are building **TravelCast-aviatorgraf-prep**, an internal TravelCast / wxSense mini-application and automation framework for preparing aviation, weather, airport, route, and FAA/NAS information for broadcast-ready graphics.

## Mission

Build a working, local-first app and the automation framework needed for Claude Code to extend it with minimal human intervention.

The app should support:

- Airport Status Board
- Airport Detail / Graphics Prep
- Aviation Hazards
- ATCSCC / FAA Ops Plan
- RouteCast
- Graphics Queue
- Source Health
- JSON / GeoJSON / GRLevelX-style exports
- Supabase-backed live mode after demo mode is verified

## Non-negotiable rules

- Build working files, not just scaffolding.
- Use plain HTML, CSS, vanilla JavaScript, JSON, SQL, and Python scripts.
- Do not use React, Next.js, Vite, Tailwind, npm, TypeScript, or any build system unless explicitly approved.
- The frontend must run locally with:

```bash
python -m http.server 8080
```

- The frontend must work in demo mode without Supabase.
- Supabase integration must be optional and configurable.
- The project should be structured so it can later be hosted on a domain.
- Never put private secrets in frontend code.
- Never use a Supabase service-role key in browser code.
- Never put Baron, OpenWeather, Synoptic, FlightAware, AeroDataBox, or any other private API key in browser code.
- Real API pulls must happen in backend/local scripts or future server-side functions.
- Do not make real source API calls from browser JS.
- Every user-visible operational card must show a source label and freshness state.

## Source doctrine

- FAA NAS Status / ATCSCC = operational traffic-management truth.
- AviationWeather.gov = aviation weather truth.
- NWS/api.weather.gov = public forecast, alerts, grid forecast, CAP/WEA context, and forecast-impact proxy.
- FAA/BTS/OurAirports = static runway reference.
- Baron/OpenWeather/Open-Meteo/Synoptic/IEM = enrichment, archive, fallback, or development sources only.

## Product honesty

Never imply that an NWS forecast-impact proxy is an official FAA delay forecast.

Use these labels exactly:

- Current Operational Impact — FAA NAS / ATCSCC
- Forecast Weather Impact — NWS forecast proxy
- Aviation Weather Truth — AviationWeather METAR/TAF
- Commercial / Enrichment — Baron/OpenWeather/Synoptic/etc.
- Graphics Output — TravelCast generated package

## Build discipline

Work in phases:

1. Read all control files.
2. Verify file tree.
3. Verify demo-mode app.
4. Verify exporters.
5. Build Supabase live layer.
6. Build pull scripts.
7. Build SQL views.
8. Run audits.
9. Fix blockers.
10. Update readiness report.

After every phase, summarize:

- files created/modified
- what works
- what remains
- blockers

Do not skip the audit.
