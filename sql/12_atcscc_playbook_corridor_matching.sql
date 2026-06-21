-- sql/12_atcscc_playbook_corridor_matching.sql
-- Phase C3 — ATCSCC Playbook + Aviation Hazard Corridor Matching
--
-- DOCTRINE:
--   FAA NAS / ATCSCC / NOTAM / official airport sources
--     = CURRENT OPERATIONAL IMPACT — operational aviation truth.
--     Advisory language is operational context — NOT route-impact scoring.
--   RouteCast corridor geometry = PLANNING/DISPLAY SCAFFOLD ONLY.
--     Not FAA operational delay truth. Not ATC restriction truth.
--     Corridor × advisory matches are context scaffolds, not impact scores.
--   NWS CAP / WEA alerts = PUBLIC WEATHER ALERT TRUTH ONLY.
--     Not FAA operational delay truth.
--     Weather hazard context near a corridor is NOT a delay claim.
--   AviationWeather.gov = AVIATION WEATHER TRUTH.
--     SIGMET/AIRMET/CWA hazard context near corridors is NOT a delay claim.
--   NWS forecast = FORECAST WEATHER IMPACT PROXY ONLY. Not FAA operational truth.
--
--   DO NOT:
--     Claim a public alert causes FAA delay.
--     Claim route geometry causes delay.
--     Produce automatic AviaImpact score.
--     Produce RoadCast output.
--     Invent advisories, restrictions, ground stops, or route closures.
--     Invent match rows.
--   Empty state is better than invented data.
--
-- Source truth lanes:
--   faa_atcscc_operational_truth            — FAA NAS / ATCSCC advisory rows
--   faa_atcscc_operational_context_pattern  — playbook pattern definitions
--   routecast_atcscc_context_match          — corridor × advisory context scaffold
--   corridor_weather_hazard_context_only    — corridor × hazard context scaffold
--
-- Tables:
--   atcscc_advisories                          — C3 advisory storage
--   atcscc_playbook_patterns                   — general pattern definitions (not real advisories)
--   routecast_corridor_atcscc_matches          — corridor × advisory context match
--   routecast_corridor_hazard_context_matches  — corridor × weather hazard context match
--
-- Views:
--   v_atcscc_advisory_dashboard    — advisory status for UI / ops review
--   v_routecast_atcscc_context     — corridor × advisory context joined
--   v_routecast_hazard_context     — corridor × hazard context joined
--   v_c3_matching_audit            — count / status audit view
--
-- NOTE: Run after sql/11_routecast_corridor_geometry.sql.
-- Safe to re-run — all statements use CREATE TABLE IF NOT EXISTS
-- and CREATE OR REPLACE VIEW. No destructive operations on existing tables.


-- ─── Table: atcscc_advisories ─────────────────────────────────────────────────
-- One row per ATCSCC / FAA NAS advisory fetched and parsed.
-- Source truth lane: faa_atcscc_operational_truth.
-- Raw text and payload preserved. Fields parsed conservatively from explicit
-- advisory language only — never invented, never inferred from weather context.
-- ATCSCC advisory data is FAA operational context.
-- This table does NOT contain delay minutes, AAR, or route-impact scores.

