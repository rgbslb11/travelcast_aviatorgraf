# ATCSCC Playbook Ontology — Phase C3

## Purpose

The ATCSCC playbook ontology provides a structured framework for classifying
FAA ATCSCC advisory text into operational categories. It exists to enable
RouteCast corridor context matching without inventing operational claims.

The ontology is a classification scaffold — not a source of operational data.
It does NOT replace or supplement real-time FAA advisory pulls.

---

## Advisory Storage Model

The `atcscc_advisories` table stores one row per FAA ATCSCC advisory fetched
and parsed. Each row:

- Preserves the full `raw_text` of the source advisory.
- Preserves `raw_payload` (JSON or structured parse) when available.
- Records `source_truth_lane = 'faa_atcscc_operational_truth'` on every row.
- Extracts fields **conservatively** from explicit advisory language only.
- Never invents field values. Never infers from weather context.

### Conservative field extraction rules

| Field | Extraction rule |
|---|---|
| `advisory_type` | Only set when advisory text **explicitly** uses the term (GDP, GS, AFP, MIT, reroute). |
| `affected_airports` | Only airport codes **explicitly mentioned** in advisory text. |
| `affected_facilities` | Only ARTCC / facility codes **explicitly mentioned** in advisory text. |
| `traffic_management_terms` | Only terms that appear **verbatim** in advisory text. |
| `weather_terms` | Only terms that appear **verbatim** in advisory text. |
| `parsed_summary` | First meaningful line of advisory text — not augmented or rewritten. |

Fields are never derived from NWS forecast context, RouteCast geometry,
or any non-advisory source.

---

## Pattern Definitions vs. Real Advisories

The `atcscc_playbook_patterns` table contains **static pattern definitions**.
These are:

- General concept templates (e.g. `ground_delay_program_context`).
- NOT real ATCSCC advisories.
- NOT operational data.
- Seeded once at migration time.
- Identified by `source_truth_lane = 'faa_atcscc_operational_context_pattern'`.

Playbook patterns define:
- `trigger_terms` — terms in advisory text that suggest this pattern applies.
- `allowed_output_language` — what C3 context output may say when matched.
- `prohibited_output_language` — what C3 must NOT say without live FAA data.

The `prohibited_output_language` field on each pattern is doctrine-in-schema.
Before producing any user-facing output based on a pattern match, this field
must be checked and respected.

### Seeded pattern categories

| pattern_key | operational_category |
|---|---|
| `ground_delay_program_context` | GDP |
| `ground_stop_context` | GS |
| `airspace_flow_program_context` | AFP |
| `reroute_advisory_context` | reroute |
| `miles_in_trail_context` | MIT |
| `weather_avoidance_context` | weather_avoidance |
| `staffing_trigger_context` | staffing |
| `runway_or_airport_constraint_context` | runway_constraint |

---

## Source Truth Lane

Every advisory row carries `source_truth_lane = 'faa_atcscc_operational_truth'`.

This lane is:
- The highest-priority operational truth source.
- The only source that may describe current ATC operational impact.
- Never substituted by NWS, RouteCast, or weather-hazard sources.

Pattern rows carry `source_truth_lane = 'faa_atcscc_operational_context_pattern'`
to distinguish them from real advisory data.

---

## Active / Stale Handling

- `is_active = true` on all newly ingested rows.
- `is_stale = true` when no refresh has occurred within the expected cadence.
- Advisory expiry is set by the source, not by TravelCast inference.
- Stale advisories should be flagged for operator review before any output use.

---

## Prohibited Claims

C3 and any downstream consumer of this ontology must NOT:

- Claim a public alert causes FAA delay.
- Claim route geometry causes delay.
- Produce automatic AviaImpact scores.
- Produce RoadCast output.
- Invent advisories, restrictions, ground stops, or route closures.
- Claim a GDP, GS, or AFP is active without explicit live advisory text.
- Derive delay from NWS forecast or RouteCast corridor geometry.
- Produce delay minutes or arrival rate claims from advisory context alone.

---

## What C3 Does Not Do

- C3 is not delay truth and does not produce delay claims.
- C3 has no impact scoring of any kind.
- C3 does not produce AviaImpact (Phase D2) output.
- C3 does not produce RoadCast (Phases D3–D5) output.
- C3 does not claim delays — it stores and classifies FAA advisory context.
- C3 does not derive operational facts from weather alerts or corridor geometry.
- C3 corridor × advisory matches are context scaffolds — not operational claims.

Empty state is better than invented data.
