# RUNWAY REFERENCE
# TravelCast AviatorGraf Prep — Static Runway Reference Data Model

**Phase B2 — Static Runway Reference**

---

## Two-Layer Architecture

The runway data model has two distinct layers. **They must not be confused.**

| Layer | Purpose | Source | Label |
|-------|---------|--------|-------|
| **Static runway reference** | Physical runway inventory: identifiers, headings, length, width, surface, endpoint coordinates, lighting, ILS availability | FAA NASR / OurAirports | `Static reference — FAA / OurAirports` |
| **Live operational runway** | Active arrival/departure runway config, AAR, flow control, closures | FAA/NAS, ATCSCC, NOTAM | `Current Operational Impact — FAA NAS / ATCSCC` |

**The static layer never overrides or substitutes for the live layer.**

A runway that appears in static reference may be closed, restricted, or temporarily reconfigured at any given time. Never claim a runway is "open," "active," or "in use" based on static reference data alone.

---

## What Static Runway Reference Covers

Static runway reference describes **physical inventory** only:

- Runway identifier / designator (e.g., 17C/35C)
- Base and reciprocal end IDs
- Length (feet)
- Width (feet)
- Surface type (ASPH, CONC, TURF, GRAVEL, etc.)
- True and magnetic headings (at time of survey)
- Threshold coordinates (lat/lon at time of survey)
- Displaced threshold distances (feet)
- Lighting type (HIRL, MIRL, LIRL, etc.)
- ILS availability and frequency (as of source date)

## What Static Runway Reference Does NOT Cover

- Active runway configuration
- Current arrival runway / departure runway
- AAR (airport arrival rate)
- Runway closures (NOTAMs, temporary closures)
- Arrival/departure flow assignments
- FAA traffic management initiatives tied to runway config
- Current pilot reports about runway conditions

---

## Source Hierarchy

| Priority | Source | Use |
|----------|--------|-----|
| 1 (authoritative) | FAA NASR / FAA AIS | Official aeronautical reference data. FAA publishes runway geometry and inventory on 28-day AIRAC cycles via the NASR subscription and FAA AIS portal. Use for production-grade runway reference. |
| 2 | OurAirports `runways.csv` | Open dataset derived from official sources. Suitable as a development baseline and cross-check. Free for reuse. Available at ourairports.com/data/. |
| 3 (cross-check only) | atis.info | Candidate discovery source. Not an official FAA data feed. Use only to cross-check designators or confirm data already sourced from FAA NASR / OurAirports. |
| 3 (cross-check only) | metar-taf.com/metar | Candidate discovery source. Not an official FAA data feed. Use only to cross-check designators or confirm data already sourced from FAA NASR / OurAirports. |

**atis.info and metar-taf.com/metar are not official data sources and must not be the sole basis for runway reference data entered into production tables.**

---

## Data Files

| File | Purpose |
|------|---------|
| `data/reference/travelcast_airport_runways.template.csv` | Headers-only template. Populate from FAA NASR / OurAirports before running the loader. |
| `data/reference/travelcast_airport_runways.csv` | Populated runway data file (create from template when ready). |

**Do not commit runway CSV files that contain invented data.**

---

## Database Objects

| Object | Type | Description |
|--------|------|-------------|
| `airport_runways` | Table | Static runway reference. One row per physical runway (both ends per row). |
| `v_airport_runway_context` | View | Runway rows joined to airport master for display context. Includes `source_label` and `static_runway_notice`. |

See `sql/08_airport_runway_reference.sql` for full schema.

---

## CSV Column Reference

