-- sql/11_routecast_corridor_geometry.sql
-- Phase C2 — RouteCast Corridor Geometry + Impact Styling
--
-- DOCTRINE:
--   Top-50 busiest route source file = static RouteCast reference, NOT delay truth.
--   FAA waypoint/coordinate artifacts = route-geometry inputs, NOT delay truth.
--   RouteCast corridor geometry = planning/display scaffold only.
--   RouteCast corridor geometry is NOT FAA operational delay truth.
--   FAA NAS / ATCSCC / NOTAM / official airport sources remain operational truth.
--   AviationWeather.gov / official aviation-weather sources remain aviation-weather truth.
--   NWS public alerts (Phase C1) = public weather hazard context only, NOT FAA truth.
--   NWS forecast impact remains forecast proxy only — separate lane.
--   Empty state is better than invented geometry.
--   Do not claim flight reroutes, delays, ground stops, or ATC impacts from geometry.
--   Do not invent missing waypoint coordinates.
--   Do not invent route segments.
--   Do not infer precise FAA airway routing from approximate waypoint data.
--   Geometry confidence must be explicit.
--
-- Geometry confidence levels:
--   unvalidated             — default; no geometry computed yet
--   control_line_scaffold   — LineString from resolved waypoints; needs validation
--   needs_source_file       — source CSV not found; no geometry possible
--   partially_resolved      — some waypoints resolved; others unresolved
--
-- Tables:
--   routecast_corridors              — corridor metadata and source reference
--   routecast_corridor_waypoints     — per-corridor waypoints with coordinate status
--   routecast_corridor_geometry      — computed geometry output
--   routecast_corridor_styles        — visual style definitions (seeded below)
--   routecast_corridor_style_assignments — corridor → style mapping
--
-- Views:
--   v_routecast_corridor_geometry    — corridor + geometry joined
--   v_routecast_corridor_map         — GeoJSON Feature per corridor
--   v_routecast_geometry_audit       — audit status with waypoint counts
--   v_routecast_style_legend         — style definitions for UI/graphics
--
-- Populated by:
--   scripts/routecast/seed_routecast_corridors.py
-- Audited by:
--   scripts/audit/audit_routecast_geometry.py
--
-- NOTE: Run after sql/10_public_alert_ontology.sql.
-- Safe to re-run — all statements use CREATE TABLE IF NOT EXISTS
-- and CREATE OR REPLACE VIEW. No destructive operations on existing tables.


-- ─── Table: routecast_corridors ───────────────────────────────────────────────
-- One row per RouteCast aviation route corridor.
-- Sourced from the Top-50 busiest route reference artifact when available.
-- route_rank_basis records the non-operational nature of the ranking.

create table if not exists public.routecast_corridors (
  id                        uuid primary key default gen_random_uuid(),
  corridor_key              text unique not null,
    -- Stable identifier, e.g. 'DFW-JFK', 'LAX-JFK'
  corridor_name             text not null,
    -- Display name, e.g. 'Dallas/Fort Worth → New York JFK'

  rank                      integer,
    -- Source rank from the Top-50 reference; not a delay priority rank
  origin_market             text,
  destination_market        text,
  origin_airport_iata       text,
  origin_airport_icao       text,
  destination_airport_iata  text,
  destination_airport_icao  text,

  primary_route_label       text,
    -- FAA route label / airway string when known, e.g. 'J80 PLESS J146'
  route_family              text,
    -- Route family grouping (future use)
  route_direction           text,
    -- 'eastbound' / 'westbound' / 'bidirectional' (future use)

  corridor_type             text not null default 'aviation_route_corridor',

  source_file               text,
    -- Path/name of the source file used to seed this row
  source_basis              text,
    -- Brief description of source, e.g. 'BTS Top-50 domestic route pairs by passenger volume'

  route_rank_basis          text default
    'static_top_50_busiest_route_reference_not_delay_truth',
    -- ALWAYS present; clarifies ranking is not an FAA delay priority

  geometry_confidence       text not null default 'unvalidated',
    -- unvalidated / control_line_scaffold / needs_source_file / partially_resolved
  geometry_status           text not null default 'needs_validation',
    -- needs_validation / needs_source_file / geometry_built / no_geometry

  active                    boolean not null default true,
  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now()
);

create index if not exists idx_routecast_corridors_corridor_key
  on public.routecast_corridors (corridor_key);

create index if not exists idx_routecast_corridors_rank
  on public.routecast_corridors (rank);

alter table public.routecast_corridors enable row level security;

