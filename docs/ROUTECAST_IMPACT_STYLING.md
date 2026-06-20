# ROUTECAST IMPACT STYLING
# TravelCast AviatorGraf Prep — RouteCast Corridor Style Definitions

**Phase C2 — RouteCast Corridor Geometry + Impact Styling**

---

## Purpose

This document defines the visual style system for RouteCast corridor display. Styles control how corridors appear on maps, dashboards, and graphics packages.

**Critical distinction: Styles are NOT impact scores.**

A corridor's visual style indicates a display context or confidence state. Styles are not FAA operational delay data and not delay truth. The Top-50 route ranking is not delay truth and not an operational status indicator.

---

## Phase C2 Default Styles

The following 5 styles are seeded into `routecast_corridor_styles` by `sql/11_routecast_corridor_geometry.sql`:

| Style Key | Label | Color | Dash | Use Case |
|-----------|-------|-------|------|----------|
| `routecast_default` | Default Corridor | `#4A90D9` | Solid | Standard display with no context assigned |
| `routecast_selected` | Selected / Highlighted | `#FF8C00` | Solid | User-selected or graphics-highlighted corridor |
| `routecast_watch_context` | Watch-Context Corridor | `#E8A000` | Solid | Future: monitoring context (not operational status) |
| `routecast_unvalidated` | Unvalidated Geometry | `#9B9B9B` | `6,4` | Geometry not yet validated; dashed to signal low confidence |
| `routecast_public_alert_context` | Public Alert Context | `#C0392B` | `4,3` | NWS public weather alert overlaps corridor — context only |

---

## Style vs. Impact Score

| Concept | Style (C2) | Impact Score (Phase D2, future) |
|---------|------------|----------------------------------|
| What it is | Visual display rule | Computed operational context |
| Source | Static definition | Live data integration |
| Claim | "Display this corridor this way" | "This corridor has measured weather/operational context" |
| Operational truth | No | No — still not FAA truth |
| FAA truth | Never | Never |

**Phase C2 does not have impact scores.** Impact scores are deferred to Phase D1 (shared impact scoring) and Phase D2 (AviaImpact product).

---

## Public Alert Context Style

The `routecast_public_alert_context` style (Phase C2 placeholder) is reserved for future use when a NWS public weather alert polygon (from Phase C1) overlaps a corridor.

**When a corridor is styled `routecast_public_alert_context`:**

- It indicates a NWS public weather alert is present near or over the corridor
- It does NOT indicate FAA operational delays
- It does NOT indicate ground stops, GDPs, route closures, or ATC restrictions
- It does NOT indicate confirmed flight impacts

**Allowed on-air language:**
- "A weather advisory is in effect along the [corridor] corridor."
- "NWS has issued a Dense Fog Advisory along the Dallas–New York corridor area."

**Not allowed:**
- "Delays expected on the DFW-JFK corridor due to the alert."
- "Ground stop possible on DFW-JFK based on weather alert."

---

## Unvalidated Geometry Style

All C2 corridors should default to `routecast_unvalidated` until the geometry has been reviewed and promoted. The dashed, low-opacity display signals that the corridor line is a planning scaffold, not a precise routing.

Promotion to `routecast_default` should only occur after:
1. Waypoint resolution is complete (no unresolved waypoints, or known gaps accepted)
2. Visual review against aviation charts
3. Operator sign-off on corridor path accuracy

---

## Top-50 Rank Is Not a Delay Truth

The Top-50 busiest route ranking controls display order and selection priority in RouteCast. It does NOT:

- Indicate which corridors are currently experiencing delays
- Weight corridors by operational impact level
- Predict which corridors will have future delays
- Provide FAA operational impact information

**Do not label lower-rank corridors as "less impacted" or higher-rank corridors as "more impacted."** Rank reflects historical passenger volume, not current operational status.

---

## Future Extension Path

| Phase | Feature | Scope |
|-------|---------|-------|
| C3 | ATCSCC playbook matching | Match corridors to active ATCSCC TMIs; output context label |
| D1 | Shared impact scoring | Combine FAA NAS + ATCSCC + weather context into scored impact |
| D2 | AviaImpact product | On-air aviation delay context package |
| D3+ | RoadCast styles | Highway corridor display styles (separate scope) |

None of these exist in C2. Do not reference or scaffold these in Phase C2 code.

---

## Prohibited Visual Language

When displaying RouteCast corridors styled with any Phase C2 style:

| What you see | What you can say | What you cannot say |
|-------------|-----------------|-------------------|
| Corridor has `routecast_public_alert_context` | "NWS alert near corridor" | "Delay on corridor due to alert" |
| Corridor has rank 1 | "Highest-traffic corridor" | "Most delayed corridor" |
| Corridor geometry is visible | "Route corridor shown" | "Confirmed FAA route restriction" |
| Corridor geometry is unvalidated | "Planning corridor — under review" | "Certified airway routing" |
| No geometry built | "Corridor planned; geometry pending" | "No route exists between these cities" |

---

## Style Assignment

Styles are assigned to corridors via `routecast_corridor_style_assignments`. The `v_routecast_corridor_map` GeoJSON Feature exposes `style_key` as a property for client-side rendering.

Default assignment: `routecast_unvalidated` until geometry is reviewed.

---

## Source Reference

Style definitions: `sql/11_routecast_corridor_geometry.sql`
Style table: `routecast_corridor_styles`
Style assignment table: `routecast_corridor_style_assignments`
Style legend view: `v_routecast_style_legend`
