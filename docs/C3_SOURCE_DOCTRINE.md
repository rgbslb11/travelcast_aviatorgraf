# C3 Source Doctrine — ATCSCC Playbook + Aviation Hazard Corridor Matching

## Overview

Phase C3 connects three existing source lanes to build corridor context
associations. It does NOT produce delay scores, impact scores, AviaImpact,
or RoadCast output. It does NOT invent advisories, matches, or operational facts.

---

## Source Lanes

### 1. FAA / ATCSCC Operational Source Lane

**Label:** `Current Operational Impact — FAA NAS / ATCSCC`
**Source truth lane:** `faa_atcscc_operational_truth`

- FAA NAS Status / ATCSCC / official airport / NOTAM sources are the **only**
  operational aviation truth.
- ATCSCC advisories may be ingested and classified for corridor context matching.
- Advisory text is parsed **conservatively** — only what the text explicitly states.
- C3 may store: advisory type, affected airports/facilities, mentioned routes/fixes,
  traffic management terms, weather terms.
- C3 must NOT: claim delay, claim GDP/GS/AFP is active without live advisory text,
  derive operational facts from weather context or corridor geometry.
- Source URL: `https://nasstatus.faa.gov/api/airport-status-information` and
  `https://www.fly.faa.gov/adv/adv_str.xml` (public FAA pages, no key required).

### 2. RouteCast Corridor Geometry Scaffold Lane

**Label:** `Graphics Output — TravelCast generated package` (for display)
**Source truth lane:** `routecast_atcscc_context_match` (for match rows)

- RouteCast corridor geometry is a **planning/display scaffold only**.
- Not FAA operational delay truth.
- Not ATC restriction truth.
- The Top-50 route file is static RouteCast reference — not delay truth.
- FAA waypoint coordinates are geometry inputs — not delay truth.
- C3 corridor × advisory match rows are context scaffolds — not delay claims.
- Do not invent corridor geometry. Do not invent route segments.

### 3. NWS Public Alert Context Lane

**Label:** `Public Weather Alert — NWS CAP`
**Source truth lane:** `corridor_weather_hazard_context_only`

- NWS CAP / WEA alerts are **Public Weather Alert Truth**.
- NWS alerts are NOT FAA operational delay truth.
- NWS alerts provide public weather hazard context near corridor endpoints.
- They do NOT predict or confirm: ground stops, ground delay programs,
  airport arrival rates, route closures, delay minutes, or ATCSCC TMIs.
- C3 may note that a corridor's endpoint airports are near an active NWS alert.
- C3 must NOT claim the NWS alert causes FAA delay on the corridor.
- Source: `https://api.weather.gov/alerts/active` (no API key required).

### 4. AviationWeather.gov Aviation-Weather Truth Lane

**Label:** `Aviation Weather Truth — AviationWeather METAR/TAF`
**Source truth lane:** `corridor_weather_hazard_context_only`

- AviationWeather.gov SIGMET / AIRMET / CWA = **Aviation Weather Truth**.
- Not FAA operational delay truth.
- Aviation hazards provide weather context near corridor endpoint airports.
- They do NOT constitute or confirm FAA delay programs or restrictions.
- C3 may note that a hazard is present near corridor endpoints.
- C3 must NOT claim the hazard causes FAA delay on the corridor.
- Sources: `https://aviationweather.gov/api/data/sigmet`,
  `https://aviationweather.gov/api/data/airmet`,
  `https://aviationweather.gov/api/data/cwa`

### 5. NWS Forecast Proxy Lane

**Label:** `Forecast Weather Impact — NWS forecast proxy`

- NWS grid forecasts are a **forecast weather impact proxy only**.
- Not FAA operational truth.
- Not used directly in C3 corridor matching.
- May appear as context in existing Phase 5 airport status views.
- Must never be described as an official FAA delay forecast.

---

## No Invented Advisories or Matches

- Do not create advisory rows without real source data.
- Do not invent match rows without real corridor + advisory data.
- Do not invent restriction claims, ground stop claims, or route closure claims.
- SQL migration inserts ONLY static playbook pattern definitions (not advisories).
- All dynamic advisory and match rows are produced by backend pull/match scripts.

---

## No Impact Scoring

C3 does not produce:

- Impact scores of any kind.
- AviaImpact scores (Phase D2).
- D1 Shared Impact Scoring.
- RoadCast outputs (Phases D3–D5).
- Delay minutes from context matching.
- Arrival rate claims from context matching.

These are future phases that require separate design approval, operator
review, and explicit source doctrine validation.

---

## Empty State Doctrine

An empty match table is correct and expected before pull scripts have been run
or before live advisories have been fetched. Empty state is better than invented
data. Audit checks must not fail solely because no live advisory source has been
pulled yet.

---

## Match Confidence Doctrine

| Confidence | Meaning |
|---|---|
| `high_geometry_intersection` | Verified geometry intersection — NOT used in C3 initial scaffold. |
| `medium_airport_or_fix_overlap` | Explicit airport or fix overlap between corridor and advisory/hazard text. |
| `low_text_context` | Broad regional / facility text match. Only written with `--include-low-confidence`. |
| `unmatched` | No safe match found. |

All system-generated match rows default to `operator_review_status = 'draft'`.
No match row is production-ready until an operator has reviewed and accepted it.

---

## Disclaimer Language

The following disclaimers are enforced in C3 SQL views and must be preserved
in any downstream display:

- Advisory dashboard: *"ATCSCC advisory data is FAA operational context.
  RouteCast matches are context scaffolds and are not impact scores."*
- ATCSCC context view: *"This is a RouteCast advisory-context match,
  not a delay claim or ATC restriction claim."*
- Hazard context view: *"Weather hazard context near a corridor is not
  FAA operational delay truth."*