drop policy if exists "tc_anon_read_routecast_corridors" on public.routecast_corridors;
create policy "tc_anon_read_routecast_corridors"
  on public.routecast_corridors for select
  to anon, authenticated
  using (true);


-- ─── Table: routecast_corridor_waypoints ──────────────────────────────────────
-- Stores per-corridor waypoints as parsed from the source route label.
-- coordinate_status distinguishes resolved vs. unresolved fixes.

create table if not exists public.routecast_corridor_waypoints (
  id                  uuid primary key default gen_random_uuid(),
  corridor_id         uuid references public.routecast_corridors(id) on delete cascade,
  corridor_key        text not null,
  waypoint_order      integer not null,
    -- Sequence position within the corridor route (0 = origin)
  waypoint_label      text not null,
    -- FAA fix/navaid identifier or descriptive label, e.g. 'PLESS', 'DFW', 'JFK'
  waypoint_type       text,
    -- 'airport' / 'fix' / 'navaid' / 'waypoint' / 'marker'
  lat                 numeric(9, 6),
    -- Decimal degrees latitude; null if unresolved
  lon                 numeric(9, 6),
    -- Decimal degrees longitude; null if unresolved
  coordinate_source   text,
    -- Source of coordinates, e.g. 'faa_waypoint_csv' / 'airports_master'
  coordinate_status   text not null default 'unresolved',
    -- 'resolved' / 'unresolved' / 'airport_lookup' / 'manual'
  is_route_endpoint   boolean not null default false,
    -- true for origin and destination airports
  created_at          timestamptz not null default now()
);

create index if not exists idx_routecast_corridor_waypoints_corridor_key
  on public.routecast_corridor_waypoints (corridor_key);

create index if not exists idx_routecast_corridor_waypoints_corridor_id
  on public.routecast_corridor_waypoints (corridor_id);

alter table public.routecast_corridor_waypoints enable row level security;

drop policy if exists "tc_anon_read_routecast_corridor_waypoints"
  on public.routecast_corridor_waypoints;
create policy "tc_anon_read_routecast_corridor_waypoints"
  on public.routecast_corridor_waypoints for select
  to anon, authenticated
  using (true);


-- ─── Table: routecast_corridor_geometry ───────────────────────────────────────
-- Stores the computed corridor geometry output.
-- geometry_geojson is null when fewer than 2 waypoints could be resolved.
-- This table is the authoritative geometry record for each corridor.
-- NEVER stores invented or interpolated geometry.

