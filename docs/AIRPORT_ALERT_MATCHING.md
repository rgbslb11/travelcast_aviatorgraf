# AIRPORT ALERT MATCHING
# TravelCast AviatorGraf Prep — NWS Alert to Airport Association

**Phase C1 — NWS CAP / WEA Public Alert Ontology**

---

## Purpose

Airport alert matching links NWS public weather alerts to TravelCast focus airports when geographic evidence safely supports the association. This allows the dashboard and exports to show weather hazard context for specific airports.

**Critical limitation:** An association indicates *weather hazard context near or over an airport* only. It does NOT indicate FAA operational delays, ground stops, ground delay programs, or any change to airport operational status.

---

## Match Methods

### 1. `geometry_intersection` — High Confidence

When an NWS alert contains explicit polygon geometry (GeoJSON Polygon or MultiPolygon) and the airport's lat/lon falls inside that polygon, the match is recorded as `geometry_intersection` with `match_confidence = 'high'`.

**Algorithm:** Ray-casting point-in-polygon test against the alert polygon's outer ring.  
**Pre-filter:** Bounding box check applied before the full ray-cast to skip alerts geographically far from the airport.  
**Geometry type support:** Polygon and MultiPolygon (outer ring only; holes not subtracted).

```
IF alert.has_geometry = true
AND airport.lat/lon is inside alert.geometry_json polygon:
  → association with match_method = 'geometry_intersection'
              match_confidence = 'high'
              distance_km = null (point-inside; not edge-distance)
```

### 2. `zone_text_match` — Medium Confidence (Scaffold Only — Phase C1)

NWS alerts that use zone-based coverage rather than explicit polygons carry UGC zone codes (e.g., `TXZ105`) in `geocode_ugc`. Matching airport locations to NWS zones requires a zone→airport lookup table mapping UGC codes to airport ids.

This matching method is **scaffolded in the schema** but not implemented in Phase C1. The `match_method = 'zone_text_match'` and `match_confidence = 'medium'` values are reserved for future implementation.

### 3. `area_text_match` — Low Confidence (Scaffold Only)

Heuristic matching by checking whether the alert's `area_desc` text contains state/city references associated with an airport. This is low confidence and not implemented in Phase C1. Do not use this method for production on-air claims.

---

## What Is NOT Implemented in Phase C1

- Zone-to-airport lookup table (UGC zone → airport mapping)
- Radius-based "nearby alert" association (alert polygon centroid within N km of airport)
- Multi-layer zone hierarchy (state zone → county zone → point)
- RouteCast corridor matching (Phase C future)

---

## `airport_public_alert_matches` Table

| Field | Meaning |
|-------|---------|
| `alert_id` | FK to `public_weather_alerts` |
| `airport_id` | FK to TravelCast airport |
| `match_method` | `geometry_intersection` / `zone_text_match` / `area_text_match` |
| `match_confidence` | `high` / `medium` / `low` |
| `distance_km` | Distance to nearest polygon edge (null for point-inside or non-geometry) |
| `associated_at_utc` | When association was computed |

A single alert may be associated to multiple airports if its polygon covers multiple airport locations. A single airport may have multiple active alert associations if several alerts are in effect.

---

## Not FAA Operational Data

Every association record and every view built on `airport_public_alert_matches` carries the `alert_notice`:

> *"NWS public weather alerts indicate weather hazards. They are not FAA operational delay data, ground stops, ground delay programs, route closures, or AAR."*

**Allowed in product output:**
- "A Winter Storm Warning is in effect over [airport] as of [time]."
- "Weather alert context: [event_type] near [airport]."
- "Public hazard: [headline] — see NWS for details."

**Not allowed in product output:**
- "[Airport] has a ground stop due to the alert."
- "NWS alert causes [N] minute delays at [airport]."
- "GDP expected based on Winter Storm Warning."
- "Alert confirms FAA delay at [airport]."

---

## Airport Coverage

Matching is applied to all 71 TravelCast focus airports with valid lat/lon coordinates. Airports without lat/lon in the Supabase `airports` table will not be matched. As of Phase C1, all 71 airports have coordinates in the focus airport CSV.

---

## Future Matching Phases

| Phase | Feature | Method |
|-------|---------|--------|
| C2+ | UGC zone → airport lookup | `zone_text_match` (medium confidence) |
| C2+ | Alert polygon buffer / nearby match | Extended radius around polygon |
| D+ | RouteCast corridor matching | Alert polygon × route corridor intersection |
| D+ | RoadCast highway corridor matching | Alert polygon × highway corridor intersection |

---

## Data Flow for Matching

```
pull_nws_alerts.py:

For each NWS alert:
  IF has_geometry:
    FOR each TravelCast airport with lat/lon:
      BBOX pre-filter → if outside, skip
      Ray-cast point-in-polygon test
      IF inside:
        INSERT airport_public_alert_matches(
          alert_id, airport_id, iata, icao,
          match_method='geometry_intersection',
          match_confidence='high',
          distance_km=NULL
        )
  ELSE:
    No association created (zone matching not yet implemented)
```

---

## On-Air Guardrails Summary

| What You Know | What You Can Say | What You Cannot Say |
|--------------|-----------------|-------------------|
| Airport is inside alert polygon | "Weather alert near/over [airport]" | "Delays at [airport] due to alert" |
| Alert severity = Extreme | "Extreme weather hazard in effect near [airport]" | "Ground stop at [airport]" |
| Alert type = Dense Fog Advisory | "Dense Fog Advisory near [airport]" | "IFR conditions confirmed at [airport]" |
| Multiple alerts over airport | "Multiple weather advisories in effect near [airport]" | "Airport is closed" |

For confirmed IFR conditions → use AviationWeather.gov METAR/TAF (Aviation Weather Truth).  
For confirmed delays/ground stops → use FAA NAS / ATCSCC (Current Operational Impact).
