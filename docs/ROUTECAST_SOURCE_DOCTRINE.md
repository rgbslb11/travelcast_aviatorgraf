# ROUTECAST SOURCE DOCTRINE
# TravelCast AviatorGraf Prep — RouteCast Source Lane Rules

**Phase C2 — RouteCast Corridor Geometry + Impact Styling**

---

## Source Lane Overview

TravelCast maintains strict lane separation across all source types. RouteCast corridor geometry is a display/planning scaffold and occupies a separate lane from all operational truth sources.

| Lane | Source | Label | What It Settles |
|------|--------|-------|----------------|
| **RouteCast Corridor Scaffold** | Top-50 reference + FAA waypoints | `RouteCast Corridor Scaffold — Static Reference` | Display corridors and planning geometry; NOT delay truth |
| **Current Operational Impact** | FAA NAS / ATCSCC | `Current Operational Impact — FAA NAS / ATCSCC` | Ground stops, GDPs, route closures, AAR, TMIs, delays |
| **Aviation Weather Truth** | AviationWeather.gov | `Aviation Weather Truth — AviationWeather.gov` | METAR, TAF, PIREP, SIGMET, AIRMET |
| **Public Weather Alert** | NWS CAP / api.weather.gov | `Public Weather Alert — NWS CAP` | Public weather hazard warnings, watches, advisories |
| **Forecast Weather Impact** | NWS / api.weather.gov forecast | `Forecast Weather Impact — NWS forecast proxy` | Public weather forecast; NOT FAA delay data |

---

## Top-50 Busiest Route Source File

**Source role:** Static RouteCast reference artifact  
**Not:** Live FAA delay truth  
**Not:** ATCSCC operational impact data  
**Not:** Official routing data  
**Not:** A source of delay forecasts or restrictions  

The Top-50 busiest U.S. aviation route source file identifies priority corridors for RouteCast display. It is a historical reference based on passenger volume or flight frequency, not a live operational feed.

**Required label when displayed:** `RouteCast Corridor Scaffold — Static Reference`  
**Required field:** `route_rank_basis = 'static_top_50_busiest_route_reference_not_delay_truth'`

---

## FAA Waypoint / Coordinate Artifacts

**Source role:** Route geometry inputs for coordinate resolution  
**Not:** Delay truth  
**Not:** Live ATC routing data  
**Not:** Filed or cleared flight route data  
**Not:** Certified airway routing for aviation use  

FAA waypoint coordinate files (NASR, DAFIF, or equivalent) provide lat/lon coordinates for FAA fixes and navaids. In TravelCast, these are used to resolve waypoint labels in the Top-50 route label strings into map coordinates.

**Do not:**
- Claim that a corridor built from waypoint coordinates represents an actual filed or cleared routing
- Use waypoint coordinates to claim precise FAA airway routing
- Invent coordinates for unresolved waypoints
- Infer fixes that are not present in the source data

---

## RouteCast Corridor Geometry

**Source role:** planning/display scaffold — display and planning use only  
**Not:** FAA operational delay truth  
**Not:** ATCSCC TMI or restriction  
**Not:** Filed or cleared flight route  
**Not:** Certified airway  

RouteCast corridor geometry is a LineString connecting resolved waypoint coordinates along a known route corridor. It is built using the `resolved_waypoint_control_line` method.

**Geometry confidence levels (not operational levels):**
- `unvalidated` — not yet reviewed
- `control_line_scaffold` — built from resolved waypoints; requires visual validation
- `partially_resolved` — built from subset of waypoints; some unresolved
- `needs_source_file` — cannot be built without source CSV

**Do not claim:**
- "FAA has routed flights along this corridor" (from geometry alone)
- "Delays confirmed on this corridor" (from geometry alone)
- "Route restriction based on corridor geometry"
- Any operational ATC impact derived solely from corridor geometry

---

## FAA NAS / ATCSCC — Current Operational Impact

This lane remains separate and is the ONLY authoritative source for:
- Ground stops (GS)
- Ground delay programs (GDP)
- Airspace flow programs (AFP)
- Traffic management initiatives (TMI)
- Airport arrival rates (AAR)
- Route closures and miles-in-trail (MIT) restrictions
- Delay minutes

