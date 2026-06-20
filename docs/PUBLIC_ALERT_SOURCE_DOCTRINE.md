# PUBLIC ALERT SOURCE DOCTRINE
# TravelCast AviatorGraf Prep — NWS CAP / WEA Source Rules

**Phase C1 — NWS CAP / WEA Public Alert Ontology**

---

## Source Lane Overview

TravelCast maintains strict lane separation between four source types. Public weather alerts are one lane — they must never be confused with the other three.

| Lane | Source | Label | What It Settles |
|------|--------|-------|----------------|
| **Public Weather Alert** | NWS CAP / api.weather.gov | `Public Weather Alert — NWS CAP` | Public weather hazard warnings, watches, advisories for public and travel context |
| **Aviation Weather Truth** | AviationWeather.gov | `Aviation Weather Truth — AviationWeather.gov` | METAR, TAF, PIREP, SIGMET, AIRMET — observed and forecast conditions at aerodromes |
| **Current Operational Impact** | FAA NAS / ATCSCC | `Current Operational Impact — FAA NAS / ATCSCC` | Ground stops, GDPs, route closures, AAR, TMIs, delay data |
| **Forecast Weather Impact** | NWS / api.weather.gov forecast | `Forecast Weather Impact — NWS forecast proxy` | Public weather forecast as a proxy for travel impact; NOT delay data |

These lanes have different sources, different claim authority, and different on-air labels. They must not be substituted for one another.

---

## NWS CAP / WEA — Public Weather Alert Truth

**Source:** `https://api.weather.gov/alerts/active`
**Operated by:** NOAA / National Weather Service
**Trust tier:** 1 (authoritative for public weather hazards)
**Mission-critical allowed:** Yes, for weather alert context

### What NWS CAP Covers

| Alert Type | Examples | TravelCast Use |
|------------|----------|----------------|
| Warnings | Tornado Warning, Winter Storm Warning, Blizzard Warning | High-priority weather context near airports |
| Watches | Severe Thunderstorm Watch, Winter Storm Watch | Elevated weather context |
| Advisories | Dense Fog Advisory, Wind Advisory, Freezing Rain Advisory | Moderate weather context |
| Statements | Special Weather Statement | Informational weather context |
| Emergency Alerts | Extreme Wind Warning | Critical weather context |

### What NWS CAP Does NOT Cover

- FAA operational traffic flow
- Ground stops or ground delay programs
- Airport arrival rates (AAR)
- Route closures or en-route restrictions
- ATCSCC traffic management initiatives
- Flight-specific delay predictions
- METAR / TAF / PIREP (those are AviationWeather.gov)

---

## FAA NAS / ATCSCC — Current Operational Impact

This lane is separate and remains the only authoritative source for:
- Ground stops (GS)
- Ground delay programs (GDP)
- Airspace flow programs (AFP)
- Route closures and miles-in-trail (MIT) restrictions
- Airport arrival rates (AAR)
- ATCSCC traffic management initiatives (TMIs)
- Delay minutes

**A NWS public weather alert — even an Extreme / Immediate Tornado Warning — does not constitute a ground stop, GDP, or FAA delay notice.**

The correct statement is: *"A Tornado Warning is in effect near [airport]. For FAA operational status, see FAA NAS / ATCSCC data."*

---

## AviationWeather.gov — Aviation Weather Truth

This lane is separate and covers:
- METAR (surface weather observations at aerodromes)
- TAF (terminal aerodrome forecasts)
- PIREP (pilot weather reports)
- SIGMET (significant meteorological information)
- AIRMET (airmen's meteorological information)

**Do not substitute NWS public alerts for AviationWeather.gov data in aviation weather product.** A Tornado Warning polygon may or may not overlap an airport; the METAR and TAF from AviationWeather.gov are the aviation weather truth for that airport's surface conditions.

---

## NWS Forecast Impact — Forecast Proxy Only

NWS point/grid forecast data (`api.weather.gov/gridpoints`, `api.weather.gov/points`) is used in TravelCast as a **forecast weather-impact proxy** for general travel context. It is a separate lane from NWS CAP alerts.

Both come from `api.weather.gov`, but they serve different roles:
- **NWS CAP alerts**: hazard notifications (official issuances)
- **NWS forecast**: predicted conditions (proxy for travel impact, not operational data)

---

## Anti-Hallucination Rules

1. **Do not invent alert data.** If NWS does not issue an alert for an area, there is no alert for that area. Empty state is correct.
2. **Do not invent polygon geometry.** If an NWS alert has no explicit polygon, store the alert as non-spatial (`has_geometry = false`). Do not attempt to construct geometry from zone/county text.
3. **Do not claim FAA operational impact from alerts.** NWS alerts do not predict, confirm, or substitute for FAA delay data.
4. **Do not confuse alert severity with operational impact severity.** An `Extreme` NWS alert is extremely hazardous weather — it is not an FAA Extreme delay.
5. **Do not use expired alerts without a visible warning.** The `is_expired` flag must be surfaced; expired alerts must not appear as current.
6. **Preserve raw_cap_json.** The full raw NWS alert payload must be retained for audit and verification purposes.

---

## Allowed vs. Not Allowed On-Air Language

### Allowed (from NWS CAP data)

- "A Winter Storm Warning is in effect near O'Hare (ORD) through Thursday morning."
- "NWS has issued a Dense Fog Advisory affecting the Dallas/Fort Worth area."
- "A Tornado Warning is active for counties near DFW as of 14:30Z."
- "Severe Thunderstorm Watch includes the Atlanta metro area."
- "Weather alert context: [event_type] — [headline]. Source: NWS CAP."

### Not Allowed (from NWS CAP data alone)

- "NWS warning causes delays at ORD."
- "Winter Storm Warning indicates a ground stop at DFW."
- "Tornado Warning shows GDP expected at ATL."
- "[N] minute delays expected due to the Severe Thunderstorm Watch."
- "FAA has issued a ground stop due to [NWS alert]." — unless sourced from FAA/ATCSCC separately

---

## Source Label Requirements

Every user-visible card, dashboard panel, or export that displays NWS alert data must include:

1. **Source label**: `Public Weather Alert — NWS CAP`
2. **Alert notice**: *"NWS public weather alerts indicate weather hazards. They are not FAA operational delay data, ground stops, ground delay programs, route closures, or AAR."*
3. **Freshness indicator**: `fetched_at_utc` and `expires_at_utc` must be visible; stale or expired data must be flagged

---

## WEA (Wireless Emergency Alerts)

NWS CAP alerts distributed via IPAWS/WEA appear on cell phones in the alert area. TravelCast uses the same NWS CAP source (api.weather.gov) and does not separately integrate the IPAWS feed.

The WEA status of an alert (whether it was broadcast to cell phones) is not directly available through api.weather.gov. The `parameters_json` field may contain WEA-related parameters in some alert types; future phases may extract and expose this.

---

## Source Priority Summary

When multiple sources provide information about weather conditions at an airport:

| Priority | Source | Claim |
|----------|--------|-------|
| 1 | FAA NAS / ATCSCC | Operational delays, ground stops, GDPs, TMIs |
| 1 | AviationWeather.gov | Aviation weather conditions (METAR, TAF, PIREP, SIGMET) |
| 1 | NWS CAP | Public weather hazard alerts (warnings, watches, advisories) |
| 2 | NWS forecast proxy | Forecast weather impact context (travel planning proxy only) |

Priority 1 sources do not override each other — they answer different questions in separate lanes.
