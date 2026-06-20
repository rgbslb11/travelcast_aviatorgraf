# NWS CAP / WEA ONTOLOGY
# TravelCast AviatorGraf Prep — Public Weather Alert Data Model

**Phase C1 — NWS CAP / WEA Public Alert Ontology**

---

## What Is NWS CAP?

NWS **Common Alerting Protocol (CAP)** is the standard format for U.S. public weather alerts issued by the National Weather Service (NWS). CAP alerts are distributed via:

- **api.weather.gov** — official NWS public API (used by TravelCast)
- IPAWS / WEA — Wireless Emergency Alerts (sent to cell phones)
- NOAA Weather Radio
- Third-party aggregators

NWS CAP alerts are **Public Weather Alert Truth** in TravelCast: they represent the authoritative source for public weather hazard information.

---

## DOCTRINE: What NWS CAP Alerts Are and Are NOT

**NWS CAP alerts ARE:**
- Official public weather hazard notifications
- Authoritative source for warnings, watches, advisories, and statements
- Source: `api.weather.gov`
- Source label: `Public Weather Alert — NWS CAP`
- Useful for contextualizing weather conditions near airports, metro areas, and travel corridors

**NWS CAP alerts ARE NOT:**
- FAA operational delay data
- Ground stop (GS) notifications
- Ground delay program (GDP) notifications
- Airport arrival rate (AAR) advisories
- Route closure notifications
- Air Traffic Control advisories
- ATCSCC traffic management initiatives (TMIs)

**Never claim:**
- "NWS alert causes delays at [airport]"
- "Weather warning indicates a ground stop"
- "Alert shows GDP expected"
- Any FAA operational impact sourced solely from NWS CAP data

Use the `alert_notice` field in all product outputs:
> *"NWS public weather alerts indicate weather hazards. They are not FAA operational delay data, ground stops, ground delay programs, route closures, or AAR."*

---

## Alert Classifications

### Status

| Value | Meaning |
|-------|---------|
| `Actual` | Real alert — operational; stored and displayed |
| `Exercise` | Drill/exercise — not stored in production tables |
| `System` | System-generated test — not stored |
| `Test` | NWS internal test — not stored |
| `Draft` | Draft/pre-release — not stored |

Only `Actual` status alerts are stored in `public_weather_alerts`.

### Message Type

| Value | Meaning |
|-------|---------|
| `Alert` | New alert issuance |
| `Update` | Update to an existing alert |
| `Cancel` | Cancellation of a prior alert |
| `Ack` | Acknowledgment |
| `Error` | Error correction |

`Cancel` message types are excluded from `v_public_weather_alerts_dashboard`.

### Severity

| Value | Severity Rank |
|-------|--------------|
| `Extreme` | 4 — Extraordinary threat to life or property |
| `Severe` | 3 — Significant threat to life or property |
| `Moderate` | 2 — Possible threat |
| `Minor` | 1 — Minimal threat |
| `Unknown` | 0 — Undetermined |

### Urgency

| Value | Meaning |
|-------|---------|
| `Immediate` | Responsive action should be taken immediately |
| `Expected` | Responsive action should be taken soon (within next hour) |
| `Future` | Responsive action should be taken in near future |
| `Past` | Responsive action is no longer required |
| `Unknown` | Urgency not known |

### Certainty

| Value | Meaning |
|-------|---------|
| `Observed` | Determined to have occurred or to be ongoing |
| `Likely` | Likely (≥ 50% probability) |
| `Possible` | Possible but not likely (< 50%) |
| `Unlikely` | Not likely |
| `Unknown` | Certainty not known |

---

## Staleness and Expiry Rules

| Rule | Value | Behavior |
|------|-------|---------|
| Alert native expiry | `expires_at_utc` from NWS | Authoritative expiry; alerts are `is_expired = true` when `expires_at_utc < now()` |
| View exclusion | 1 hour past expiry | `v_public_alerts_active` excludes alerts expired more than 1 hour ago |
| Data freshness | 8 hour fetch stale | Data fetched 8 or more hours ago is flagged `is_stale = true` |
| Recommended refresh | 10–30 minutes | NWS alerts change frequently; production should refresh every 10–30 minutes |