**RouteCast corridor geometry does NOT substitute for, predict, or confirm FAA NAS / ATCSCC data.**

C3 (ATCSCC playbook matching) will associate corridor geometry with active ATCSCC TMIs — but that integration is future work and must not be built in Phase C2.

---

## AviationWeather.gov — Aviation Weather Truth

AviationWeather.gov data (METAR, TAF, PIREP, SIGMET, AIRMET) remains aviation-weather truth. RouteCast corridor geometry does not represent, predict, or confirm aviation weather conditions.

For confirmed IFR conditions along a corridor → use AviationWeather.gov METAR/TAF.  
For confirmed significant meteorological hazards → use AviationWeather.gov SIGMET/AIRMET.

---

## NWS CAP / Public Alerts — Public Weather Alert Truth

NWS public weather alerts (Phase C1) may overlap with RouteCast corridor geometry. When an alert polygon intersects a corridor, the corridor may be styled with `routecast_public_alert_context`. This is **weather hazard CONTEXT only**.

**An NWS alert overlapping a corridor does NOT:**
- Confirm delays on that corridor
- Confirm a route closure
- Confirm a GDP or ground stop related to that corridor
- Constitute FAA operational data

For confirmed FAA operational data → use FAA NAS / ATCSCC (Current Operational Impact lane).

---

## NWS Forecast Impact — Forecast Proxy Only

NWS point/grid forecast data is a forecast weather-impact proxy. It is not an FAA delay forecast and must not be used to claim delay probability on a RouteCast corridor.

---

## Anti-Hallucination Rules

1. **Do not invent Top-50 route rows.** Only seed corridors from the actual source CSV.
2. **Do not invent waypoint coordinates.** If a fix is not in the coordinate source, it remains unresolved.
3. **Do not claim route restrictions from geometry.** Geometry alone does not prove ATC restrictions.
4. **Do not claim delays from corridor rank.** Rank reflects historical traffic volume, not operational impact.
5. **Do not claim NWS alert causes FAA delay on corridor.** Alert overlap is weather context only.
6. **Do not confuse corridor geometry confidence with operational impact confidence.** They are different things.
7. **Empty state is always better than invented data.** If no source file is available, the corridor table is empty — do not fabricate corridors.

---

## Allowed vs. Not Allowed On-Air Language

### Allowed (from C2 data)

- "The DFW–JFK corridor is one of the busiest domestic routes in the U.S."
- "A Dense Fog Advisory is in effect along the DFW–JFK corridor area — check AviationWeather.gov for current conditions."
- "RouteCast corridor geometry is a planning scaffold. Actual routing may differ."
- "Corridor geometry confidence: control_line_scaffold — pending validation."

### Not Allowed (from C2 data alone)

- "Delays on the DFW–JFK corridor."
- "FAA has restricted the DFW–JFK route."
- "Ground stop in effect on this corridor."
- "NWS alert causes delay on the DFW–JFK corridor."
- "Corridor geometry confirms FAA routing."
- "Top-50 rank indicates high delay risk."

---

## Source Priority Summary

| Priority | Source | What It Settles | Label |
|----------|--------|----------------|-------|
| 1 | FAA NAS / ATCSCC | Operational delays, ground stops, GDPs, TMIs | `Current Operational Impact — FAA NAS / ATCSCC` |
| 1 | AviationWeather.gov | Aviation weather conditions (METAR, TAF, PIREP, SIGMET) | `Aviation Weather Truth — AviationWeather.gov` |
| 1 | NWS CAP | Public weather hazard alerts | `Public Weather Alert — NWS CAP` |
| 2 (proxy) | NWS forecast | Forecast weather-impact proxy | `Forecast Weather Impact — NWS forecast proxy` |
| Scaffold | Top-50 + FAA waypoints | RouteCast corridor display planning | `RouteCast Corridor Scaffold — Static Reference` |

Source labels are not optional. Every user-visible corridor card, map feature, and export package must carry the appropriate source label and a geometry confidence indicator.
