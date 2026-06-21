# Impact Score Source Doctrine — Phase D1

## Overview

Every source lane in the D1 shared scoring framework carries a defined
`truth_role`, `allowed_use`, `prohibited_use`, and `claim_boundary`.
This is **doctrine-in-schema**: the rules are stored in `impact_score_source_lanes`
and enforced at audit, display, and operator review.

No invented source data may be used as a scoring input.
Empty inputs must trigger empty-state behavior — not invented signals.

---

## Source Lane Definitions

### 1. FAA Operational Truth Lane

**source_lane_key:** `faa_operational_truth`
**Label:** Current Operational Impact — FAA NAS / ATCSCC
**truth_role:** `operational_truth`

**Allowed use:**
- State current FAA-issued operational programs: GDP, GS, AFP, MIT, reroute.
- Reference official delay programs and ATC restrictions when advisory text
  explicitly supports the claim.

**Prohibited use:**
- Do not invent advisories.
- Do not claim delay without explicit FAA advisory text.
- Do not derive operational programs from weather context or corridor geometry.

**Claim boundary:** Only FAA NAS / ATCSCC / NOTAM / official airport sources
may be claimed as operational truth.

---

### 2. Aviation Weather Truth Lane

**source_lane_key:** `aviation_weather_truth`
**Label:** Aviation Weather Truth — AviationWeather METAR/TAF
**truth_role:** `aviation_weather_truth`

**Allowed use:**
- Report current aviation weather conditions: METAR, TAF, SIGMET, AIRMET,
  CWA, PIREP.
- Use to describe weather hazards near airports or corridors.

**Prohibited use:**
- Do not claim aviation weather causes FAA delay programs.
- Do not claim aviation hazards equal operational restrictions.

**Claim boundary:** AviationWeather.gov sources are aviation-weather truth —
not FAA operational delay truth.

---

### 3. Public Weather Alert Truth Lane

**source_lane_key:** `public_weather_alert_truth`
**Label:** Public Weather Alert — NWS CAP
**truth_role:** `public_weather_alert_truth`

**Allowed use:**
- Describe public weather alert context near airports or corridors.
- Reference NWS CAP event type, area, and headline as weather context.

**Prohibited use:**
- Do not claim NWS public alerts cause FAA delay.
- Do not claim NWS alerts equal ground stops, GDPs, or arrival rate reductions.
- Public alerts are not FAA operational truth.

**Claim boundary:** NWS CAP public alerts are Public Weather Alert Truth —
not FAA operational delay truth.

---

### 4. Forecast Proxy Lane

**source_lane_key:** `forecast_proxy`
**Label:** Forecast Weather Impact — NWS forecast proxy
**truth_role:** `forecast_proxy`

**Allowed use:**
- Describe NWS grid forecast impact as a forecast weather proxy.
- May inform anticipated weather conditions at airports.

**Prohibited use:**
- Do not describe forecast proxy output as observed weather.
- Do not describe forecast proxy as an official FAA delay forecast.
- Forecast proxy is not observation truth.

**Claim boundary:** NWS forecast proxy is a planning signal — not observation
truth and not FAA delay truth.

---

### 5. RouteCast Geometry Scaffold Lane

**source_lane_key:** `routecast_geometry_scaffold`
**Label:** RouteCast Corridor Geometry — Planning/Display Scaffold
**truth_role:** `planning_scaffold`

**Allowed use:**
- Display RouteCast corridor routes on maps.
- Use corridor endpoints and waypoints to provide geographic context.

**Prohibited use:**
- Do not claim corridor geometry causes delay.
- Do not claim corridor geometry equals an ATC routing decision.
- RouteCast geometry is not delay truth and not FAA operational truth.

**Claim boundary:** RouteCast corridor geometry is a planning/display scaffold —
not FAA operational delay truth.

---

### 6. RouteCast Context Match Lane

**source_lane_key:** `routecast_context_match`
**Label:** RouteCast Context Match — Advisory/Hazard Context Scaffold
**truth_role:** `context_match`

**Allowed use:**
- Associate RouteCast corridors with nearby advisory or hazard context.
- Use as a display hint that advisory context is present near a corridor.

**Prohibited use:**
- Do not claim a context match is an impact score.
- Do not claim a context match proves delay or restriction.
- C3 context matches are not impact scores.

**Claim boundary:** C3 context matches are context scaffolds — not delay claims
and not impact scores.

---

### 7. ATCSCC Context Match Lane

**source_lane_key:** `atcscc_context_match`
**Label:** ATCSCC Advisory Context Match — C3 Scaffold
**truth_role:** `context_match`

**Allowed use:**
- Reference that an ATCSCC advisory mentions airports or fixes near a corridor.
- Use as a context signal for operator review.

**Prohibited use:**
- Do not claim an ATCSCC advisory context match equals an active delay program.
- Do not generate impact scores solely from context matches.
- Context matches are not operational delay claims.

**Claim boundary:** ATCSCC advisory context matches are context scaffolds —
not delay claims or impact scores.

---

### 8. Manual Operator Review Lane

**source_lane_key:** `manual_operator_review`
**Label:** Manual Operator Review — Operator-Verified Signal
**truth_role:** `operator_verified`

**Allowed use:**
- Record operator-confirmed signal values after human review.
- May upgrade draft output status after explicit review.

**Prohibited use:**
- Do not auto-populate operator review signals from system scoring.
- Do not treat draft scoring output as operator-verified without explicit review.

**Claim boundary:** Operator review is a human gate — not an automated scoring
signal.

---

## No Invented Source Data

Scoring inputs must be traceable to a real source row.

- Do not invent advisory data to produce a non-zero score.
- Do not invent weather observations to meet input requirements.
- Do not use stale data as if it were current without flagging staleness.
- Do not populate empty inputs with default values to produce scores.

If a required input is missing: return `empty_state_result()`.
Empty state is better than invented scoring data.

---

## Lane Boundary Summary

| Lane | May claim | May NOT claim |
|---|---|---|
| FAA operational truth | Current FAA operational programs (GDP, GS, AFP, MIT) | Invented advisories; delay without advisory text |
| Aviation weather truth | Current METAR/TAF/SIGMET/AIRMET conditions | FAA delay programs; operational restrictions |
| Public weather alert truth | NWS CAP alert context near airports | FAA delay; ground stops; GDPs |
| Forecast proxy | Anticipated weather conditions (forecast) | Observed truth; official FAA delay forecast |
| RouteCast geometry scaffold | Geographic display context | Delay claims; ATC routing decisions |
| RouteCast context match | Advisory/hazard context near corridor | Impact scores; delay proofs |
| ATCSCC context match | Advisory mentions corridor area | Active delay programs; impact scores |
| Manual operator review | Operator-confirmed signal values | Auto-populated scoring inputs |