create table if not exists public.atcscc_advisories (
  id                        uuid primary key default gen_random_uuid(),
  advisory_id               text unique,
    -- Stable dedup key: hash of source + content identity
  advisory_number           text,
    -- Advisory number from source when parseable (e.g. '42', 'ADVZY 42')
  source                    text not null default 'FAA_ATCSCC',
  source_url                text,
    -- Source URL if fetched from a specific advisory page
  source_timestamp          timestamptz,
    -- Timestamp from source text when parseable; not our fetch time
  event_time_text           text,
    -- Raw event time string as found in source (e.g. '1400Z-2000Z')
  raw_text                  text not null default '',
    -- Preserved full plain-text of the advisory
  raw_payload               jsonb,
    -- Full raw payload (JSON or structured parse) if available

  advisory_type             text,
    -- Conservative parse: GDP / GS / AFP / MIT / reroute / weather / other
    -- Set ONLY when advisory text explicitly uses the term.
  operational_category      text,
    -- Conservative category from playbook pattern match if matched

  affected_facilities       text[] not null default '{}',
    -- FAA facility codes mentioned explicitly in advisory text
  affected_airports         text[] not null default '{}',
    -- IATA or ICAO codes mentioned explicitly in advisory text
  affected_regions          text[] not null default '{}',
    -- Named regions or ARTCCs mentioned explicitly
  mentioned_routes          text[] not null default '{}',
    -- Route labels / airways mentioned explicitly
  mentioned_fix_labels      text[] not null default '{}',
    -- Fix labels mentioned explicitly (e.g. 'PLESS', 'CAMRN')
  weather_terms             text[] not null default '{}',
    -- Weather-related terms mentioned explicitly in advisory
  traffic_management_terms  text[] not null default '{}',
    -- Traffic management terms mentioned explicitly (GDP, GS, MIT, AFP, etc.)

  parsed_summary            text,
    -- Short text summary parsed from source — never invented, never augmented
  is_active                 boolean not null default true,
  is_stale                  boolean not null default false,
    -- is_stale = true when no refresh within expected source cadence

  source_truth_lane         text not null default 'faa_atcscc_operational_truth',
    -- Always 'faa_atcscc_operational_truth' for advisory rows

  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now()
);

comment on table public.atcscc_advisories is
  'FAA ATCSCC advisory storage for C3 context matching. '
  'Source truth lane: faa_atcscc_operational_truth. '
  'Advisory data is FAA operational context — not delay scores or route-impact scores. '
  'Raw text preserved. Fields parsed conservatively from explicit advisory language only. '
  'Do not invent advisories. Empty state is better than invented data.';


-- ─── Table: atcscc_playbook_patterns ─────────────────────────────────────────
-- General pattern definitions for ATCSCC advisory classification.
-- These are NOT real advisories. They are concept / category templates
-- used to classify incoming advisory text into operational_category buckets.
-- prohibited_output_language enforces doctrine at the pattern level.
-- Source truth lane: faa_atcscc_operational_context_pattern.

create table if not exists public.atcscc_playbook_patterns (
  id                         uuid primary key default gen_random_uuid(),
  pattern_key                text unique not null,
    -- Stable machine key, e.g. 'ground_delay_program_context'
  pattern_label              text not null,
    -- Display label, e.g. 'Ground Delay Program'
  operational_category       text not null,
    -- Category bucket: GDP / GS / AFP / MIT / reroute / weather / staffing / etc.
  trigger_terms              text[] not null default '{}',
    -- Terms in advisory text that suggest this pattern applies
  facility_terms             text[] not null default '{}',
    -- Facility-type terms associated with this pattern
  route_terms                text[] not null default '{}',
    -- Route / airway terms associated with this pattern
  weather_terms              text[] not null default '{}',
    -- Weather terms that often accompany this pattern
  description                text,
  allowed_output_language    text,
    -- What C3 may say when this pattern matches
  prohibited_output_language text,
    -- What C3 must NOT say — no delay claim without live FAA operational data
  source_truth_lane          text not null default 'faa_atcscc_operational_context_pattern',
  created_at                 timestamptz not null default now()
);

comment on table public.atcscc_playbook_patterns is
  'General ATCSCC advisory classification patterns. '
  'Source truth lane: faa_atcscc_operational_context_pattern. '
  'These are static concept definitions — NOT real advisories. '
  'prohibited_output_language must be respected before producing any user-facing output. '
  'No delay claims without live FAA operational data.';


-- ─── Table: routecast_corridor_atcscc_matches ────────────────────────────────
-- Context match rows linking RouteCast corridors to ATCSCC advisories.
-- These are CONTEXT SCAFFOLDS — not delay claims, not impact scores,
-- not ATC restriction claims.
-- Source truth lane: routecast_atcscc_context_match.