| Column | Required | Type | Notes |
|--------|----------|------|-------|
| `airport_id` | Yes | text | Must match `airport_id` in airports table |
| `iata` | Yes | text | 3-letter IATA code (e.g., DFW) |
| `icao` | Yes | text | 4-letter ICAO code (e.g., KDFW) |
| `runway_id` | Yes | text | Composite primary key: `{ICAO}-{base}-{reciprocal}` e.g., `KDFW-17C-35C` |
| `base_end_id` | Yes | text | Low-number or primary end (e.g., 17C) |
| `reciprocal_end_id` | No | text | High-number or reciprocal end (e.g., 35C) |
| `length_ft` | No | integer | Runway length in feet |
| `width_ft` | No | integer | Runway width in feet |
| `surface_type` | No | text | ASPH, CONC, TURF, GRAVEL, etc. |
| `base_heading_true` | No | numeric | True heading (degrees) at base end |
| `base_heading_magnetic` | No | numeric | Magnetic heading at base end |
| `reciprocal_heading_true` | No | numeric | True heading at reciprocal end |
| `reciprocal_heading_magnetic` | No | numeric | Magnetic heading at reciprocal end |
| `base_threshold_lat` | No | numeric | Latitude of base end threshold |
| `base_threshold_lon` | No | numeric | Longitude of base end threshold |
| `reciprocal_threshold_lat` | No | numeric | Latitude of reciprocal end threshold |
| `reciprocal_threshold_lon` | No | numeric | Longitude of reciprocal end threshold |
| `base_displaced_threshold_ft` | No | integer | Feet from runway end to displaced threshold, base end |
| `reciprocal_displaced_threshold_ft` | No | integer | Feet from runway end to displaced threshold, reciprocal end |
| `lighting` | No | text | HIRL, MIRL, LIRL, ODALS, MALSR, ALSF-2, etc. |
| `base_ils_available` | No | boolean | true/false |
| `base_ils_frequency` | No | text | ILS frequency at base end (e.g., 110.3) |
| `reciprocal_ils_available` | No | boolean | true/false |
| `reciprocal_ils_frequency` | No | text | ILS frequency at reciprocal end |
| `source` | No | text | `faa_nasr`, `faa_ais`, `ourairports`. Do not use `atis.info` or `metar-taf.com`. |
| `source_date` | No | date | NASR cycle date or OurAirports export date (YYYY-MM-DD) |
| `notes` | No | text | Free text notes |

---

## How to Populate Runway Data

**Step 1 — Get official runway data**

Option A (authoritative): FAA NASR/AIS
- FAA AIS portal: `https://www.faa.gov/air_traffic/flight_info/aeronav/aero_data/`
- FAA NASR subscription: runway and airport geometry files
- Cycle date: 28-day AIRAC cycles; use the current or most recent cycle

Option B (development baseline): OurAirports
- Download `runways.csv` from `https://ourairports.com/data/`
- Filter by `airport_ident` matching your 71 ICAO codes
- Cross-check against FAA NASR before production use

**Step 2 — Populate the CSV**

Copy `data/reference/travelcast_airport_runways.template.csv` to `travelcast_airport_runways.csv` and fill in the data rows. Do not invent values.

**Step 3 — Dry-run validation**

```cmd
python scripts\load\load_airport_runways.py --dry-run
```

**Step 4 — Apply SQL migration**

Run `sql/08_airport_runway_reference.sql` in the Supabase SQL editor to create the `airport_runways` table and `v_airport_runway_context` view.

**Step 5 — Load to Supabase**

```cmd
python scripts\load\load_airport_runways.py
```

**Step 6 — Audit**

```cmd
python scripts\audit\audit_runway_reference.py
```

---

## On-Air Guardrails

**Allowed (from static reference):**
- "DFW has runways 17C/35C, 18L/36R, 13L/31R, and 13R/31L according to static runway reference."
- "SEA Runway 16C/34C is 11,900 feet according to FAA reference data."

**Not allowed (from static reference alone):**
- "Runway 17C is active for arrivals."
- "Runway 35C is currently closed."
- "The arrival rate is 44 operations per hour."
- "DFW is landing north today."

Live runway configuration and operational status must be sourced from FAA/NAS, ATCSCC, or official operational data.
