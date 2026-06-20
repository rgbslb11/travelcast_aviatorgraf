# AVIATION WEATHER SOURCE DOCTRINE
# TravelCast AviatorGraf Prep — Aviation Weather Source Rules

**Phase B3/B4 — Aviation Weather Maturity**

---

## Core Principle

Aviation weather sources and FAA operational sources are **separate, non-interchangeable lanes**.

| Lane | Source | Label | Can Claim |
|------|--------|-------|-----------|
| **Aviation Weather Truth** | AviationWeather.gov | `Aviation Weather Truth — AviationWeather.gov` | Observed and forecast weather conditions at aerodromes; in-flight conditions; hazard areas |
| **Current Operational Impact** | FAA NAS / ATCSCC | `Current Operational Impact — FAA NAS / ATCSCC` | Ground stops, GDPs, route closures, AAR, delays, TMIs |
| **Forecast Weather Impact** | NWS / api.weather.gov | `Forecast Weather Impact — NWS forecast proxy` | Forecast weather that may affect travel; NWS impact proxy ONLY |
| **Commercial / Enrichment** | Baron, OpenWeather, Synoptic, etc. | `Commercial / Enrichment — {source}` | Enrichment, archive, development fallback |

These lanes must never be mixed in on-air product copy without the appropriate source label.

---

## AviationWeather.gov — Aviation Weather Truth

**Source:** `https://aviationweather.gov/`  
**Operated by:** NOAA / National Weather Service Aviation Weather Center (AWC)  
**Trust tier:** 1 (authoritative)  
**Mission-critical allowed:** Yes

### Data Products Covered

| Product | What It Is | Source Label |
|---------|-----------|--------------|
| **METAR** | Hourly or more-frequent surface weather observation at an aerodrome | `Aviation Weather Truth — AviationWeather.gov` |
| **TAF** | Terminal Aerodrome Forecast — official aviation forecast for aerodrome conditions | `Aviation Weather Truth — AviationWeather.gov` |
| **PIREP / UA / UUA** | Pilot Weather Reports — observed in-flight conditions | `Aviation Weather Truth — AviationWeather.gov` |
| **SIGMET** | Significant Meteorological Information — hazards to all aircraft (severe turbulence, icing, volcanic ash, tropical cyclones) | `Aviation Weather Truth — AviationWeather.gov` |
| **AIRMET** | Airmen's Meteorological Information — hazards to small aircraft (IFR, turbulence, mountain obscuration) | `Aviation Weather Truth — AviationWeather.gov` |
| **CWA** | Center Weather Advisory — short-term (2-hour) convective and hazard advisories from ARTCCs | `Aviation Weather Truth — AviationWeather.gov` |

### API Endpoints

```
METAR:  https://aviationweather.gov/api/data/metar?ids={ICAO}&format=json
TAF:    https://aviationweather.gov/api/data/taf?ids={ICAO}&format=json
PIREP:  https://aviationweather.gov/api/data/pirep?ids={ICAO}&format=json&age=3
SIGMET: https://aviationweather.gov/api/data/sigmet?format=json
AIRMET: https://aviationweather.gov/api/data/airmet?format=json
CWA:    https://aviationweather.gov/api/data/cwa?format=json
```

---

## FAA NAS Status / ATCSCC — Current Operational Impact

**Source:** FAA System Command Center / ATCSCC  
**Trust tier:** 1 (authoritative)  
**Mission-critical allowed:** Yes

FAA NAS Status and ATCSCC data are the **only authoritative sources** for:
- Ground stops (GS)
- Ground delay programs (GDP)
- Airspace flow programs (AFP)
- Traffic management initiatives (TMI)
- Arrival demand reduction (ADR)
- Airport arrival rates (AAR)
- Miles-in-trail (MIT) restrictions
- Route closures or reroutes

**Aviation weather data from AviationWeather.gov does NOT predict, confirm, or substitute for FAA operational data.**

---

## NWS / api.weather.gov — Forecast Weather Impact (Proxy Only)

**Source:** `https://api.weather.gov/`  
**Trust tier:** 1 (official NWS), but limited role in TravelCast aviation lane  
**Label:** `Forecast Weather Impact — NWS forecast proxy`

NWS forecast data is used in TravelCast as a **forecast weather-impact proxy** for the general public travel context. It is:
- NOT an official FAA delay forecast
- NOT an aviation weather forecast
- NOT the same as a TAF

NWS data may be used to say: *"NWS forecasts weather that may affect travel in the region."*  
NWS data must NOT be used to say: *"Delays are expected based on the NWS forecast."*

