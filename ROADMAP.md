# ROADMAP.md — TravelCast AviatorGraf Prep

## Milestone 1 — Demo-mode graphics prep console

- Static HTML/CSS/JS app.
- Demo airport status board.
- DEN graphics detail card.
- LocalStorage graphics queue.
- JSON/GeoJSON/placefile exporters.

## Milestone 2 — Supabase read mode

- Configure Supabase URL/anon key.
- Read from `v_airport_status_dashboard`.
- Fallback to demo data when Supabase is missing.
- Source health dashboard.

## Milestone 3 — Backend loading engine

- Airport master CSV loader.
- Runway reference loader.
- FAA NAS Status pull.
- AviationWeather METAR/TAF pull.
- NWS forecast pull.
- ATCSCC Ops Plan parser scaffold.

## Milestone 4 — Graphics production outputs

- Supabase Storage export publish.
- MyRadar/Aguacero hosted GeoJSON URLs.
- GRLevelX placefile publishing.
- Broadcast package JSON archive.

## Milestone 5 — RouteCast and StormGlass

- RouteCast route sampling and impact scoring.
- Public alert/CAP/WEA handling.
- AIRMET/SIGMET/CWA overlays.
- StormGlass hazard intelligence boards.
