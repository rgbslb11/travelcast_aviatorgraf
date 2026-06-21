# Shared Impact Scoring Framework — Phase D1

## Purpose

Phase D1 builds the **shared scoring architecture** that future product phases
(D2 AviaImpact, D3–D5 RoadCast) will use. It establishes the source lane
registry, guardrails, score scale definitions, and scoring utility primitives.

D1 **does not generate live impact scores**. It does not produce AviaImpact
output. It does not produce RoadCast output. It does not publish graphics or
broadcast outputs. It does not invent weather data, operational data, or
scoring results.

Operator review is required before any draft output becomes a public claim.
Empty state is better than invented scoring data.

---

## Shared Model Registry

The `impact_score_models` table stores draft and placeholder model definitions.

| Field | Purpose |
|---|---|
| `model_key` | Stable machine key (e.g. `shared_impact_scoring_framework_v0_1`) |
| `model_status` | `draft` / `placeholder` / `active` / `deprecated` |
| `intended_product` | Target product (null for shared framework) |
| `source_truth_lanes` | Source lanes this model may consume |
| `allowed_inputs` | Permitted signal types |
| `prohibited_inputs` | Signal types this model must not use |
| `guardrail_notes` | Human-readable guardrail summary |

D1 seeds three model definitions — all `draft` or `placeholder`:

- `shared_impact_scoring_framework_v0_1` — D1 shared framework (draft)
- `aviaimpact_future_v0_1_placeholder` — D2 AviaImpact placeholder (not active)
- `roadcast_future_v0_1_placeholder` — D3–D5 RoadCast placeholder (not active)

No AviaImpact scores are generated in D1. No RoadCast scores are generated in D1.

---

## Source Lane Registry

The `impact_score_source_lanes` table is **doctrine-in-schema**: every source
lane carries explicit `allowed_use`, `prohibited_use`, and `claim_boundary`
fields that define what may and may not be claimed from that lane.

| source_lane_key | truth_role |
|---|---|
| `faa_operational_truth` | operational_truth |
| `aviation_weather_truth` | aviation_weather_truth |
| `public_weather_alert_truth` | public_weather_alert_truth |
| `forecast_proxy` | forecast_proxy |
| `routecast_geometry_scaffold` | planning_scaffold |
| `routecast_context_match` | context_match |
| `atcscc_context_match` | context_match |
| `manual_operator_review` | operator_verified |

Source lane boundaries are enforced at audit, display, and operator review.
See `docs/IMPACT_SCORE_SOURCE_DOCTRINE.md` for full per-lane doctrine.

---

## Generic 0–5 Score Scale

The `impact_score_scale_definitions` table seeds a shared `generic_0_5` scale.
This is **not** a product scale. It is a shared vocabulary for D2/D3 to extend.

| Level | Label | Meaning |
|---|---|---|
| 0 | No Known Impact | No adverse context signals present |
| 1 | Minimal Context | Low-confidence context signal present |
| 2 | Monitor | Medium-confidence signal — no operational claim |
| 3 | Elevated | Multiple signals — operator review recommended |
| 4 | High | Strong context — operator review required |
| 5 | Severe / Critical | Severe signals — mandatory operator review |

All levels require operator review before any public claim. Level 5 requires
explicit operator approval and confirmed FAA source data.

---

## Component / Weight Scoring Model

The D1 utility provides a `weighted_score(components, weights)` function.

Rules:
- Weights must sum to 1.0 (within 1×10⁻⁶ tolerance).
- Component scores clamp to [0, 5].
- Output clamps to [0, 5].
- Empty inputs must return `empty_state_result()` — not zero-as-fact.
- All outputs default `operator_review_required = True`.
- All outputs default `public_release_allowed = False`.

The function is deterministic and pure — no network calls, no file I/O,
no Supabase writes.

---

## Empty-State Behavior

When required source inputs are missing, stale, or insufficient:

- Return `empty_state_result(reason)` — not a score of zero.
- A zero score is a meaningful signal only when source data actually supports it.
- An empty state is better than an invented score.
- `empty_state_result()` always sets `operator_review_required = True` and
  `public_release_allowed = False`.

---

## Operator Review Requirement

No draft score output may become a public claim without operator review.

- All system-generated outputs carry `operator_review_status = 'draft'`.
- `public_release_allowed` defaults to `false` and must never be set
  automatically by the scoring engine.
- An operator must explicitly set `public_release_allowed = true` after
  reviewing and accepting the output.
- The `v_impact_score_draft_review_queue` view surfaces all pending draft
  outputs with the disclaimer:
  *"Draft impact score outputs require operator review and are not public claims."*

---

## Framework vs. Product Score

D1 is a **framework**, not a product:

| Framework (D1) | Product Score (D2/D3+) |
|---|---|
| Defines source lanes | Consumes source lane data |
| Defines guardrails | Enforces guardrails at generation time |
| Defines scale vocabulary | Implements product-specific scale |
| Provides scoring utilities | Generates draft product scores |
| No live outputs | Draft outputs pending operator review |

---

## Future D2/D3 Extension Path

D2 (AviaImpact) will:
- Activate the `aviaimpact_future_v0_1_placeholder` model after separate design approval.
- Consume `faa_operational_truth`, `aviation_weather_truth`, and `forecast_proxy` lanes.
- Produce draft AviaImpact scores into `impact_score_draft_outputs`.
- Require operator review before any public AviaImpact output.

D3–D5 (RoadCast) will:
- Activate the `roadcast_future_v0_1_placeholder` model after separate design approval.
- Consume `forecast_proxy` and `public_weather_alert_truth` lanes.
- Produce draft RoadCast scores into `impact_score_draft_outputs`.
- Require operator review before any public RoadCast output.

Neither D2 nor D3 may be activated without explicit design approval and operator
validation. D1 does not implement either product.

---

## What D1 Does Not Do

- D1 does not generate live impact scores.
- No AviaImpact scores are produced in D1.
- No RoadCast scores are produced in D1.
- D1 does not publish graphics or broadcast outputs.
- D1 does not generate live operational assertions.
- D1 does not invent weather data, advisory data, or scoring results.
- D1 does not claim FAA operational truth from NWS alert context.
- D1 does not claim delay from RouteCast geometry or C3 context matches.
- D1 does not auto-approve any draft output for public release.

Empty state is better than invented scoring data.