NWS CAP/WEA alerts (public emergency alerts) are addressed in Phase C.

---

## Commercial / Enrichment Sources

| Source | Category | Allowed Use |
|--------|----------|-------------|
| Baron | Commercial enrichment | Supplemental weather visualization; not official aviation weather truth |
| OpenWeather | Commercial enrichment | Development fallback; not official aviation weather truth |
| Open-Meteo | Open model | Archive and development baseline only |
| Synoptic / MesoWest | Observational enrichment | Surface obs enrichment; not authoritative for aviation |
| IEM | Archive | Historical data; not real-time aviation weather truth |

**Commercial / enrichment sources must never be labeled as Aviation Weather Truth.**  
Use label: `Commercial / Enrichment — {source_name}`

---

## Staleness Rules

| Source | TravelCast Stale Threshold | Behavior |
|--------|---------------------------|---------|
| METAR | 2 hours | Older METARs flagged stale in views |
| TAF | 8 hours | TAF data fetched 8+ hours ago flagged `is_stale` |
| TAF periods | Expired | Periods with `valid_to_utc < now()` flagged `is_expired` |
| PIREP (operational) | 2 hours | Observations 2+ hours old flagged `is_operationally_stale` |
| PIREP (fetch) | 8 hours | Fetch data 8+ hours old flagged `is_fetch_stale` |
| SIGMET | Per validity window | Use `valid_to_utc` from source |
| AIRMET | Per validity window | Use `valid_to_utc` from source |

**Stale data must never appear in on-air product without a clearly visible freshness warning.**

---

## Anti-Hallucination Rules

These rules apply to all code, queries, exports, and product outputs in TravelCast:

1. **Do not invent weather data.** If the source does not provide a value, store NULL.
2. **Do not invent coordinates.** PIREP location text (e.g., "40NE ORD") must not be converted to lat/lon unless the source API provides coordinates.
3. **Do not claim FAA operational impacts from weather sources.** AviationWeather.gov data does not predict ground stops, GDPs, delays, or route closures.
4. **Do not claim NWS forecasts are delay forecasts.** NWS is forecast weather impact proxy only.
5. **Do not mix source labels.** TAF data must carry the TAF source label, not the NWS label, and vice versa.
6. **Preserve raw source text.** Store `raw_taf`, `raw_pirep`, etc. for verification and auditability.
7. **Empty state is always better than invented data.** If a pull has not run, show "No data" — do not show cached stale data without a stale warning.

---

## Allowed vs. Not Allowed On-Air Language

### METAR

**Allowed:**
- "JFK is currently reporting IFR conditions with ceiling 800 feet overcast and visibility 1.5 miles."

**Not allowed:**
- "METAR shows delays expected at JFK."
- "Current METAR indicates a ground stop."

### TAF

**Allowed:**
- "The TAF for LAX shows VFR conditions through the afternoon with a TEMPO of IFR from 20Z to 22Z."

**Not allowed:**
- "The TAF predicts delays at LAX."
- "TAF indicates a ground delay program is likely."

### PIREPs

**Allowed:**
- "Pilots report moderate turbulence at FL280 near Denver."
- "A UUA report near ORD indicates severe icing at FL180."

**Not allowed:**
- "PIREP turbulence reports are causing delays at Denver."
- "Pilot reports indicate a ground stop is possible."

### SIGMETs / AIRMETs

**Allowed:**
- "A SIGMET is active for severe turbulence over the Midwest affecting flights at FL280–FL400."

**Not allowed:**
- "SIGMET turbulence is causing ground delays at [airport]."

---

## Source Hierarchy Summary

| Priority | Source | What It Settles | Label |
|----------|--------|----------------|-------|
| 1 | FAA NAS / ATCSCC | Operational impacts (ground stops, GDPs, delays, TMIs) | `Current Operational Impact — FAA NAS / ATCSCC` |
| 1 | AviationWeather.gov | Aviation weather conditions (METAR, TAF, PIREP, SIGMET, AIRMET) | `Aviation Weather Truth — AviationWeather.gov` |
| 1 (proxy) | NWS / api.weather.gov | Public forecast weather impact (not FAA operational) | `Forecast Weather Impact — NWS forecast proxy` |
| 2 | FAA/BTS/OurAirports | Static runway and airport reference | `Static reference — FAA / OurAirports` |
| 3 | Commercial (Baron, OpenWeather, etc.) | Enrichment and development only | `Commercial / Enrichment — {source}` |

Source labels are not optional. Every user-visible operational card and export package must display the appropriate source label and freshness state.