create table if not exists public.routecast_corridor_atcscc_matches (
  id                      uuid primary key default gen_random_uuid(),
  corridor_key            text not null,
    -- References routecast_corridors.corridor_key
  advisory_id             text,
    -- References atcscc_advisories.advisory_id (nullable before live pull)
  match_type              text not null,
    -- 'airport_overlap' / 'fix_overlap' / 'route_label_overlap' / 'facility_text_match'
  match_confidence        text not null,
    -- 'medium_airport_or_fix_overlap' — corridor airports / fixes in advisory text
    -- 'low_text_context'              — broad regional / facility text match
    -- 'unmatched'                     — no safe match found
    -- 'high_geometry_intersection'    — ONLY when geometry intersection is confirmed
  matched_terms           text[] not null default '{}',
    -- Terms from the advisory that triggered the match
  matched_airports        text[] not null default '{}',
    -- Airport codes that appear in both corridor and advisory
  matched_facilities      text[] not null default '{}',
    -- Facility codes that appear in advisory text
  matched_fixes           text[] not null default '{}',
    -- Fix labels that appear in both corridor and advisory
  match_reason            text,
    -- Human-readable description of why this match was created
  source_truth_lane       text not null default 'routecast_atcscc_context_match',
  operator_review_status  text not null default 'draft',
    -- 'draft' / 'reviewed' / 'accepted' / 'rejected'
    -- All system-generated matches start as 'draft'
  created_at              timestamptz not null default now()
);

comment on table public.routecast_corridor_atcscc_matches is
  'RouteCast corridor × ATCSCC advisory context match scaffold. '
  'Source truth lane: routecast_atcscc_context_match. '
  'These are context associations — not delay claims, not impact scores, '
  'not ATC restriction claims. All matches default to operator_review_status=draft. '
  'Do not invent match rows. Do not claim delay without explicit advisory text.';


-- ─── Table: routecast_corridor_hazard_context_matches ────────────────────────
-- Context match rows linking RouteCast corridors to weather hazard context.
-- Covers NWS CAP public alerts and AviationWeather.gov hazards (SIGMET/AIRMET/CWA).
-- Weather hazard context near a corridor is NOT FAA operational delay truth.
-- NWS alerts are Public Weather Alert Truth — not FAA delay truth.
-- Source truth lane: corridor_weather_hazard_context_only.

create table if not exists public.routecast_corridor_hazard_context_matches (
  id                        uuid primary key default gen_random_uuid(),
  corridor_key              text not null,
    -- References routecast_corridors.corridor_key
  hazard_source             text not null,
    -- 'nws_cap' / 'aviationweather_sigmet' / 'aviationweather_airmet' / 'aviationweather_cwa'
  hazard_source_id          text,
    -- Source-system identifier for the specific hazard row
  hazard_type               text,
    -- Alert / hazard type from source (e.g. 'Winter Storm Warning', 'SIGMET', 'AIRMET Sierra')
  match_type                text not null,
    -- 'airport_overlap' / 'geometry_intersection_scaffold' / 'text_area_match'
  match_confidence          text not null,
    -- 'medium_airport_or_fix_overlap' — corridor airports appear in hazard affected area
    -- 'low_text_context'              — broad area text match only
    -- 'unmatched'                     — no safe match
    -- 'high_geometry_intersection'    — ONLY when geometry intersection is confirmed
  matched_geometry_method   text,
    -- 'ray_cast_point_in_polygon' / 'bbox_overlap' / 'text_match_only' / null
  matched_terms             text[] not null default '{}',
    -- Terms from the hazard that triggered the match
  match_reason              text,
    -- Human-readable description of why this match was created
  source_truth_lane         text not null default 'corridor_weather_hazard_context_only',
    -- Always 'corridor_weather_hazard_context_only'
    -- Never promoted to an operational delay lane from weather context alone
  operator_review_status    text not null default 'draft',
  created_at                timestamptz not null default now()
);

