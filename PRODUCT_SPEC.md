# PRODUCT_SPEC.md — TravelCast Graphics Prep Console

## Purpose

The TravelCast Graphics Prep Console is an internal mini-application for preparing aviation, weather, airport, route, and FAA/NAS information for graphics packages.

It is not a public consumer product. It is a graphics-preparation cockpit.

## Primary users

- TravelCast operator
- wxSense graphics/prep operator
- Broadcast graphics preparer
- Data/ops analyst

## Core screens

1. Airport Status Board
2. Airport Detail / Graphics Prep
3. Aviation Hazards
4. ATCSCC / FAA Ops Plan
5. RouteCast
6. Graphics Queue
7. Source Health

## Core outputs

- Dashboard JSON
- Airport broadcast package JSON
- GeoJSON for MyRadar/Aguacero
- GRLevelX-style placefile text
- Source health/audit reports

## Day One MVP

The app must work with demo data first.

Demo airports:

- DEN
- DFW
- ATL
- MIA
- SFO
- LAS
- LAX
- JFK
- ORD
- IAH

DEN must show:

- Ground Delay Program
- Weather / Thunderstorms
- Average delay 63 minutes
- Maximum delay 386 minutes
- Arrival runways 16L/16R/17R
- Forecast thunderstorms
- Icon ID 04
- Red impact

## Hosted-domain posture

The frontend must be static-hostable on a domain later. Avoid hardcoded local paths. Use relative paths and safe configuration files. Keep future production export hosting in mind: Supabase Storage, backend routes, or CDN paths.
