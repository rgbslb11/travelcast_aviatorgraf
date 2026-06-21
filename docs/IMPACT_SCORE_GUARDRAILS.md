# Impact Score Guardrails — Phase D1

## Overview

The `impact_score_guardrails` table stores **doctrine-in-schema** guardrails
for the D1 shared impact scoring framework. Every guardrail carries:

- `rule_text` — authoritative doctrine statement
- `allowed_language` — safe phrasing when the relevant signal is present
- `prohibited_language` — phrasing that is never acceptable
- `enforcement_level` — `hard_block` / `operator_flag` / `audit`

Guardrails apply to all scoring models, source lanes, and product phases
unless `applies_to` specifies a narrower scope.

---

## Prohibited Claim Patterns

The following patterns are **hard-blocked** — they must never appear in any
system-generated output text, public claim, or broadcast package.

| Pattern | Why prohibited |
|---|---|
| `NWS alert caused FAA delay` | NWS public alerts are not FAA operational truth |
| `public alert caused airport delay` | Same as above |
| `RouteCast geometry caused delay` | Geometry is a display scaffold, not delay truth |
| `context match proves impact` | C3 context matches are not impact scores |
| `forecast proxy is observed truth` | Forecast proxy is not observation truth |
| `AviaImpact score generated` | AviaImpact is not active in D1 |
| `RoadCast score generated` | RoadCast is not active in D1 |
| `ground stop inferred` | Ground stops require explicit FAA advisory text |
| `restriction inferred` | Restrictions require explicit FAA advisory text |
| `closure inferred` | Closures require explicit FAA advisory text |
| `delay confirmed` | Delay confirmation requires explicit FAA source |
| `delay caused by NWS` | NWS is not FAA operational truth |
| `delay caused by forecast` | Forecast proxy is not operational truth |
| `geometry proves delay` | Geometry is a display scaffold |
| `match equals impact` | Context match is not an impact score |

These patterns are also enforced in `scripts/scoring/shared_impact_scoring.py`
via `validate_no_prohibited_claim(text)`.

---

## Allowed Phrasing

When relevant signals ARE present, use only this class of language:

| Situation | Allowed phrasing |
|---|---|
| NWS alert context near airport | "NWS alert context is present near this airport. Source: Public Weather Alert — NWS CAP." |
| RouteCast corridor displayed | "RouteCast corridor is a display scaffold — no delay claim from geometry." |
| C3 context match present | "Context match present — operator review required before any public claim." |
| Forecast proxy signal | "Forecast weather proxy: NWS forecast suggests conditions may affect operations." |
| No source data available | "Source not available — score not generated." |
| Draft output pending review | "Draft impact score output. Operator review required before public release." |

Never augment allowed phrasing with operational claims that are not supported
by live FAA source data.

---

## Operator Review

Operator review is a **hard-block** before public release.

- All system-generated scoring outputs carry `operator_review_status = 'draft'`.
- `public_release_allowed` defaults to `false`.
- No scoring engine or automation may set `public_release_allowed = true`.
- An operator must explicitly review and accept the output before public release.
- The `v_impact_score_draft_review_queue` view surfaces all pending draft outputs
  with the disclaimer:
  *"Draft impact score outputs require operator review and are not public claims."*

---

## No Public Release by Default

The `assert_no_public_release(result)` function enforces this at the utility layer:

- Raises `ValueError` if `public_release_allowed` is already `True`.
- Sets `public_release_allowed = False` on the result dict.

This function should be called on any result before it is written to storage
or returned to a calling system.

---

## Empty State Doctrine

When required source inputs are missing, stale, or below the minimum
confidence threshold:

1. Return `empty_state_result(reason)` — not a score.
2. Do not default the score to zero as if no impact exists.
3. Log the reason for empty state so operators can diagnose missing data.
4. Do not populate missing inputs with invented or default values.
5. Do not generate non-zero scores from empty inputs.

A zero score is meaningful only when source data explicitly supports it.
Empty state is better than invented scoring data.

---

## D1 / D2 / D3 Boundaries

| Phase | Guardrail |
|---|---|
| D1 | No AviaImpact scores. No RoadCast scores. No live output rows. Framework only. |
| D2 | AviaImpact scores only. Requires separate D2 design approval. No RoadCast. |
| D3–D5 | RoadCast scores only. Requires separate D3–D5 design approval. |

The guardrails `no_aviaimpact_output_in_d1` and `no_roadcast_output_in_d1` are
both `hard_block` enforcement. They remain active until D2/D3 explicitly
supersedes them in their respective phases.

---

## Future Product-Specific Guardrails

When D2 (AviaImpact) is activated:
- It will inherit all D1 guardrails.
- It will add AviaImpact-specific guardrails (e.g. minimum FAA source confidence,
  maximum forecast-proxy weight, operator review cadence).
- The `no_aviaimpact_output_in_d1` guardrail will be superseded for D2 scope only.

When D3–D5 (RoadCast) is activated:
- It will inherit all D1 guardrails.
- It will add RoadCast-specific guardrails (e.g. highway/corridor scope limits,
  forecast staleness limits, public-facing language controls).
- The `no_roadcast_output_in_d1` guardrail will be superseded for D3–D5 scope only.

No product-specific guardrails may be defined or bypassed without explicit
phase design approval and a separate audit pass.

---

## Guardrail Enforcement Summary

| Guardrail key | Type | Level |
|---|---|---|
| `no_invented_source_data` | source_boundary | hard_block |
| `no_nws_alert_causes_faa_delay` | prohibited_claim | hard_block |
| `no_routecast_geometry_causes_delay` | prohibited_claim | hard_block |
| `no_context_match_equals_impact_score` | prohibited_claim | hard_block |
| `no_forecast_proxy_as_observation` | prohibited_claim | hard_block |
| `no_aviaimpact_output_in_d1` | product_boundary | hard_block |
| `no_roadcast_output_in_d1` | product_boundary | hard_block |
| `operator_review_required_for_public_release` | operator_control | hard_block |