comment on table public.routecast_corridor_hazard_context_matches is
  'RouteCast corridor × weather hazard context match scaffold. '
  'Source truth lane: corridor_weather_hazard_context_only. '
  'Weather hazard context near a corridor is NOT FAA operational delay truth. '
  'NWS CAP alerts are Public Weather Alert Truth — not FAA operational delay truth. '
  'AviationWeather hazards are Aviation Weather Truth — not FAA delay truth. '
  'Do not invent match rows. Empty state is better than invented data.';


-- ─── Seed: atcscc_playbook_patterns ──────────────────────────────────────────
-- Static general pattern definitions. NOT real ATCSCC advisories.
-- Each row enforces doctrine via prohibited_output_language.
-- Do not invent real advisory rows here.

insert into public.atcscc_playbook_patterns (
  pattern_key, pattern_label, operational_category,
  trigger_terms, facility_terms, route_terms, weather_terms,
  description, allowed_output_language, prohibited_output_language,
  source_truth_lane
) values

( 'ground_delay_program_context',
  'Ground Delay Program',
  'GDP',
  array['GDP','ground delay program','ground delay'],
  array['TRACON','ARTCC','ATCT'],
  array[]::text[],
  array['volume','capacity','weather','fog','low visibility'],
  'Pattern for ground delay program advisory context. '
  'GDP is issued by FAA ATCSCC — not derived from NWS or RouteCast.',
  'ATCSCC advisory context mentions a Ground Delay Program. Source: FAA ATCSCC.',
  'Do not claim a GDP is active without explicit live advisory text. '
  'Do not claim delay minutes without explicit advisory data. '
  'Do not derive GDP from NWS forecast or RouteCast corridor geometry.',
  'faa_atcscc_operational_context_pattern'
),

( 'ground_stop_context',
  'Ground Stop',
  'GS',
  array['GS','ground stop','ground stops'],
  array['TRACON','ARTCC','ATCT'],
  array[]::text[],
  array['convective','thunderstorm','ice','low ceiling'],
  'Pattern for ground stop advisory context. '
  'GS is issued by FAA ATCSCC — not derived from NWS or RouteCast.',
  'ATCSCC advisory context mentions a Ground Stop. Source: FAA ATCSCC.',
  'Do not claim a ground stop is active without explicit live advisory text. '
  'Do not derive ground stop from weather forecast or NWS public alert. '
  'Do not derive ground stop from RouteCast corridor geometry.',
  'faa_atcscc_operational_context_pattern'
),

( 'airspace_flow_program_context',
  'Airspace Flow Program',
  'AFP',
  array['AFP','airspace flow program','flow program'],
  array['ARTCC','ZDC','ZNY','ZBW','ZJX','ZAU','ZID','ZOB'],
  array[]::text[],
  array['convective','thunderstorm','SIGMET'],
  'Pattern for airspace flow program advisory context.',
  'ATCSCC advisory context mentions an Airspace Flow Program. Source: FAA ATCSCC.',
  'Do not claim an AFP is active without explicit live advisory text. '
  'Do not derive AFP from RouteCast geometry or NWS alerts.',
  'faa_atcscc_operational_context_pattern'
),

( 'reroute_advisory_context',
  'Reroute Advisory',
  'reroute',
  array['reroute','playbook','CDR','coded departure route','avoid'],
  array['ATCSCC','ARTCC'],
  array['J80','J100','J146','Q','DCT'],
  array['convective','SIGMET','thunderstorm'],
  'Pattern for reroute or coded departure route advisory context.',
  'ATCSCC advisory context mentions rerouting or a coded departure route. Source: FAA ATCSCC.',
  'Do not claim a reroute is in effect without explicit advisory text. '
  'RouteCast corridor geometry is not reroute truth. '
  'Do not imply route closure from RouteCast geometry alone.',
  'faa_atcscc_operational_context_pattern'
),

