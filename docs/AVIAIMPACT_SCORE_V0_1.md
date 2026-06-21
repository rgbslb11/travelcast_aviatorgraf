# AviaImpact Score v0.1 — Phase D2

## Purpose

AviaImpact is a **draft aviation impact scoring model** built on the D1 Shared
Impact Scoring Framework. It produces deterministic, component-weighted draft
scores for internal operator review.

AviaImpact draft scores are not FAA operational-delay claims. They do not
replace FAA/NAS/ATCSCC operational truth. They are internal context signals
that require operator review before any use.

Empty state is better than invented scoring data.

---

## Model Logic

AviaImpact v0.1 uses a **five-component weighted scoring model**. Each component
maps one source lane to a normalized score in [0, 5]. The overall score is the
weighted average of available components.

Context is not impact. Forecast proxy is not observation. Missing data must
produce empty-state results — not zero-as-fact.

All outputs default to:
- `operator_review_status = 'draft'`
- `operator_review_required = True`
- `public_release_allowed = False`

Operator review required before any AviaImpact output is used externally.

---

## Component Weights

| Component key | Source lane | Weight |
|---|---|---|
| `official_operational_status_component` | `faa_operational_truth` | **0.35** |
| `aviation_weather_component` | `aviation_weather_truth` | **0.25** |
| `public_alert_context_component` | `public_weather_alert_truth` | **0.15** |
| `routecast_context_component` | `routecast_context_match` | **0.15** |
| `forecast_proxy_component` | `forecast_proxy` | **0.10** |
| **Total** | | **1.00** |

---

## Component Descriptions

### 1. Official Operational Status (weight 0.35)

Source: FAA/NAS/ATCSCC/official airport sources — operational truth.

| Status | Score |
|---|---|
| Airport closure / unavailable | 5 |
| Ground stop (explicit) | 5 |
| Ground delay program (GDP) | 4 |
| AFP / reroute / major TMI | 3 |
| MIT / staffing / route constraint | 2 |
| No known impact (from official source) | 0 |
| Missing / stale / unknown | empty-state |

Official operational source required for operational delay claims.
Do not infer operational delay from weather context, NWS alerts, or geometry.

### 2. Aviation Weather Conditions (weight 0.25)

Source: AviationWeather.gov / official aviation-weather sources.

| Status | Score |
|---|---|
| LIFR / severe convective / major runway impact | 5 |
| IFR / strong convective / high wind | 3 |
| MVFR / moderate weather limitation | 2 |
| VFR / no hazard | 0 |
| Missing / stale | empty-state |

Weather hazard does not equal FAA delay without official operational confirmation.
Do not fabricate METAR/TAF values.

### 3. Public Alert Context (weight 0.15)

Source: NWS CAP/WEA public alerts (public_weather_alert_truth).

| Alert type | Score |
|---|---|
| Tornado Warning / Severe Thunderstorm Warning / Flash Flood Warning | 4 |
| Watch / Advisory | 2 |
| Special Weather Statement / lower urgency | 1 |
| Fresh source confirms no active relevant alert | 0 |
| Missing / stale | empty-state |

NWS alerts provide public-weather-alert context only.
Public alerts do not prove airport delay or route disruption.
Missing or stale alert source must be empty-state, not zero-as-fact.

### 4. RouteCast Corridor Context (weight 0.15)

Source: C3 corridor × advisory / hazard context matches.

| Context type | Score |
|---|---|
| High-confidence official ATCSCC corridor match | 3 |
| Medium airport/fix overlap with official advisory | 2 |
| Public alert / hazard context match only | 1 |
| Geometry scaffold only | 0 |
| Low-text context only (requires operator review) | 1 max |
| Missing / stale | empty-state |

Context is not impact. RouteCast geometry is a planning/display scaffold —
not delay truth. High context with no official operational/weather backing
must not produce public claims.

### 5. Forecast Proxy (weight 0.10)

Source: NWS forecast / TAF forecast / official aviation-weather forecast.

| Forecast status | Score |
|---|---|
| High-impact forecast hazard in time window | 3 |
| Moderate forecast hazard | 2 |
| Low forecast hazard | 1 |
| Fresh forecast shows no meaningful hazard | 0 |
| Missing / stale | empty-state |

Forecast proxy is not observation. Forecast proxy cannot override official
current operational truth. Forecast proxy cannot create delay claims.

---

## Source Lanes

All AviaImpact components consume registered D1 source lanes:

