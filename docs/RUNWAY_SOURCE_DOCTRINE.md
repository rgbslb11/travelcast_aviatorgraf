# RUNWAY SOURCE DOCTRINE
# TravelCast AviatorGraf Prep — Runway Data Source Rules

**Phase B2 — Static Runway Reference**

---

## Core Rule

Static runway reference and live runway operations are **separate source lanes**. They must never be mixed in product output or broadcast copy.

---

## Static Runway Reference Sources

### Tier 1 — Authoritative (Preferred for Production)

**FAA NASR / FAA AIS**
- What it is: The official U.S. aeronautical data authority. FAA publishes runway geometry, airport reference data, and aeronautical charts on 28-day AIRAC cycles via the National Airspace System Resources (NASR) subscription and the Aeronautical Information Services (AIS) portal.
- How to get it: FAA AIS at `https://www.faa.gov/air_traffic/flight_info/aeronav/aero_data/` or NASR subscription.
- When to use: Production runway reference data. Use for official IATA/ICAO runway identifiers, lengths, headings, threshold coordinates, lighting, and ILS availability.
- `source` field value: `faa_nasr` or `faa_ais`

### Tier 2 — Development Baseline

**OurAirports**
- What it is: An open airport and runway dataset maintained by contributors and partially derived from official sources including FAA data. Available at `https://ourairports.com/data/`. Distributed under the Creative Commons Public Domain Dedication.
- How to get it: Download `runways.csv` and `airports.csv` from `https://ourairports.com/data/`.
- When to use: Development baseline, rapid prototyping, or cross-checking against FAA NASR. Verify against FAA NASR before production use.
- `source` field value: `ourairports`

---

## Candidate Cross-Check / Discovery Sources

These sources are documented here as cross-check and discovery tools only. They are **not official data sources** and must not be the sole basis for runway data loaded into the `airport_runways` table.

**atis.info**
- What it is: A third-party website displaying ATIS/D-ATIS, METAR, TAF, NOTAM, and runway information for airports. Not an official FAA data feed.
- Allowed use: Cross-check runway designators or ILS frequencies against data already sourced from FAA NASR or OurAirports.
- Not allowed: Using it as the primary source for `airport_runways` data rows.
- Do not use `atis.info` as the `source` field value on data rows.

**metar-taf.com/metar**
- What it is: A third-party weather and airport information website displaying METAR, TAF, and runway data. Not an official FAA data feed.
- Allowed use: Cross-check runway designators against data already sourced from FAA NASR or OurAirports.
- Not allowed: Using it as the primary source for `airport_runways` data rows.
- Do not use `metar-taf.com` as the `source` field value on data rows.

---

## Live Operational Runway Sources

Live runway configuration and operational status are out of scope for the static runway reference table. Those are covered by:

| Source | Data | Label |
|--------|------|-------|
| FAA NAS Status | Active runway configuration, AAR, delays | `Current Operational Impact — FAA NAS / ATCSCC` |
| ATCSCC advisories | Traffic management initiatives, flow control, runway usage | `Current Operational Impact — FAA NAS / ATCSCC` |
| NOTAM / airport official sources | Temporary runway closures, NOTAM-based restrictions | Official operational source |

---

## Source Field Values

The `source` column in `airport_runways` must be one of these values:

| Value | Meaning |
|-------|---------|
| `faa_nasr` | FAA NASR subscription data |
| `faa_ais` | FAA AIS portal data |
| `ourairports` | OurAirports runways.csv |
| `template` | Placeholder — row not yet populated from an official source |

**`template` rows must not be loaded to Supabase production tables.** The `source` field must be updated to an official source before loading.

The `audit_runway_reference.py` script will FAIL on data rows with `source = template`, `atis.info`, `metar-taf.com`, or similar non-official values.

---

## Broadcast Guardrails

The `v_airport_runway_context` view includes:

- `source_label`: `"Static reference — FAA / OurAirports"`
- `static_runway_notice`: `"Static runway reference describes physical runway inventory only. Active runway configuration and operational use must be sourced from FAA/NAS, ATCSCC, or official operational sources."`

These fields must appear in any product card or export package that displays static runway data.

---

## Anti-Hallucination Rules

- Do not invent runway identifiers, headings, lengths, or coordinates.
- Do not claim a runway is open, active, or in use based on static reference.
- Do not claim a runway is closed based on static reference alone.
- Do not claim ILS is available unless sourced from FAA NASR or OurAirports and verified against current NOTAM status.
- Do not use static runway headings as current magnetic variation without checking for updates.
- Empty state (no static runway data loaded) is always better than invented data.