( 'miles_in_trail_context',
  'Miles in Trail',
  'MIT',
  array['MIT','miles in trail','miles-in-trail'],
  array['ARTCC','TRACON','ENROUTE'],
  array[]::text[],
  array['convective','weather','volume'],
  'Pattern for miles-in-trail separation advisory context.',
  'ATCSCC advisory context mentions miles-in-trail separation. Source: FAA ATCSCC.',
  'Do not claim MIT restrictions without explicit live advisory text. '
  'Do not derive MIT from NWS alerts or RouteCast geometry.',
  'faa_atcscc_operational_context_pattern'
),

( 'weather_avoidance_context',
  'Weather Avoidance',
  'weather_avoidance',
  array['weather avoidance','SWAP','avoidance route','pilot deviation'],
  array[]::text[],
  array[]::text[],
  array['convective','thunderstorm','SIGMET','turbulence','icing'],
  'Pattern for weather avoidance or SWAP advisory context.',
  'ATCSCC advisory context mentions weather avoidance. Source: FAA ATCSCC.',
  'Do not claim specific avoidance routes without advisory text support. '
  'NWS alerts indicate weather — not FAA avoidance decisions. '
  'RouteCast geometry is a display scaffold, not a routing authority.',
  'faa_atcscc_operational_context_pattern'
),

( 'staffing_trigger_context',
  'Staffing Trigger',
  'staffing',
  array['staffing','controller','ATC staffing','short staffed','low staffing'],
  array['ARTCC','TRACON','ATCT'],
  array[]::text[],
  array[]::text[],
  'Pattern for staffing-related capacity advisory context.',
  'ATCSCC advisory context mentions staffing as a capacity trigger. Source: FAA ATCSCC.',
  'Do not claim staffing delays without explicit live advisory text. '
  'Staffing status is FAA operational data — not derivable from weather context.',
  'faa_atcscc_operational_context_pattern'
),

( 'runway_or_airport_constraint_context',
  'Runway / Airport Constraint',
  'runway_constraint',
  array['runway','taxiway','EMAS','closure','equipment','construction','NOTAM'],
  array['ATCT','TRACON'],
  array[]::text[],
  array[]::text[],
  'Pattern for runway or airport physical constraint advisory context.',
  'ATCSCC advisory context mentions a runway or airport constraint. '
  'Source: FAA ATCSCC / NOTAM / airport authority.',
  'Do not claim runway closure without explicit NOTAM or advisory text support. '
  'RouteCast geometry cannot confirm or deny runway status. '
  'NWS alerts are weather context — not runway closure indicators.',
  'faa_atcscc_operational_context_pattern'
)

on conflict (pattern_key) do nothing;


-- ─── View: v_atcscc_advisory_dashboard ───────────────────────────────────────
-- Advisory status dashboard for ops review.
-- ATCSCC advisory data is FAA operational context.
-- RouteCast matches are context scaffolds and are not impact scores.

create or replace view public.v_atcscc_advisory_dashboard as
select
  a.advisory_id,
  a.advisory_number,
  a.source,
  a.source_timestamp,
  a.advisory_type,
  a.operational_category,
  a.affected_facilities,
  a.affected_airports,
  a.affected_regions,
  a.mentioned_routes,
  a.mentioned_fix_labels,
  a.traffic_management_terms,
  a.weather_terms,
  a.parsed_summary,
  a.is_active,
  a.is_stale,
  a.source_truth_lane,
  a.updated_at,
  'ATCSCC advisory data is FAA operational context. '
  'RouteCast matches are context scaffolds and are not impact scores.'::text  as disclaimer
from public.atcscc_advisories a
order by a.source_timestamp desc nulls last, a.created_at desc;