- `faa_operational_truth` — FAA/NAS/ATCSCC operational truth
- `aviation_weather_truth` — AviationWeather.gov aviation-weather truth
- `public_weather_alert_truth` — NWS CAP public alert context
- `routecast_context_match` — C3 corridor context scaffold
- `forecast_proxy` — NWS forecast proxy (not observation)

---

## Input Requirements

Required for non-empty scoring:
- At least one of `faa_operational_truth` OR `aviation_weather_truth` must be
  available and fresh.
- Total available component weight must be ≥ 0.60.

If these conditions are not met, the result is `do_not_score` / empty-state.

---

## Empty-State Behavior

When required inputs are missing, stale, or insufficient:
- Return `do_not_score` / empty-state result.
- Do not backfill missing components with zero.
- Do not treat missing source as confirmed no-impact.
- Empty state is better than invented scoring data.
- Clearly list missing components in `missing_components` field.

---

## Partial Scoring Rules

When not all components are available (v0.1):

1. At least one official operational OR aviation-weather source must be fresh
   and source-backed.
2. Total available component weight must be ≥ 0.60.
3. Unavailable components are listed in `missing_components`.
4. Available weights are renormalized to sum to 1.0 for the available subset.
5. Confidence is downgraded:
   - Available weight ≥ 0.90 → `high`
   - Available weight ≥ 0.75 → `medium`
   - Available weight < 0.75 → `low`

Never backfill a missing component with zero. Never treat missing source as
no impact.

---

## Score Mode

| `score_mode` | Meaning |
|---|---|
| `draft_internal` | All required sources present or partial scoring with official source |
| `weather_context_only` | No official operational source; weather/alert/context only |
| `full_coverage` | All 5 components available and scored |
| `do_not_score` | Insufficient source coverage — empty state |

When `score_mode = 'weather_context_only'`, the score reflects weather and
context signals only. No operational delay claim is supported.

---

## Score Labels (generic_0_5 scale)

| Level | Label |
|---|---|
| 0 | No Known Impact |
| 1 | Minimal Context |
| 2 | Monitor |
| 3 | Elevated |
| 4 | High |
| 5 | Severe / Critical |

---

## Explanation JSON

Every AviaImpact output includes an `explanation` JSON field containing:

```json
{
  "model_key": "aviaimpact_v0_1",
  "model_version": "0.1",
  "overall_score": 3.2,
  "overall_level": 3,
  "score_mode": "draft_internal",
  "available_weight": 0.75,
  "missing_components": ["forecast_proxy_component"],
  "components": {
    "official_operational_status": {
      "available": true,
      "score": 3.0,
      "weight": 0.35,
      "explanation": "Official operational source explicitly reports: reroute. Score 3/5."
    }
  },
  "disclaimer": "AviaImpact draft scores require operator review and are not FAA operational-delay claims.",
  "note": "This explanation is for operator review only."
}
```

---

## Source Summary JSON

Every output includes a `source_summary` JSON field with per-component
source lane, availability, freshness, confidence, and raw value:

```json
{
  "official_operational_status": {
    "source_lane_key": "faa_operational_truth",
    "available": true,
    "stale": false,
    "confidence": "high",
    "raw_value": "reroute"
  }
}
```

---

## Draft/Internal Status

All AviaImpact v0.1 outputs are draft/internal:
- `operator_review_status = 'draft'` on all rows
- `public_release_allowed = false` on all rows
- No automatic score publication
- No automatic public release

---

## Operator-Review Workflow

1. Score is generated by `compute_aviaimpact_score()` and stored as draft.
2. Operator reviews `v_aviaimpact_draft_review_queue`.
3. Operator reads `explanation` and `source_summary` for each row.
4. Operator checks component explanations and verifies source accuracy.
5. Operator sets `operator_review_status = 'accepted'` and
   `public_release_allowed = true` only after explicit approval.
6. No automatic step may set `public_release_allowed = true`.

Operator review required before any AviaImpact output is used externally.

---

## What AviaImpact Does Not Claim

- AviaImpact does not claim FAA-confirmed delay.
- AviaImpact does not claim ground stop, GDP, AFP, MIT, closure, or restriction
  unless the official operational source explicitly supports the claim.
- AviaImpact does not derive operational delay from NWS alerts, RouteCast
  geometry, or C3 context matches.
- AviaImpact does not claim forecast proxy output equals observed conditions.
- AviaImpact does not publish scores without operator review.
- AviaImpact does not generate RoadCast output.

Context is not impact. Forecast proxy is not observation.
Empty state is better than invented scoring data.
