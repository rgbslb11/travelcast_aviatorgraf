# AviaImpact Operator Review Guide — Phase D2

## Purpose

All AviaImpact draft scores require operator review before any external use.
This document describes what the operator must check before approving or
publishing any AviaImpact output.

Operator review required before any AviaImpact draft score is used externally.
Public release false by default — operator must explicitly set approval.

---

## Before Any Use: Operator Checklist

Before relying on or sharing any AviaImpact draft output, the operator must:

1. **Verify official operational source.** If `score_mode = 'weather_context_only'`
   or `official_operational_status` is in `missing_components`, no operational
   delay claim is supported. The score reflects weather/context signals only.

2. **Read the component explanations.** Open the `explanation.components` field
   and read each component's `explanation` text. Verify the raw source value is
   plausible and consistent with current known conditions.

3. **Check source freshness.** Stale components appear with `stale: true` in
   `source_summary`. A score based on stale data should not be used without
   verifying current source conditions.

4. **Identify missing components.** The `missing_components` field lists which
   source lanes were not available. The score was renormalized without these
   components. Verify whether missing sources might change the score if they
   were available.

5. **Check score confidence.** `score_confidence = 'low'` means the available
   source weight was below 0.75. This score requires more caution than a
   medium- or high-confidence result.

6. **Verify score mode.** Acceptable modes for external use (after review):
   - `draft_internal` — official source present, some components may be missing
   - `full_coverage` — all 5 components available
   - **NOT** `weather_context_only` — this does not support operational claims
   - **NOT** `do_not_score` — this must never be shared

7. **Never publish a score where `public_release_allowed = false`** until you
   have explicitly approved it and set `public_release_allowed = true` and
   `operator_review_status = 'accepted'`.

---

## Reading Component Explanations

Each component in `explanation.components` shows:

- `available`: Whether this component had a valid, fresh source
- `score`: The normalized score (0–5) from this component's source
- `weight`: This component's weight in the model
- `explanation`: Human-readable explanation of what the source reported

Example:

```json
"official_operational_status": {
  "available": true,
  "score": 4.0,
  "weight": 0.35,
  "explanation": "Official operational source explicitly reports: ground_delay_program. Score 4/5. Source: FAA/NAS/ATCSCC/official airport."
}
```

If `available: false`, the component was not present in the score. Do not
assume the missing component would have scored zero.

---

## Before Public Release: What Must Be True

Before setting `public_release_allowed = true`:

- [ ] `operator_review_status` is being changed to `'accepted'`
- [ ] Official operational source is available (`official_operational_status` not in `missing_components`)
- [ ] Source data is fresh (no stale components)
- [ ] `score_mode` is `draft_internal` or `full_coverage` — not `weather_context_only`
- [ ] Component explanations have been read and verified
- [ ] The intended use of the output has been verified as compliant with doctrine
- [ ] The output does not include prohibited claims

Public release false by default. No automated step may set public_release_allowed to true.

---

## Why Public Release Defaults False

AviaImpact draft scores are internal scoring signals. They:
- May be based on incomplete source coverage
- May reflect weather context that does not correspond to an actual FAA delay
- May be stale by the time they are reviewed
- Require human judgment about source accuracy before any external use

A score of 4 or 5 does not mean there is a confirmed FAA delay. It means
the available signals suggest elevated aviation impact context. An operator
must verify against current FAA/ATCSCC source data before any claim is made.

---

## What Claims Are Prohibited

Operators must never publish claims derived from AviaImpact that include:

**Prohibited language:**
- "NWS warning caused the airport delay."
- "RouteCast shows a ground stop."
- "Forecast proxy confirms observed disruption."
- "Context match proves operational impact."
- "Alert context confirmed delay at EWR."
- "The model predicts a ground stop at LAX."
- "AviaImpact shows a restriction is in place."

**Why prohibited:**
- AviaImpact draft scores are not FAA operational-delay claims.
- NWS alerts are weather hazard context only.
- RouteCast geometry is a planning/display scaffold — not delay truth.
- Context match is not impact.
- Forecast proxy is not observation.

---

## Acceptable Internal Wording

When referencing AviaImpact output in internal operator notes:

- `Draft AviaImpact indicates elevated aviation-weather context pending operator review.`
- `Official ATCSCC source reports [exact source-backed status].`
- `NWS alert context is present near the corridor; this does not confirm airport delay.`
- `AviaImpact score is weather-context-only — no official operational source available.`
- `Operator review: score confidence is low due to missing official operational source.`
- `AviaImpact draft score 4 (High) based on official GDP advisory from FAA ATCSCC. Pending operator review for public release.`

---

## What AviaImpact Does NOT Claim

Operators must not characterize AviaImpact output as:

- A replacement for FAA/NAS/ATCSCC operational truth
- A confirmed FAA delay forecast
- A ground stop, GDP, AFP, MIT, closure, diversion, or restriction claim
  unless the official operational source explicitly supports it
- An observation of current conditions when `forecast_proxy` is the
  only available source
- A public score that has been approved for broadcast

Context is not impact. Context signals must not be promoted to operational claims without explicit official source support and operator approval.

---

## Draft AviaImpact Review Queue

Use `v_aviaimpact_draft_review_queue` in Supabase to see pending draft scores.

All rows in this view carry the disclaimer:
> *AviaImpact draft scores require operator review and are not FAA operational-delay claims.*

No row in this view is ready for external use until the operator has:
1. Read the `explanation` and `source_summary` for the row.
2. Verified the source data.
3. Explicitly set `operator_review_status = 'accepted'` and
   `public_release_allowed = true` in the `aviaimpact_draft_scores` table.