create table if not exists public.routecast_corridor_geometry (
  id                    uuid primary key default gen_random_uuid(),
  corridor_id           uuid references public.routecast_corridors(id) on delete cascade,
  corridor_key          text not null,

  geometry_geojson      jsonb,
    -- GeoJSON geometry object (LineString); null if not enough resolved points
  geometry_type         text,
    -- 'LineString' when present
  geometry_source       text,
    -- Description of geometry source, e.g. 'waypoint_control_line_from_faa_csv'
  geometry_method       text,
    -- 'resolved_waypoint_control_line' — only method used in C2
    -- null when no geometry could be built
  geometry_confidence   text not null default 'unvalidated',
    -- 'unvalidated' / 'control_line_scaffold' / 'needs_source_file'
  geometry_status       text not null default 'needs_validation',
    -- 'needs_validation' / 'geometry_built' / 'no_geometry' / 'needs_source_file'
  unresolved_waypoints  text[] not null default '{}',
    -- Array of waypoint labels that could not be resolved to coordinates
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

create index if not exists idx_routecast_corridor_geometry_corridor_key
  on public.routecast_corridor_geometry (corridor_key);

create index if not exists idx_routecast_corridor_geometry_corridor_id
  on public.routecast_corridor_geometry (corridor_id);

alter table public.routecast_corridor_geometry enable row level security;

drop policy if exists "tc_anon_read_routecast_corridor_geometry"
  on public.routecast_corridor_geometry;
create policy "tc_anon_read_routecast_corridor_geometry"
  on public.routecast_corridor_geometry for select
  to anon, authenticated
  using (true);


-- ─── Table: routecast_corridor_styles ─────────────────────────────────────────
-- Visual style definitions for corridor display on maps and graphics.
-- Styles are NOT impact scores. They do not imply delays or operational status.
-- Seeded with 5 default styles below.

create table if not exists public.routecast_corridor_styles (
  id              uuid primary key default gen_random_uuid(),
  style_key       text unique not null,
    -- Stable identifier, e.g. 'routecast_default'
  style_label     text not null,
    -- Human-readable label, e.g. 'Default Corridor'
  stroke_color    text not null,
    -- Hex color, e.g. '#4A90D9'
  stroke_width    numeric(4, 1) not null default 2.0,
  stroke_opacity  numeric(3, 2) not null default 0.85,
  dash_array      text,
    -- SVG dash pattern, e.g. '6,4'; null = solid
  fill_color      text,
  fill_opacity    numeric(3, 2),
  use_case        text,
    -- Description of when to apply this style
  created_at      timestamptz not null default now()
);

alter table public.routecast_corridor_styles enable row level security;

drop policy if exists "tc_anon_read_routecast_corridor_styles"
  on public.routecast_corridor_styles;
create policy "tc_anon_read_routecast_corridor_styles"
  on public.routecast_corridor_styles for select
  to anon, authenticated
  using (true);


-- ─── Table: routecast_corridor_style_assignments ──────────────────────────────
-- Bridge table linking corridors to their assigned display style.

create table if not exists public.routecast_corridor_style_assignments (
  id                  uuid primary key default gen_random_uuid(),
  corridor_id         uuid references public.routecast_corridors(id) on delete cascade,
  style_key           text not null,
  assignment_reason   text,
  created_at          timestamptz not null default now()
);

create index if not exists idx_routecast_style_assignments_corridor_id
  on public.routecast_corridor_style_assignments (corridor_id);

alter table public.routecast_corridor_style_assignments enable row level security;

drop policy if exists "tc_anon_read_routecast_corridor_style_assignments"
  on public.routecast_corridor_style_assignments;
create policy "tc_anon_read_routecast_corridor_style_assignments"
  on public.routecast_corridor_style_assignments for select
  to anon, authenticated
  using (true);


-- ─── Seed: Default Corridor Styles ────────────────────────────────────────────
-- These are stable visual style definitions — not impact scores or delay data.
-- Styles do not indicate delays, ground stops, or FAA operational status.

insert into public.routecast_corridor_styles (
  style_key, style_label, stroke_color, stroke_width, stroke_opacity,
  dash_array, fill_color, fill_opacity, use_case
) values
  (
    'routecast_default',
    'Default Corridor',
    '#4A90D9', 2.0, 0.85, null, null, null,
    'Standard corridor display — no impact context assigned. Not an operational status.'
  ),
  (
    'routecast_selected',
    'Selected / Highlighted Corridor',
    '#FF8C00', 3.0, 0.95, null, null, null,
    'Corridor selected by user or highlighted in map/graphics. Not an operational status.'
  ),
  (
    'routecast_watch_context',
    'Watch-Context Corridor',
    '#E8A000', 2.5, 0.80, null, null, null,
    'Future: corridor flagged for monitoring context. Not an operational delay or restriction.'
  ),
  (
    'routecast_unvalidated',
    'Unvalidated Geometry',
    '#9B9B9B', 1.5, 0.60, '6,4', null, null,
    'Corridor geometry not yet validated. Dashed display indicates low confidence. '
    'Do not treat as precise routing.'
  ),
  (
    'routecast_public_alert_context',
    'Public Alert Context',
    '#C0392B', 2.0, 0.70, '4,3', null, null,
    'Corridor overlaps with an NWS public weather alert (Phase C1). '
    'This is weather hazard CONTEXT only — NOT FAA operational delay truth. '
    'Does not indicate ground stops, GDPs, or route closures.'
  )
on conflict (style_key) do update set
  style_label    = excluded.style_label,
  stroke_color   = excluded.stroke_color,
  stroke_width   = excluded.stroke_width,
  stroke_opacity = excluded.stroke_opacity,
  dash_array     = excluded.dash_array,
  use_case       = excluded.use_case;


-- ─── View: v_routecast_corridor_geometry ──────────────────────────────────────
-- Corridor metadata joined to geometry output.
-- geometry_geojson is null when geometry could not be built.

create or replace view public.v_routecast_corridor_geometry as
select
  c.corridor_key,
  c.corridor_name,
  c.rank,
  c.origin_market,
  c.destination_market,
  c.origin_airport_iata,
  c.origin_airport_icao,
  c.destination_airport_iata,
  c.destination_airport_icao,
  c.primary_route_label,
  c.route_family,
  c.route_rank_basis,
  c.corridor_type,
  c.source_file,
  c.source_basis,
  c.active,
  g.geometry_geojson,
  g.geometry_type,
  g.geometry_source,
  g.geometry_method,
  coalesce(g.geometry_confidence, c.geometry_confidence) as geometry_confidence,
  coalesce(g.geometry_status,     c.geometry_status)     as geometry_status,
  coalesce(g.unresolved_waypoints, '{}')                 as unresolved_waypoints,
  g.updated_at as geometry_updated_at
from public.routecast_corridors c
left join public.routecast_corridor_geometry g on g.corridor_id = c.id
where c.active = true;


-- ─── View: v_routecast_corridor_map ───────────────────────────────────────────
-- One GeoJSON Feature per corridor where geometry is available.
-- For use by map/dashboard/graphics layer.
-- Disclaimer is mandatory and embedded in every Feature.

create or replace view public.v_routecast_corridor_map as
select
  c.corridor_key,
  c.corridor_name,
  c.rank,
  g.geometry_confidence,
  g.geometry_status,
  jsonb_build_object(
    'type',     'Feature',
    'geometry', g.geometry_geojson,
    'properties', jsonb_build_object(
      'corridor_key',           c.corridor_key,
      'corridor_name',          c.corridor_name,
      'rank',                   c.rank,
      'origin_market',          c.origin_market,
      'destination_market',     c.destination_market,
      'origin_airport_iata',    c.origin_airport_iata,
      'destination_airport_iata', c.destination_airport_iata,
      'primary_route_label',    c.primary_route_label,
      'route_family',           c.route_family,
      'route_rank_basis',       c.route_rank_basis,
      'geometry_confidence',    g.geometry_confidence,
      'geometry_status',        g.geometry_status,
      'style_key',              sa.style_key,
      'source_basis',           c.source_basis,
      'disclaimer',
        'RouteCast corridor geometry is a planning/display scaffold '
        'and not FAA operational delay truth.'
    )
  ) as geojson_feature
from public.routecast_corridors c
join public.routecast_corridor_geometry g
  on g.corridor_id = c.id
left join public.routecast_corridor_style_assignments sa
  on sa.corridor_id = c.id
where c.active = true
  and g.geometry_geojson is not null;


-- ─── View: v_routecast_geometry_audit ─────────────────────────────────────────
-- Audit view: corridor status with resolved/unresolved waypoint counts.

create or replace view public.v_routecast_geometry_audit as
select
  c.corridor_key,
  c.corridor_name,
  c.rank,
  count(w.id)                                                    as waypoint_count,
  count(w.id) filter (where w.coordinate_status = 'resolved'
                         or w.coordinate_status = 'airport_lookup')
                                                                 as resolved_waypoint_count,
  count(w.id) filter (where w.coordinate_status = 'unresolved') as unresolved_waypoint_count,
  coalesce(g.geometry_status,     c.geometry_status)            as geometry_status,
  coalesce(g.geometry_confidence, c.geometry_confidence)        as geometry_confidence,
  coalesce(g.unresolved_waypoints, '{}')                        as unresolved_waypoints,
  c.route_rank_basis
from public.routecast_corridors c
left join public.routecast_corridor_waypoints w
  on w.corridor_id = c.id
left join public.routecast_corridor_geometry g
  on g.corridor_id = c.id
where c.active = true
group by
  c.corridor_key, c.corridor_name, c.rank,
  g.geometry_status, g.geometry_confidence, g.unresolved_waypoints,
  c.geometry_status, c.geometry_confidence,
  c.route_rank_basis;


-- ─── View: v_routecast_style_legend ───────────────────────────────────────────
-- Style reference for UI and graphics builders.
-- Styles are visual definitions — not impact scores or delay indicators.

create or replace view public.v_routecast_style_legend as
select
  style_key,
  style_label,
  stroke_color,
  stroke_width,
  stroke_opacity,
  dash_array,
  fill_color,
  fill_opacity,
  use_case
from public.routecast_corridor_styles
order by style_key;


-- ─── Grants ───────────────────────────────────────────────────────────────────

grant select on public.routecast_corridors                     to anon, authenticated;
grant select on public.routecast_corridor_waypoints            to anon, authenticated;
grant select on public.routecast_corridor_geometry             to anon, authenticated;
grant select on public.routecast_corridor_styles               to anon, authenticated;
grant select on public.routecast_corridor_style_assignments    to anon, authenticated;
grant select on public.v_routecast_corridor_geometry           to anon, authenticated;
grant select on public.v_routecast_corridor_map                to anon, authenticated;
grant select on public.v_routecast_geometry_audit              to anon, authenticated;
grant select on public.v_routecast_style_legend                to anon, authenticated;

grant select, insert, update, delete
  on public.routecast_corridors,
     public.routecast_corridor_waypoints,
     public.routecast_corridor_geometry,
     public.routecast_corridor_styles,
     public.routecast_corridor_style_assignments
  to service_role;
