# AviaImpact Source Doctrine — Phase D2

## Overview

Every AviaImpact component is bound to a source lane defined in the D1
`impact_score_source_lanes` registry. Each lane has explicit `allowed_use`,
`prohibited_use`, and `claim_boundary` fields that are doctrine-in-schema.

AviaImpact draft scores are not FAA operational-delay claims.
Public release false by default — operator must explicitly approve.
Empty state is better than invented scoring data.

---

## Lane 1: FAA Operational Truth

**source_lane_key:** `faa_operational_truth`
**AviaImpact component:** `official_operational_status_component` (weight 0.35)

**Allowed inputs to AviaImpact:**
- Explicit FAA-issued ground stop (text must say "ground stop")
- Explicit ground delay program (GDP) with advisory text
- Explicit AFP, reroute, MIT, or other TMI with advisory text
- Explicit airport closure or runway unavailability from official airport source
- Explicit no-impact statement from official FAA source

**Prohibited claims from this lane:**
- Do not claim delay without explicit FAA advisory text.
- Do not infer operational programs from weather context alone.
- Do not infer GDP or GS from NWS alert.
- Do not infer route restriction from RouteCast geometry.
- Missing/stale official source must be empty-state, not zero.
- Official operational source required for operational delay claims.

**Claim boundary:** Only FAA/NAS/ATCSCC/official airport sources may produce
operational-delay claims in AviaImpact output.

---

## Lane 2: Aviation Weather Truth

**source_lane_key:** `aviation_weather_truth`
**AviaImpact component:** `aviation_weather_component` (weight 0.25)

**Allowed inputs to AviaImpact:**
- METAR/TAF flight category (LIFR/IFR/MVFR/VFR) from AviationWeather.gov
- Convective weather from official aviation-weather sources
- Official SIGMET, AIRMET, or Convective SIGMET
- PIREP severity from official aviation-weather sources
- Wind/gust/ceiling/visibility values from official sources

**Prohibited claims from this lane:**
- Do not fabricate METAR or TAF values.
- Do not score from missing aviation-weather data.
- Weather hazard does not equal FAA delay without official operational
  source confirmation.
- Forecast weather may only be used as forecast proxy if labeled as such.

**Claim boundary:** AviationWeather.gov sources are aviation-weather truth —
not FAA operational delay truth.

---

## Lane 3: NWS Public Alert Context

**source_lane_key:** `public_weather_alert_truth`
**AviaImpact component:** `public_alert_context_component` (weight 0.15)

**Allowed inputs to AviaImpact:**
- Active NWS CAP/WEA warning, watch, or advisory near airport/corridor
- NWS alert type, urgency, and certainty from C1 parsed alert data
- Geographic alert area overlap with airport or corridor polygon

**Prohibited claims from this lane:**
- NWS alerts are context only — not FAA delay truth.
- Public alerts do not prove airport delay.
- Public alerts do not prove route disruption.
- Do not claim NWS alert causes FAA ground stop, GDP, AFP, or restriction.
- Missing or stale alert source must be empty-state, not zero-as-fact.
- Context match is not impact.

**Claim boundary:** NWS public alerts are Public Weather Alert Truth — not
FAA operational delay truth. NWS alert context scores reflect weather hazard
proximity, not confirmed operational impact.

---

## Lane 4: RouteCast Context Match

**source_lane_key:** `routecast_context_match`
**AviaImpact component:** `routecast_context_component` (weight 0.15)

**Allowed inputs to AviaImpact:**
- C3 ATCSCC corridor match confidence (medium or high)
- C3 hazard context match confidence near corridor
- Airport/fix overlap confidence from corridor × advisory matching

**Prohibited claims from this lane:**
- RouteCast geometry is context/scaffold only — not delay truth.
- Context match is not impact.
- Do not claim delay from geometry match alone.
- High context with no official backing must not produce public claims.
- Low-text context match scores a maximum of 1 and requires operator review.
- Context match is not impact. Geometry is not operational truth.

**Claim boundary:** C3 context matches are context scaffolds — not delay
claims and not impact scores. RouteCast geometry is not FAA operational
delay truth.

---

## Lane 5: Forecast Proxy

**source_lane_key:** `forecast_proxy`
**AviaImpact component:** `forecast_proxy_component` (weight 0.10)

**Allowed inputs to AviaImpact:**
- TAF forecast hazard from official aviation-weather sources
- NWS point or grid forecast hazard with explicit time window
- Official aviation-weather forecast product

**Prohibited claims from this lane:**
- Forecast proxy is not observation.
- Forecast proxy cannot override official current operational truth.
- Forecast proxy cannot create delay claims.
- Stale forecast data must be empty-state.
- Forecast-only outputs must be clearly labeled as forecast context.

**Claim boundary:** Forecast proxy is a planning signal — not observation
truth and not FAA delay truth.

---

## Prohibited Claim Examples

These phrases must NEVER appear in AviaImpact output text:

| Prohibited | Because |
|---|---|
| "NWS alert caused FAA delay" | NWS alerts are context only — not FAA delay truth |
| "RouteCast shows a ground stop" | RouteCast geometry is not FAA operational truth |
| "Forecast proxy confirms observed disruption" | Forecast proxy is not observation |
| "Context match proves operational impact" | Context match is not impact |
| "Alert context confirmed delay at JFK" | Public alerts do not confirm FAA delay |
| "Ground stop inferred from weather" | Operational inference prohibited without FAA source |
| "Geometry caused delay on this corridor" | Geometry is not delay truth |

---

## Allowed Phrasing Examples

When relevant signals are present, only this class of language is acceptable:

| Situation | Allowed phrasing |
|---|---|
| FAA ATCSCC advisory reports ground stop | "Official ATCSCC source reports: ground stop. Score: Severe / Critical (5). Source: FAA/NAS/ATCSCC." |
| NWS tornado warning near airport | "NWS tornado warning context is present near this airport. This does not confirm airport delay. Source: Public Weather Alert — NWS CAP." |
| IFR conditions from AviationWeather.gov | "Aviation weather: IFR reported. Source: AviationWeather.gov. Note: weather conditions do not confirm FAA delay without official operational source." |
| RouteCast corridor has high advisory match | "RouteCast corridor has high-confidence ATCSCC advisory context. Context match is not impact. Operator review required." |
| Missing official source | "Official operational source not available — empty state. Do not infer delay." |
| Score is weather-context-only | "Score reflects aviation weather context only — no official operational source available. Not an operational delay claim." |

---

## Missing / Stale Source Handling

| Condition | Required behavior |
|---|---|
| Component source not available | Return empty-state for that component (`do_not_score`) |
| Component source stale | Mark stale, return empty-state for that component |
| Available weight < 0.60 | Return overall `do_not_score` / empty-state result |
| No official operational or weather source | Return `do_not_score` / empty-state result |
| Unknown `explicit_status` value | Return empty-state for that component |

Do not backfill missing components with zero.
Do not treat missing source as confirmed no-impact.
Public release false by default — operator must explicitly approve any release.
Empty state is better than invented scoring data.
Official operational source required for operational delay claims.
