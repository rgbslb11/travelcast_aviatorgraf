# TAF TIMELINE
# TravelCast AviatorGraf Prep — TAF Forecast Period Data Model

**Phase B3 — Aviation Weather Maturity: TAF Timeline**

---

## What Is a TAF?

A **Terminal Aerodrome Forecast (TAF)** is an official aviation weather forecast issued by the National Weather Service (NWS) for specific airports. TAFs are the authoritative aviation forecast for surface weather conditions at an aerodrome.

TAFs are **Aviation Weather Truth** in TravelCast: they represent the best available official forecast of surface weather affecting flight operations at a specific airport.

---

## DOCTRINE: What TAF Is and Is NOT

**TAF IS:**
- Official aviation weather forecast
- Source: AviationWeather.gov / NWS
- Source label: `Aviation Weather Truth — AviationWeather.gov`
- Authoritative for forecast weather conditions at the aerodrome

**TAF IS NOT:**
- An FAA operational delay forecast
- A ground stop notification
- A ground delay program (GDP) prediction
- A route closure or en-route delay forecast
- An airport arrival rate (AAR) forecast
- An official capacity or flow-control advisory

**Never imply or claim:**
- "TAF predicts delays at [airport]"
- "TAF indicates a ground stop"
- "According to the TAF, expect [N] minute delays"
- Any operational impact language sourced solely from TAF conditions

Use the `taf_notice` field in all product outputs: *"TAF is aviation forecast weather. It does not predict FAA operational delays, ground stops, ground delay programs, route closures, or AAR."*

---

## Forecast Group Types

| Group Type | Meaning |
|------------|---------|
| `BASE` | Initial forecast period (no change group) |
| `FM` | From — permanent change beginning at `valid_from_utc` |
| `TEMPO` | Temporary — fluctuating conditions lasting < 1 hour at a time, valid within window |
| `PROB` | Probability — conditions expected with stated probability (PROB30 or PROB40) |
| `BECMG` | Becoming — gradual change completing by `valid_to_utc` |

---

## Staleness Rules

| Rule | Value | Behavior |
|------|-------|---------|
| TAF data stale threshold | 8 hours | Data fetched 8 or more hours ago is flagged `is_stale = true` in views |
| TAF period expired | — | Periods where `valid_to_utc < now()` are flagged `is_expired = true` |
| Cache refresh recommendation | Before each pull cycle | Run `pull_aviationweather_metar_taf.py` before `pull_taf_timeline.py` |

**Stale data must not appear in on-air product without a freshness warning.**

---

## Implied Flight Category

The `flight_category_implied` field is computed from `ceiling_ft` and `visibility_sm` using standard FAA thresholds:

| Category | Ceiling | Visibility |
|----------|---------|------------|
| LIFR | < 500 ft | < 1 SM |
| IFR | 500–999 ft | 1–2 SM |
| MVFR | 1000–3000 ft | 3–5 SM |
| VFR | > 3000 ft | > 5 SM |

This is an **implication from source conditions** — not a certified FAA flight category determination. The field is always labeled `flight_category_implied`, not `flight_category`. It may not match official ATIS or NWS MOS categories.

Do not present `flight_category_implied` as an official category without qualification.

---

## Database Objects

| Object | Type | Description |
|--------|------|-------------|
| `taf_forecasts` | Table | One row per TAF bulletin (per airport, per issue time) |
| `taf_forecast_periods` | Table | One row per forecast group within a TAF |
| `v_taf_timeline_current` | View | Non-expired periods with freshness flags; source label; `taf_notice` |
| `v_airport_taf_periods_active` | View | Periods joined to airport context for dashboard use |

See `sql/09_taf_pirep_maturity.sql` for full schema.

---

## Key Fields

### `taf_forecasts`

| Field | Notes |
|-------|-------|
| `taf_id` | `{ICAO}-{YYYYMMDD}-{HHMM}`, e.g. `KATL-20260620-0958` |
| `issue_time_utc` | When the TAF was issued |
| `valid_from_utc` | Start of overall TAF valid window |
| `valid_to_utc` | End of overall TAF valid window |
| `raw_taf` | Preserved raw TAF text |
| `fetched_at_utc` | When data was fetched; used for stale computation |

### `taf_forecast_periods`

| Field | Notes |
|-------|-------|
| `period_id` | `{taf_id}-{seq:02d}`, e.g. `KATL-20260620-0958-00` |
| `group_type` | BASE / FM / TEMPO / PROB / BECMG |
| `probability` | Integer (30 or 40) for PROB groups; null otherwise |
| `ceiling_ft` | Lowest BKN or OVC layer in feet; null if no ceiling |
| `flight_category_implied` | VFR / MVFR / IFR / LIFR (implication from source; not certified) |
| `conditions_text` | Concise summary from source fields; no added interpretation |
| `raw_period_json` | Full raw forecast group JSON preserved from source |

---

## Data Flow

```
AviationWeather.gov TAF API
  ↓
pull_aviationweather_metar_taf.py  → data/raw/taf_raw.json
  ↓
pull_taf_timeline.py               → reads taf_raw.json
  ↓                                  → parses fcsts[] into periods
  ↓                                  → upserts taf_forecasts + taf_forecast_periods
  ↓
Supabase: taf_forecasts / taf_forecast_periods
  ↓
v_taf_timeline_current / v_airport_taf_periods_active
  ↓
Frontend (dashboard detail panel) / Exports
```

`pull_taf_timeline.py` reads from the existing `taf_raw.json` cache to avoid redundant API calls. Run `pull_aviationweather_metar_taf.py` first, or use `--fetch` to force a fresh pull.

---

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/pull/pull_taf_timeline.py` | Parse TAF periods; write to Supabase |
| `scripts/audit/audit_taf_pirep_maturity.py` | Audit doctrine, files, and compile |

### Usage

```cmd
python scripts\pull\pull_aviationweather_metar_taf.py
python scripts\pull\pull_taf_timeline.py --dry-run
python scripts\pull\pull_taf_timeline.py
python scripts\pull\pull_taf_timeline.py --limit 5
python scripts\pull\pull_taf_timeline.py --fetch     REM re-fetch from AviationWeather.gov
```

---

## On-Air Guardrails

**Allowed (from TAF data):**
- "The TAF for JFK indicates a period of IFR conditions from 18Z to 22Z with ceilings below 1,000 feet and visibility under 2 miles."
- "A TEMPO group in the DFW TAF shows thunderstorm probability between 14Z and 17Z."
- "Current TAF for ORD shows VFR conditions through the morning hours."

**Not allowed (from TAF data alone):**
- "JFK expects delays due to the TAF."
- "TAF indicates a ground stop at DFW."
- "Expect [N] minute delays based on the TAF forecast."
- "The TAF shows a ground delay program in effect."
- "Arrival rates will drop to [N] based on the TAF."

FAA operational impacts must be sourced from FAA NAS Status, ATCSCC advisories, or official operational data.
