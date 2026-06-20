-- sql/08_airport_runway_reference.sql
-- Phase B2 — Static Runway Reference
--
-- Creates the static airport runway reference table and supporting view.
--
-- DOCTRINE:
--   Static runway reference describes runway physical inventory: identifiers,
--   headings, length, width, surface, threshold coordinates, lighting, and ILS
--   availability. It does NOT describe live runway usage, active configuration,
--   AAR, arrival/departure flows, or closures.
--
--   Live/operational runway information must remain sourced from FAA/NAS,
--   ATCSCC, NOTAM, or other official operational sources.
--
-- SOURCE HIERARCHY:
--   1. FAA NASR / FAA AIS — authoritative static runway reference
--   2. OurAirports runways.csv — open development baseline
--   3. atis.info / metar-taf.com — candidate cross-check only (not official)
--
-- Populated by: scripts/load/load_airport_runways.py
-- Audit:        scripts/audit/audit_runway_reference.py


-- ─── Table: airport_runways ────────────────────────────────────────────────

create table if not exists public.airport_runways (
  -- Identity
  runway_id                       text primary key,
    -- Composite: {icao}-{base_end_id}-{reciprocal_end_id}
    -- Example:   KDFW-17C-35C

  airport_id                      text not null,
  iata                            text not null,
  icao                            text not null,

  -- Runway designators
  runway_designator               text not null,
    -- Combined designator, e.g. "17C/35C"
  base_end_id                     text not null,
    -- Low-number or primary end, e.g. "17C"
  reciprocal_end_id               text,
    -- High-number or reciprocal end, e.g. "35C" (null for single-end entries)

  -- Physical dimensions
  length_ft                       integer,
  width_ft                        integer,
  surface_type                    text,
    -- ASPH = asphalt, CONC = concrete, TURF, GRAVEL, etc.

  -- Headings (static magnetic/true at time of survey)
  base_heading_true               numeric(6,2),
  base_heading_magnetic           numeric(6,2),
  reciprocal_heading_true         numeric(6,2),
  reciprocal_heading_magnetic     numeric(6,2),

  -- Threshold coordinates (static survey positions)
  base_threshold_lat              numeric(10,7),
  base_threshold_lon              numeric(11,7),
  reciprocal_threshold_lat        numeric(10,7),
  reciprocal_threshold_lon        numeric(11,7),

  -- Displaced thresholds (feet from runway end)
  base_displaced_threshold_ft     integer,
  reciprocal_displaced_threshold_ft integer,

  -- Lighting
  lighting                        text,
    -- HIRL = high-intensity runway lights
    -- MIRL = medium-intensity runway lights
    -- LIRL = low-intensity runway lights
    -- ODALS = omnidirectional approach lights
    -- MALSR / ALSF-2 / etc.

  -- ILS — base end
  base_ils_available              boolean default false,
  base_ils_frequency              text,
    -- e.g. "110.3" — store as text to preserve precision

  -- ILS — reciprocal end
  reciprocal_ils_available        boolean default false,
  reciprocal_ils_frequency        text,

  -- Data provenance
  source                          text not null default 'template',
    -- 'faa_nasr', 'faa_ais', 'ourairports', 'template'
  source_date                     date,
    -- Date the source data was effective (NASR cycle date, OurAirports export date)
  notes                           text,

  active                          boolean not null default true,
  loaded_at                       timestamptz not null default now(),
  updated_at                      timestamptz not null default now()
);

-- Index: fast lookup by airport
create index if not exists idx_airport_runways_airport_id
  on public.airport_runways (airport_id);

create index if not exists idx_airport_runways_icao
  on public.airport_runways (icao);


-- ─── View: v_airport_runway_context ───────────────────────────────────────
--
-- Joins static runway reference to airport master for a complete runway card.
-- Does NOT include live runway configuration or active flow data.

create or replace view public.v_airport_runway_context as
select
  r.runway_id,
  r.airport_id,
  r.iata,
  r.icao,

  -- Airport context from airports table
  a.display_name,
  a.city,
  a.state,
  a.region,
  a.latitude  as airport_lat,
  a.longitude as airport_lon,

  -- Runway identity
  r.runway_designator,
  r.base_end_id,
  r.reciprocal_end_id,

  -- Physical
  r.length_ft,
  r.width_ft,
  r.surface_type,

  -- Headings
  r.base_heading_true,
  r.base_heading_magnetic,
  r.reciprocal_heading_true,
  r.reciprocal_heading_magnetic,

  -- Thresholds
  r.base_threshold_lat,
  r.base_threshold_lon,
  r.reciprocal_threshold_lat,
  r.reciprocal_threshold_lon,
  r.base_displaced_threshold_ft,
  r.reciprocal_displaced_threshold_ft,

  -- Lighting and ILS
  r.lighting,
  r.base_ils_available,
  r.base_ils_frequency,
  r.reciprocal_ils_available,
  r.reciprocal_ils_frequency,

  -- Provenance
  r.source,
  r.source_date,
  r.notes,
  r.active,
  r.loaded_at,

  -- Required source labels
  'Static reference — FAA / OurAirports' as source_label,
  'Static runway reference describes physical runway inventory only. ' ||
  'Active runway configuration and operational use must be sourced from ' ||
  'FAA/NAS, ATCSCC, or official operational sources.'
    as static_runway_notice

from public.airport_runways r
left join public.airports a
  on a.airport_id = r.airport_id
where r.active = true;


-- ─── Grant: anon read ──────────────────────────────────────────────────────

grant select on public.airport_runways to anon, authenticated;
grant select on public.v_airport_runway_context to anon, authenticated;
grant select, insert, update, delete on public.airport_runways to service_role;
