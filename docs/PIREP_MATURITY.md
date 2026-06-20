# PIREP MATURITY
# TravelCast AviatorGraf Prep — Pilot Weather Report Data Model

**Phase B4 — Aviation Weather Maturity: PIREP Ingestion**

---

## What Is a PIREP?

A **Pilot Weather Report (PIREP)** is an observation of actual meteorological conditions reported by pilots in flight. PIREPs are coded as:

- **UA** — Routine pilot report
- **UUA** — Urgent pilot report (severe conditions observed)
- **AIREP** — Aircraft meteorological data relay (typically international)

PIREPs are **Aviation Weather Truth** in TravelCast: they represent real-time, observed in-flight conditions from pilots.

---

## DOCTRINE: What PIREPs Are and Are NOT

**PIREPs ARE:**
- Pilot-observed flight conditions (turbulence, icing, sky, visibility)
- Real-time observational data from the flight environment
- Source: AviationWeather.gov
- Source label: `Aviation Weather Truth — AviationWeather.gov`

**PIREPs ARE NOT:**
- FAA operational delay data
- Ground stop or GDP notifications
- Route closures or restrictions
- Delay minute estimates
- Airport arrival rate (AAR) advisories
- Official NAS status information

**Never imply or claim:**
- "PIREPs indicate delays at [airport]"
- "PIREP shows a ground stop"
- "Turbulence PIREPs indicate a ground delay program"
- Any FAA operational impact language sourced solely from PIREP data

Use the `pirep_notice` field in all product outputs: *"PIREPs are pilot-reported observations of actual conditions. They are not FAA operational delay data, delay forecasts, or route closure information."*

---

## Staleness Rules

| Rule | Value | Behavior |
|------|-------|---------|
| PIREP operational stale threshold | 2 hours | PIREPs older than 2 hours are flagged `is_operationally_stale = true` — conditions may no longer be present |
| PIREP fetch stale threshold | 8 hours | Data fetched 8 or more hours ago is flagged `is_fetch_stale = true` |
| View exclusion threshold | 6 hours | v_pireps_active excludes PIREPs observed more than 6 hours ago |

PIREPs represent observed conditions at a point in time and location. A 2-hour-old PIREP may still be useful for context but conditions may have changed. A 6-hour-old PIREP should not be used in operational on-air product.

**Stale data must not appear in on-air product without a freshness warning.**

---

## Geolocation Rules

| Rule | Behavior |
|------|---------|
| `is_geolocated = true` | `latitude` and `longitude` were provided by AviationWeather.gov in the source response |
| `is_geolocated = false` | No lat/lon in source; `latitude` and `longitude` are NULL |
| Do NOT infer coordinates | Location text (VOR/fix references, e.g., "40 NE of ORD") must not be converted to lat/lon unless the source provides them |

Do not attempt to resolve PIREP location text (e.g., "40NE ORD") into coordinates. The risk of error is high and violates data honesty rules. Store the raw location text in `location_text` as-is.

---

## Airport Association

PIREPs are associated to TravelCast airports by two methods:

| Method | When Used | `distance_nm` |
|--------|----------|---------------|
| `radius_match` | PIREP has source-provided lat/lon; within configured radius (default 50 NM) | Computed via Haversine formula |
| `fetch_target` | PIREP has no lat/lon; airport was in the fetch batch | NULL |

PIREPs associated as `fetch_target` are near the airport in that the report was retrieved by querying that airport's ICAO on AviationWeather.gov, but precise distance cannot be determined without lat/lon.

---

## Database Objects

| Object | Type | Description |
|--------|------|-------------|
| `pirep_reports` | Table | One row per unique PIREP (keyed by MD5 hash of raw text) |
| `pirep_airport_associations` | Table | PIREP → airport linkages (one PIREP may associate to multiple airports) |
| `v_pireps_active` | View | Non-stale PIREPs with freshness flags; source label; `pirep_notice` |
| `v_airport_pireps_active` | View | PIREPs joined to airport context for dashboard use |

See `sql/09_taf_pirep_maturity.sql` for full schema.

---

## Key Fields

### `pirep_reports`

| Field | Notes |
|-------|-------|
| `pirep_id` | `pirep-{12-char-hex}` from MD5 of raw PIREP text |
| `report_type` | `UA` (routine) / `UUA` (urgent) / `AIREP` |
| `raw_pirep` | Preserved raw PIREP text |
| `observed_at_utc` | Time of observation |
| `aircraft_type` | Aircraft type as reported by pilot |
| `altitude_ft` | Flight level in feet (FL280 → 28000 ft); null if not parseable |
| `latitude` / `longitude` | Source-provided only; null if not in API response |
| `is_geolocated` | true only if source provided lat/lon |
| `location_text` | Raw location reference from source |
| `turbulence_intensity` | NEG / LGT / LGT-MOD / MOD / MOD-SEV / SEV / EXTR |
| `icing_intensity` | NEG / TRC / LGT / MOD / HVY |
| `fetched_at_utc` | When data was fetched; used for stale computation |

### `pirep_airport_associations`

| Field | Notes |
|-------|-------|
| `pirep_id` | FK to `pirep_reports` |
| `airport_id` | FK to TravelCast airport |
| `distance_nm` | Haversine distance; null for `fetch_target` associations |
| `association_method` | `radius_match` / `fetch_target` / `manual` |

---

## Data Flow

```
AviationWeather.gov PIREP API
  https://aviationweather.gov/api/data/pirep?ids={ICAO_LIST}&format=json&age=3
  ↓
pull_pireps.py   → data/raw/pirep_raw.json
  ↓                → normalizes each PIREP
  ↓                → associates to airports (radius or fetch-target)
  ↓                → upserts pirep_reports + pirep_airport_associations
  ↓
Supabase: pirep_reports / pirep_airport_associations
  ↓
v_pireps_active / v_airport_pireps_active
  ↓
Frontend (hazards panel, airport detail) / Exports
```

---

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/pull/pull_pireps.py` | Fetch PIREPs; associate to airports; write to Supabase |
| `scripts/audit/audit_taf_pirep_maturity.py` | Audit doctrine, files, and compile |

### Usage

```cmd
python scripts\pull\pull_pireps.py --dry-run
python scripts\pull\pull_pireps.py
python scripts\pull\pull_pireps.py --limit 5
python scripts\pull\pull_pireps.py --radius 100    REM 100 NM association radius
```

---

## On-Air Guardrails

**Allowed (from PIREP data):**
- "Pilots report moderate turbulence between FL280 and FL320 in the KDFW area."
- "A UUA (urgent) pilot report near KORD indicates severe icing at FL180."
- "PIREPs near KJFK show IFR sky conditions reported at 14:30Z."

**Not allowed (from PIREP data alone):**
- "Turbulence PIREPs are causing delays at DFW."
- "Pilot reports indicate a ground stop."
- "PIREPs show [N] minute delays expected."
- "Arrival rates at ORD are reduced due to PIREP icing reports."

FAA operational impacts must be sourced from FAA NAS Status, ATCSCC advisories, or official operational data.

---

## UUA (Urgent PIREP) Handling

Urgent PIREPs (`report_type = 'UUA'`) indicate severe or extreme conditions observed in flight. In product:
- Flag UUA reports visually distinct from routine reports
- Include the raw `raw_pirep` text for context
- Do NOT claim that a UUA report indicates a ground stop, GDP, or FAA action unless that information comes from FAA/NAS or ATCSCC

A UUA PIREP describes what a pilot observed. It does not constitute an FAA traffic management action.
