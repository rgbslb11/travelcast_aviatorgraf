# TRAVELCAST PRODUCT HIERARCHY
# wxSense / TravelCast / AviatorGraf — Brand and Product Architecture

**Locked as of:** 2026-06-20
**Source:** Operation Aero Shear decision captures (wxSense Graphics.txt), BUILD LOGIC 2.txt, WILLOW SPAR doctrine

---

## Network Umbrella

```
wxSense
├── TravelCast               ← travel / aviation / road / field-ops product
├── StormGlass Live          ← severe-weather override / public alert graphics
└── WxSense Lab              ← experimentation; nothing airs from Lab without review
```

---

## TravelCast Sub-Products

```
TravelCast
└── AviatorGraf              ← graphics prep console (current build)
    ├── Airport Status Board
    ├── Airport Detail / Graphics Prep
    ├── Aviation Hazards
    ├── ATCSCC / FAA Ops Plan
    ├── RouteCast             ← BUILT (Phase 8–10)
    ├── Graphics Queue
    ├── Source Health
    ├── RoadCast              ← PLANNED (Phase D)
    └── Public Alerts / WEA  ← PLANNED (Phase C, via StormGlass alignment)
```

---

## Three Route/Road/Impact Products: Distinctions

### RouteCast (BUILT)
- **What it is:** Origin → destination airline route monitoring for configured route pairs
- **Data inputs:** Airport status (FAA NAS), METAR/TAF (AviationWeather.gov), ATCSCC Ops Plan (text matching)
- **Scoring:** Text-based enrichment; no formal 0/5–5/5 score yet; route-level status (Normal / Monitor / Elevated / Significant)
- **Scale:** 6 starter routes (DFW→JFK, SFO→ORD, etc.); expandable
- **What it is NOT:** An official FAA route forecast. Does not predict specific flight delays.
- **Label:** "RouteCast is a TravelCast prep summary, not official FAA routing guidance."
- **Phase C upgrade:** Route corridor geometry + SIGMET/AIRMET/CWA intersection + ATCSCC playbook matching

### RoadCast (PLANNED — Phase D)
- **What it is:** Highway corridor weather-impact scoring for road travel; 0/5–5/5
- **Data inputs:** NWS api.weather.gov forecasts (official source). Static corridor exposure scores (FHWA / truck route / traffic data as reference).
- **Scoring formula:**
  - Weather (40%) + Heavy Truck (10%) + Day-of-Week (10%) + Holiday/Vacation (15%) + Average Traffic (15%) + Route Danger (10%)
- **Scale:** 50 corridors (national highway network), seeded via `data/reference/roadcast_corridors.csv`
- **What it is NOT:** Real-time road closure information. Does not claim closures unless official source confirms.
- **Hard overrides:** Official closure/impassable = force 5/5; chain law / traction law = minimum 4/5
- **Label:** "Forecast Weather Impact — NWS forecast proxy" (never labeled as official CDOT/DOT closure data)
- **Distinction from RouteCast:** RoadCast = roadway corridors; RouteCast = airline origin/destination pairs

### AviaImpact (PLANNED — Phase D)
- **What it is:** Airport aviation flight-impact scoring; 0/5–5/5. Combines terminal weather, convective hazards, FAA/NAS constraints, airport exposure, time-of-day, and route/airspace exposure.
- **Data inputs:** METAR/TAF (AviationWeather.gov), SIGMET/AIRMET/CWA, FAA NAS Status, ATCSCC advisories, static airport exposure scores
- **Scoring formula:**
  - Terminal Weather (30%) + Convective/Hazard (20%) + FAA/NAS Constraint (20%) + Airport Exposure (10%) + Time-of-Day/Bank (10%) + Route/Airspace Exposure (10%)
- **Scale:** 71 focus airports (same set as AviatorGraf Airport Status Board)
- **What it is NOT:** A replacement for FAA operational delay data. Does not claim ground stops, exact delay minutes, or cancellations unless sourced from FAA/ATCSCC.
- **Hard overrides:** FAA ground stop active = force 5/5; GDP active = minimum 4/5
- **Label:** "Forecast-based AviaImpact score: X/5 [Label]" — always qualified as forecast-based
- **Distinction from RouteCast:** AviaImpact = airport-level flight disruption risk; RouteCast = airline route pair monitoring

