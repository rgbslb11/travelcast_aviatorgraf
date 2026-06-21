# Aviation Hazard Corridor Matching — Phase C3

## Purpose

Phase C3 builds context associations between RouteCast aviation route corridors
and available weather hazard / ATCSCC advisory context. These associations are
**context scaffolds only** — not delay claims, impact scores, or operational
restriction claims.

---

## RouteCast Corridor Source Inputs

Corridors are loaded from:

1. **Supabase `routecast_corridors` table** (primary) — seeded by
   `seed_routecast_corridors.py` from the Top-50 reference CSV.
2. **`data/reference/routecast_top_50_busiest_aviation_routes_v0_1.csv`** (fallback)
   — used when Supabase is unavailable.

Corridor fields used for matching:
- `origin_airport_iata` / `origin_airport_icao`
- `destination_airport_iata` / `destination_airport_icao`
- `primary_route_label` (airway string)
- `waypoints` (pipe-delimited fix labels)

RouteCast corridor geometry is a **planning/display scaffold only**.
Not FAA operational delay truth. Not ATC restriction truth.

---

## ATCSCC Advisory Matching

Advisory context is loaded from `data/raw/atcscc_c3_advisories.json`
(written by `pull_atcscc_advisories.py`).

Match rows are written to `routecast_corridor_atcscc_matches`.

ATCSCC advisories are **FAA operational context only** — not route impact scores.
Match rows describe that an advisory *mentions* airports or fixes associated with
a corridor. They do NOT claim the corridor is delayed, restricted, or rerouted.

### ATCSCC match types

| match_type | Description |
|---|---|
| `airport_overlap` | Corridor endpoint airport appears in advisory `affected_airports`. |
| `fix_overlap` | Corridor waypoint / fix appears in advisory `mentioned_fix_labels`. |
| `route_label_overlap` | Corridor route label terms appear in advisory `mentioned_routes`. |
| `facility_text_match` | ARTCC facility in advisory text; no direct airport overlap. |

---

## Public Alert / Aviation Hazard Context Matching

Hazard context is loaded from:
- `data/raw/nws_alerts_parsed.json` — NWS CAP public alert context.
- `data/raw/aviation_hazards.json` — AviationWeather.gov SIGMET/AIRMET/CWA context.

Match rows are written to `routecast_corridor_hazard_context_matches`.

**NWS CAP alerts are Public Weather Alert Truth — NOT FAA operational delay truth.**
**AviationWeather.gov hazards are Aviation Weather Truth — NOT FAA operational delay truth.**
Weather hazard context near a corridor is **not** a delay claim.

### Hazard match types

| match_type | Description |
|---|---|
| `airport_overlap` | Corridor airport appears in alert area description. |
| `geometry_intersection_scaffold` | Placeholder for future geometry intersection. |
| `text_area_match` | Broad area text match (low confidence only). |

---

## Match Confidence Levels

| match_confidence | Meaning | When used |
|---|---|---|
| `high_geometry_intersection` | Geometry intersection confirmed. | NOT used in C3 initial scaffold. Reserved for future implementation. |
| `medium_airport_or_fix_overlap` | Corridor airports or fixes explicitly appear in advisory / hazard text. | Primary C3 confidence level. |
| `low_text_context` | Broad regional or facility text match. | Only written with `--include-low-confidence`. |
| `unmatched` | No safe match found. | Implicit when no row is produced. |

**`high_geometry_intersection` is reserved and must NOT be applied unless a verified
geometry intersection implementation is in place and confirmed.** C3 does not implement
geometry intersection — that is a future path.

---

## Operator Review Status

All system-generated match rows have `operator_review_status = 'draft'`.

Allowed values:
- `draft` — system-generated, not yet reviewed.
- `reviewed` — operator has examined but not decided.
- `accepted` — operator confirms the context association is valid.
- `rejected` — operator finds the association incorrect or unhelpful.

No match row may be promoted to a public-facing output until an operator
has reviewed and accepted it.

---

## Accepted Phrasing

When referencing match context in any output:

- "ATCSCC advisory context mentions [airport/facility]."
- "This corridor's endpoint airports appear in an active ATCSCC advisory."
- "NWS public alert context is present near this corridor's endpoints."
- "Weather hazard context (NWS / AviationWeather) is present near this corridor."
- "Source: FAA ATCSCC operational advisory." (for ATCSCC context)
- "Source: Public Weather Alert — NWS CAP." (for NWS context)
- "Source: Aviation Weather Truth — AviationWeather.gov." (for SIGMET/AIRMET/CWA)

---

## Prohibited Phrasing

The following phrases must NOT appear in any C3 output or downstream consumer:

- "[corridor] is delayed due to [weather / alert]."
- "[alert] causes FAA delay on [corridor]."
- "Route [X] is restricted / closed."
- "Automatic AviaImpact score assigned."
- "Route impact: [score / color]."
- Any claim of delay minutes, ground stop, or GDP derived from weather context.
- Any claim of delay minutes, ground stop, or GDP derived from RouteCast geometry.

---

## Future Extension Path to D1/D2

C3 match scaffolds are **inputs** for future phases, not outputs.

- **D1 Shared Impact Scoring**: not built in C3. Requires separate design approval.
- **D2 AviaImpact**: not built in C3. Requires D1 and operator review.
- C3 match rows carry `operator_review_status = 'draft'` to prevent premature use.

No scoring yet. Empty state is better than invented data.

---

## No Scoring

C3 does not produce:
- Delay scores
- Impact colors derived from context matches
- AviaImpact scores
- RoadCast outputs

Scoring is a future phase (D1/D2) that requires explicit design approval,
operator review, and source doctrine validation.
