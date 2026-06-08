# Broadcast Use Guardrails — TravelCast AviatorGraf Prep

Rules for what this tool's output may and may not claim on-air. These guardrails exist because the app assembles data from multiple official and proxy sources. Mixing them up risks misrepresenting official aviation data.

---

## Source Authority Rules

### Do not call NWS forecast proxy an FAA delay forecast

NWS `api.weather.gov` grid forecasts are a **weather-impact proxy** only. They are not FAA traffic management products.

- **Wrong:** "FAA is forecasting a ground delay program at SFO this afternoon."
- **Wrong:** "FAA delays are expected due to NWS forecast data."
- **Right:** "NWS is forecasting conditions at SFO that may be a factor for air travel — a TravelCast forecast-impact proxy shows amber for SFO."
- **Right:** "Forecast Weather Impact — NWS forecast proxy shows elevated risk at SFO."

### Do not call TravelCast route status an official FAA route forecast

RouteCast route prep status is a TravelCast text-matching enrichment. It is not an FAA route forecast, SWAP, or CDR.

- **Wrong:** "FAA is showing elevated delays on the DFW-JFK corridor."
- **Wrong:** "RouteCast confirms FAA traffic management on this route."
- **Right:** "Our TravelCast RouteCast tool shows elevated prep status for DFW-JFK based on current FAA/NAS and hazard data — not an official FAA route forecast."

### Do not say a hazard affects an airport unless the source explicitly supports it

`aviation_hazard_products.affected_airports` is populated from source data. Do not manually infer airport impact from a SIGMET's geographic description unless it is explicitly stated.

- **Wrong:** "This SIGMET over the Midwest will affect Chicago O'Hare."
- **Right:** "An active SIGMET for icing is in effect for portions of the Midwest. Source: AviationWeather.gov. Check Airport Detail for ORD operational status."

### Do not infer cancellations, diversions, or delays beyond source data

TravelCast AviatorGraf Prep does not have access to live flight data. The app does not know if specific flights are cancelled, diverted, or delayed.

- **Wrong:** "Flights into SFO are being diverted due to fog."
- **Wrong:** "Cancellations are expected at JFK due to the GDP."
- **Right:** "FAA NAS Status shows a Ground Delay Program at SFO. Travelers should check with their airline for specific flight status."

---

## Language Rules

### Always preserve source labels in copy

When presenting information from this tool on-air, include the source label:

- "FAA NAS Status shows..." — for operational events
- "AviationWeather.gov reports..." — for METAR/TAF/SIGMET/AIRMET/CWA
- "NWS forecast proxy indicates..." — for forecast impact
- "TravelCast translation of [source] advisory" — for translated text

### Use TravelCast prep language for internal impact assessments

The app uses four internal prep-status terms. These are for graphics preparation — not official language:

| Term | Meaning | Use |
|---|---|---|
| `Significant` | Red operational impact — active closure or GDP | Internal prep |
| `Elevated` | Amber operational or forecast impact | Internal prep |
| `Monitor` | Conditions worth watching but no active program | Internal prep |
| `Normal` | No active impact on record | Internal prep |

Do not present these as official FAA classifications.

### Do not say "safe" or "unsafe" beyond source-supported operational language

The app does not certify flight safety. Source data supports operational planning, not airworthiness determinations.

- **Wrong:** "This airport is unsafe for operations right now."
- **Right:** "FAA NAS Status shows an Airport Closure at [airport]."

---

## Data Freshness and Honesty Rules

### When data is stale, say so

If Source Health shows `stale` or `no_runs` for an official source:
- Do not present that source's data as current.
- Say: "As of [last update time], FAA NAS Status showed..."
- Or: "Source data for [source] is currently unavailable — information may not reflect current NAS state."

### Empty state is better than invented data

If a tab shows an honest empty state ("No active aviation hazard records"), that is correct. Do not speculate about hazards, delays, or programs not in source data.

- **Wrong:** "There are probably SIGMETs in that area based on the weather pattern."
- **Right:** "No active SIGMETs are currently on record in AviationWeather.gov."

### When uncertain, say "source data unavailable" or "not currently stored"

These are safe, honest phrases that preserve credibility:

- "FAA NAS Status data is not currently available."
- "ATCSCC Operations Plan data not currently stored — check fly.faa.gov directly."
- "AviationWeather.gov METAR data is unavailable for [airport]."

---

## What This Tool Is and Is Not

### This tool IS:

- An internal TravelCast / wxSense graphics-preparation console
- A viewer and exporter of official FAA/NWS/AviationWeather source data
- A tool for preparing broadcast-ready packages with proper source labels
- A TravelCast translation layer that explains official source text in plain language

### This tool IS NOT:

- An official FAA product
- An NWS product
- A flight dispatch or clearance system
- A source of flight-specific cancellation or diversion data
- A real-time ATC feed
- A certified weather product

---

## Checklist Before Going to Air

- [ ] Source Health shows `fresh` for FAA NAS Status and AviationWeather
- [ ] Exported Package JSON shows `source_mode: "live"` — not `"demo"`
- [ ] All operational impact copy references FAA NAS Status as the source
- [ ] All METAR/TAF copy references AviationWeather.gov as the source
- [ ] No NWS forecast impact copy is labeled as an FAA delay forecast
- [ ] No route status copy claims to be an official FAA route forecast
- [ ] No hazard copy claims to affect an airport unless `affected_airports` supports it
- [ ] No cancellation or diversion language not supported by source data
- [ ] Data age is noted where it exceeds the recommended freshness window