---

## Product Placement Summary

| Product | Type | Data Basis | Scale | Phase |
|---------|------|-----------|-------|-------|
| Airport Status Board | Live operational dashboard | FAA NAS, AviationWeather, NWS proxy | 71 airports | BUILT |
| Aviation Hazards | Live hazard display | AviationWeather SIGMET/AIRMET/CWA | National | BUILT |
| ATCSCC / FAA Ops Plan | Live operational display | ATCSCC advisories + ops plan | National | BUILT |
| RouteCast | Route pair monitoring | FAA NAS + AviationWeather + ATCSCC text match | 6+ routes | BUILT |
| Source Health | Freshness/staleness monitor | feed_runs + source_systems | All sources | BUILT |
| Graphics Queue + Exports | Broadcast package output | All above sources | 71 airports | BUILT |
| Static Runway Reference | Reference data tab | OurAirports / FAA AIS | 71 airports | Phase B |
| TAF Timeline / PIREP | Aviation weather maturity | AviationWeather.gov | 71 airports | Phase B |
| NWS CAP/WEA Alerts | Public alert display | NWS api.weather.gov | National | Phase C |
| RouteCast Corridor Upgrade | Route intelligence | Above + corridor geometry | 6+ routes | Phase C |
| AviaImpact | Aviation impact score | METAR/TAF + FAA/NAS + static exposure | 71 airports | Phase D |
| RoadCast | Road corridor impact | NWS + static corridor scores | 50 corridors | Phase D |
| wxSense Graphics Templates | Broadcast graphics | All above export packages | All above | Phase E |
| Hosted Worker + Production RLS | Infrastructure | Supabase + Python worker | All above | Phase E |

---

## Approved Output Labels

Use these exact strings in all product cards, exports, and on-air copy:

```
Current Operational Impact — FAA NAS / ATCSCC
Forecast Weather Impact — NWS forecast proxy
Aviation Weather Truth — AviationWeather.gov
Public Alert Truth — NWS CAP / Alerts
Static reference — FAA / OurAirports
Commercial / Enrichment — Baron/OpenWeather/Synoptic/etc.
Graphics Output — TravelCast generated package
```

---

## Source Doctrine (Non-Negotiable)

| Source | Truth Role | May be labeled as |
|--------|-----------|-------------------|
| FAA NAS / ATCSCC | Operational traffic-management truth | Current Operational Impact |
| AviationWeather.gov | Aviation weather truth | Aviation Weather Truth |
| NWS / api.weather.gov | Forecast weather-impact proxy | Forecast Weather Impact |
| NWS CAP / WEA | Public alert and warning truth | Public Alert Truth |
| FAA / BTS / OurAirports | Static reference data | Static reference |
| Baron / OpenWeather / Synoptic | Enrichment / archive / fallback | Commercial / Enrichment |

**Never:**
- Relabel NWS forecast proxy as FAA operational truth
- Claim RouteCast is an official FAA route forecast
- Claim AviaImpact ground stop unless FAA/ATCSCC sourced
- Claim RoadCast road closure unless official DOT/state source confirms
- Generate WEA text; WEA text is NWS CAP-provided only
- Claim TravelCast sends WEA

---

## StormGlass Live Integration Notes

StormGlass Live is the severe-weather override product within wxSense. The NWS CAP/WEA alert lane (Phase C1) feeds StormGlass graphics alongside AviatorGraf's airport context.

StormGlass gets:
- Active NWS alert polygons
- WEA-capable message text (NWS-provided only)
- Airport match context (point_in_polygon or zone_match only)
- Alert priority color (red/amber/blue based on severity/event type)

StormGlass does NOT:
- Generate or rewrite NWS warning text
- Claim airport is "under warning" unless match_type = `point_in_polygon` or `zone_match`
- Mix NWS public alerts into the FAA NAS operational truth lane