The `is_expired` flag reflects the alert's own stated validity window.
The `is_stale` flag reflects whether the TravelCast data cache is current.
**Both flags must be surfaced in on-air product — stale or expired data must not be shown without a freshness warning.**

---

## Geometry and Spatial Coverage

NWS alerts carry either:

1. **Explicit polygon geometry** — GeoJSON Polygon or MultiPolygon describing the alert area exactly; stored in `geometry_json`; `has_geometry = true`
2. **Zone-based coverage** — NWS UGC zone codes (`geocode_ugc`) or FIPS county codes (`geocode_same`) with no explicit polygon; `has_geometry = false`

The `has_geometry` flag distinguishes these cases. Airport matching in Phase C1 uses geometry intersection only (high confidence). Zone-based matching is scaffolded but not yet implemented — see `AIRPORT_ALERT_MATCHING.md`.

If NWS provides no polygon geometry, store the alert as non-spatial/raw. **Do not invent polygon geometry.**

---

## Raw Payload Retention

The full raw NWS alert feature is preserved in `raw_cap_json` (jsonb). This allows:
- Audit and verification against the NWS source
- Future extraction of additional fields without re-fetching
- Debugging and backfill capability

`raw_cap_json` contains the complete GeoJSON Feature object as returned by the NWS API.

---

## Aviation-Context Alerts (`v_public_alerts_aviation_context`)

The `v_public_alerts_aviation_context` view filters active alerts to event types that create weather hazard context relevant to aviation operations:

- Tornado Warning / Watch
- Severe Thunderstorm Warning / Watch
- Winter Storm Warning / Watch / Advisory
- Blizzard Warning
- Ice Storm Warning
- Dense Fog Advisory / Warning
- High Wind Warning / Watch / Advisory
- Freezing Rain / Drizzle Advisory
- Dust Storm Warning
- Flash Flood Warning / Watch
- Air Quality Alert
- Special Weather Statement

These events may affect ceiling, visibility, wind, or surface conditions at or near TravelCast airports. **They do not constitute FAA operational data.**

---

## Database Objects

| Object | Type | Description |
|--------|------|-------------|
| `public_weather_alerts` | Table | One row per NWS CAP alert (upsert on `alert_id` URN) |
| `airport_public_alert_matches` | Table | Alert × airport linkages by match method and confidence |
| `v_public_weather_alerts_dashboard` | View | Non-expired, Actual alerts with freshness flags; `alert_notice`; `source_label` |
| `v_airport_public_alert_context` | View | Active alerts joined to airport context; `match_confidence` |
| `v_public_alert_source_health` | View | Source health: fetch time, active count, staleness, freshness label |
| `v_public_alerts_aviation_context` | View | Alerts filtered to aviation-relevant event types |

See `sql/10_public_alert_ontology.sql` for full schema.

---

## Data Flow

```
api.weather.gov/alerts/active
  ↓
pull_nws_alerts.py   → data/raw/nws_alerts_raw.json
  ↓                    → data/raw/nws_alerts_parsed.json
  ↓                    → parse each alert
  ↓                    → geometry intersection with 71 airports
  ↓                    → upserts public_weather_alerts + airport_public_alert_matches
  ↓
Supabase: public_weather_alerts / airport_public_alert_matches
  ↓
v_public_weather_alerts_dashboard / v_airport_public_alert_context
  / v_public_alert_source_health / v_public_alerts_aviation_context
  ↓
Frontend (hazards panel, airport detail, alert context) / Exports
```

---

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/pull/pull_nws_alerts.py` | Fetch alerts; match to airports; write to Supabase |
| `scripts/audit/audit_public_alert_ontology.py` | Audit doctrine, files, compile, labels |

### Usage

```cmd
python scripts\pull\pull_nws_alerts.py --dry-run
python scripts\pull\pull_nws_alerts.py
python scripts\pull\pull_nws_alerts.py --limit 20
python scripts\pull\pull_nws_alerts.py --area TX,LA,GA,FL,NY
```