-- ─── View: v_routecast_atcscc_context ────────────────────────────────────────
-- RouteCast corridor × ATCSCC advisory context match view.
-- This is a RouteCast advisory-context match,
-- not a delay claim or ATC restriction claim.

create or replace view public.v_routecast_atcscc_context as
select
  m.corridor_key,
  c.corridor_name,
  c.origin_airport_iata,
  c.origin_airport_icao,
  c.destination_airport_iata,
  c.destination_airport_icao,
  m.advisory_id,
  a.advisory_type,
  a.operational_category,
  m.match_type,
  m.match_confidence,
  m.matched_terms,
  m.matched_airports,
  m.matched_facilities,
  m.matched_fixes,
  m.match_reason,
  m.operator_review_status,
  m.source_truth_lane,
  m.created_at,
  'This is a RouteCast advisory-context match, '
  'not a delay claim or ATC restriction claim.'::text  as disclaimer
from public.routecast_corridor_atcscc_matches m
left join public.routecast_corridors c
  on c.corridor_key = m.corridor_key
left join public.atcscc_advisories a
  on a.advisory_id = m.advisory_id
order by m.created_at desc;


-- ─── View: v_routecast_hazard_context ────────────────────────────────────────
-- RouteCast corridor × weather hazard context match view.
-- Weather hazard context near a corridor is not FAA operational delay truth.

create or replace view public.v_routecast_hazard_context as
select
  m.corridor_key,
  c.corridor_name,
  m.hazard_source,
  m.hazard_source_id,
  m.hazard_type,
  m.match_type,
  m.match_confidence,
  m.matched_geometry_method,
  m.matched_terms,
  m.match_reason,
  m.operator_review_status,
  m.source_truth_lane,
  m.created_at,
  'Weather hazard context near a corridor is not FAA operational delay truth.'::text  as disclaimer
from public.routecast_corridor_hazard_context_matches m
left join public.routecast_corridors c
  on c.corridor_key = m.corridor_key
order by m.created_at desc;


-- ─── View: v_c3_matching_audit ────────────────────────────────────────────────
-- Audit counts by category, match confidence, review status, and source truth lane.

create or replace view public.v_c3_matching_audit as
select
  'atcscc_advisories'            as source_category,
  count(*)::integer              as row_count,
  null::text                     as match_confidence,
  null::text                     as operator_review_status,
  null::text                     as source_truth_lane
from public.atcscc_advisories

union all

select
  'atcscc_playbook_patterns',
  count(*)::integer,
  null, null, null
from public.atcscc_playbook_patterns

union all

select
  'routecast_corridor_atcscc_matches',
  count(*)::integer,
  match_confidence,
  operator_review_status,
  source_truth_lane
from public.routecast_corridor_atcscc_matches
group by match_confidence, operator_review_status, source_truth_lane

union all

select
  'routecast_corridor_hazard_context_matches',
  count(*)::integer,
  match_confidence,
  operator_review_status,
  source_truth_lane
from public.routecast_corridor_hazard_context_matches
group by match_confidence, operator_review_status, source_truth_lane

order by source_category, match_confidence, operator_review_status;


-- ─── Grants ───────────────────────────────────────────────────────────────────

grant select on public.atcscc_advisories                          to anon, authenticated;
grant select on public.atcscc_playbook_patterns                   to anon, authenticated;
grant select on public.routecast_corridor_atcscc_matches          to anon, authenticated;
grant select on public.routecast_corridor_hazard_context_matches  to anon, authenticated;
grant select on public.v_atcscc_advisory_dashboard                to anon, authenticated;
grant select on public.v_routecast_atcscc_context                 to anon, authenticated;
grant select on public.v_routecast_hazard_context                 to anon, authenticated;
grant select on public.v_c3_matching_audit                        to anon, authenticated;

grant select, insert, update, delete
  on public.atcscc_advisories,
     public.atcscc_playbook_patterns,
     public.routecast_corridor_atcscc_matches,
     public.routecast_corridor_hazard_context_matches
  to service_role;
