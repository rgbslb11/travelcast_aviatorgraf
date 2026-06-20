# ROUTECAST CORRIDOR GEOMETRY
# TravelCast AviatorGraf Prep — RouteCast Corridor Geometry Scaffold

**Phase C2 — RouteCast Corridor Geometry + Impact Styling**

---

## Purpose

Phase C2 builds the schema and seed scaffold for RouteCast aviation route corridor geometry. It provides:

- A structured corridor metadata table (`routecast_corridors`)
- Per-corridor waypoint tables with coordinate status tracking (`routecast_corridor_waypoints`)
- A computed geometry output table (`routecast_corridor_geometry`)
- Dashboard/map/export-ready views
- Geometry confidence labeling at every level

**This is a planning/display scaffold. RouteCast corridor geometry is NOT FAA operational delay truth. Empty state is better than invented geometry.**

---

## Top-50 Busiest Route Source File

The Top-50 busiest U.S. aviation route source file is a **static reference artifact** that identifies priority RouteCast corridors. It is used as:

- A list of corridor candidates to seed into `routecast_corridors`
- A ranking input for display prioritization

**It is NOT:**
- Live FAA delay data
- ATCSCC operational impact data
- Official routing data
- A source of delay forecasts or operational restrictions

The `route_rank_basis` field in `routecast_corridors` permanently records:
```
static_top_50_busiest_route_reference_not_delay_truth
```

This field is always populated and must not be removed or overwritten with operational claim language.

### Source File Location

Place the Top-50 source CSV at any of these paths:

```
data/reference/top_50_routes.csv
data/reference/top_50_busiest_routes.csv
data/reference/routecast_corridors.csv
data/reference/travelcast_top50_routes.csv
```

Or use:
```
python scripts/routecast/seed_routecast_corridors.py --source-csv PATH/TO/FILE.csv
```

---

## Tables

### `routecast_corridors`

One row per RouteCast aviation route corridor. Sourced from the Top-50 reference when available.

| Field | Purpose |
|-------|---------|
| `corridor_key` | Stable identifier (e.g. `DFW-JFK`) |
| `corridor_name` | Display name |
| `rank` | Source rank; not a delay priority rank |
| `origin_airport_iata` / `destination_airport_iata` | Endpoint airports |
| `primary_route_label` | FAA airway/route string when known |
| `route_rank_basis` | Always: `static_top_50_busiest_route_reference_not_delay_truth` |
| `geometry_confidence` | Current confidence level for associated geometry |
| `geometry_status` | Current status of geometry build |
| `source_file` | Name of source file used to seed this row |

### `routecast_corridor_waypoints`

Per-corridor waypoints parsed from the route label or waypoints field.

| Field | Purpose |
|-------|---------|
| `waypoint_label` | FAA fix/navaid identifier |
| `waypoint_order` | Sequence position within the corridor |
| `lat` / `lon` | Decimal degrees; null if unresolved |
| `coordinate_status` | `resolved` / `airport_lookup` / `unresolved` |
| `coordinate_source` | Which lookup provided coordinates |
| `is_route_endpoint` | true for origin/destination airports |

**Unresolved waypoints:** If a FAA fix/navaid label cannot be resolved to coordinates from the available source files, the lat/lon remain null and `coordinate_status = 'unresolved'`. The label is preserved in `routecast_corridor_geometry.unresolved_waypoints`.

### `routecast_corridor_geometry`

Computed geometry for each corridor.

| Field | Purpose |
|-------|---------|
| `geometry_geojson` | GeoJSON LineString; null if fewer than 2 points resolved |
| `geometry_method` | `resolved_waypoint_control_line` (only method in C2) |
| `geometry_confidence` | See confidence levels below |
| `geometry_status` | `geometry_built` / `no_geometry` / `needs_source_file` |
| `unresolved_waypoints` | Array of labels that could not be resolved |

---

## Geometry Confidence Levels

| Level | Meaning |
|-------|---------|
| `unvalidated` | Default; geometry has not been reviewed |
| `control_line_scaffold` | LineString from resolved waypoints; needs validation before operational use |
| `partially_resolved` | Geometry built but some waypoints were unresolved; may skip key fixes |
| `needs_source_file` | No geometry possible; source CSV not available |

All geometry produced by C2 has `geometry_confidence = 'control_line_scaffold'` or worse. No C2 geometry should be represented as precise FAA routing.

---

## Coordinate Sources

| Source | Priority | Notes |
|--------|----------|-------|
| FAA waypoint coordinates CSV | High | FAA NASR or equivalent; must be provided via `--waypoint-coordinates` |
| Project airport master CSV | Fallback | `travelcast_focus_airports.csv` — used for endpoint airports |
| Not resolved | None | Label preserved in `unresolved_waypoints`; no coordinates invented |

**Never invent coordinates for unresolved waypoints.** If a waypoint label cannot be matched to a known coordinate, it remains unresolved and its lat/lon stays null.

---

## Control-Line Limitation

The C2 geometry method (`resolved_waypoint_control_line`) builds a straight-line LineString connecting resolved waypoint coordinates in order. This is:

- **Not** a precise FAA airway routing
- **Not** a preferred MEA/MVA routing
- **Not** a cleared or filed flight-route representation
- **Not** an ATC-validated corridor path

It is a **planning scaffold** connecting known geographic points along a known route corridor. It should be visually distinguished from operational routing data using the `routecast_unvalidated` style.

---

## Unresolved Waypoint Handling

When waypoints cannot be resolved:

1. The waypoint row is preserved with `coordinate_status = 'unresolved'`
2. The waypoint label is stored in `routecast_corridor_geometry.unresolved_waypoints[]`
3. Geometry is built from remaining resolved points only
4. If fewer than 2 points resolve, no geometry is built (`geometry_status = 'no_geometry'`)
5. `geometry_confidence` is set to `partially_resolved` when some but not all waypoints resolve

Use the `v_routecast_geometry_audit` view to see unresolved waypoint counts per corridor:
```sql
select * from v_routecast_geometry_audit order by unresolved_waypoint_count desc;
```

---

## Dashboard / Export Views

| View | Purpose |
|------|---------|
| `v_routecast_corridor_geometry` | Corridor + geometry joined; all fields; geometry may be null |
| `v_routecast_corridor_map` | GeoJSON Feature per corridor (only corridors with geometry) |
| `v_routecast_geometry_audit` | Waypoint resolution counts and geometry status per corridor |
| `v_routecast_style_legend` | Style definitions for UI/graphics builders |

The `v_routecast_corridor_map` view embeds a `disclaimer` property in every GeoJSON Feature:

> `RouteCast corridor geometry is a planning/display scaffold and not FAA operational delay truth.`

---

## Data Flow

```
Top-50 route source CSV (data/reference/*.csv)
  ↓
scripts/routecast/seed_routecast_corridors.py
  ├── data/reference/faa_waypoint_coordinates.csv (optional — resolve fixes)
  ├── data/reference/travelcast_focus_airports.csv (endpoint airport coords)
  └── resolve waypoints → build LineString where ≥2 points resolve
  ↓
Supabase:
  routecast_corridors
  routecast_corridor_waypoints
  routecast_corridor_geometry
  ↓
v_routecast_corridor_geometry / v_routecast_corridor_map / v_routecast_geometry_audit
  ↓
Map layer / Dashboard / Exports
```

---

## What C2 Does NOT Do

- Does not produce FAA operational delay data
- Does not match corridors to live ATCSCC TMIs (Phase C3)
- Does not compute AviaImpact scores (Phase D2)
- Does not build RoadCast highway corridors (Phase D3+)
- Does not invent waypoint coordinates
- Does not snap to FAA airways without explicit airway data
- Does not claim flight reroutes, ground stops, or route restrictions
- Does not treat the Top-50 rank as a delay probability rank

---

## Validation Requirements

Before using C2 geometry in production on-air graphics:

1. Review `v_routecast_geometry_audit` for unresolved waypoints
2. Visually inspect corridors in map view against known aviation charts
3. Provide validated waypoint coordinate CSV (`--waypoint-coordinates`)
4. Re-run seed script to rebuild geometry with resolved coordinates
5. Confirm geometry visually represents a plausible great-circle corridor
6. Update `geometry_confidence` only when a qualified operator has reviewed the routing

Until then, display all corridors using the `routecast_unvalidated` style (dashed, low-opacity).
