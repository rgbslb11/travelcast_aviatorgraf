-- sql/09_taf_pirep_maturity.sql
-- Phase B3/B4 — TAF Timeline + PIREP Maturity
--
-- DOCTRINE:
--   AviationWeather.gov = Aviation Weather Truth.
--   TAF is official aviation forecast weather. It does NOT predict FAA operational
--   delays, ground stops, ground delay programs, route closures, or AAR.
--   PIREPs are pilot-reported observed conditions. They are NOT delay forecasts.
--   NWS forecast impact remains forecast proxy only — separate lane.
--   Empty state is better than invented data.
--
-- Staleness rule:
--   Data fetched_at_utc >= 8 hours ago is treated as stale for TravelCast
--   aviation-weather production. Views surface this as a flag, not hidden.
--
-- Populated by:
--   scripts/pull/pull_taf_timeline.py
--   scripts/pull/pull_pireps.py
-- Audited by:
--   scripts/audit/audit_taf_pirep_maturity.py


-- ─── Source Systems ────────────────────────────────────────────────────────

insert into public.source_systems (
  source_system_id,
  display_name,
  trust_tier,
  official_source,
  mission_critical_allowed,
  category,
  notes
) values (
  'taf_timeline',
  'AviationWeather TAF Timeline',
  1,
  true,
  true,
  'official',
  'Structured TAF forecast periods parsed from AviationWeather.gov TAF data. '
  'Aviation Weather Truth. Does not represent FAA operational delay information.'
)
on conflict (source_system_id) do update set
  display_name = excluded.display_name,
  trust_tier = excluded.trust_tier,
  official_source = excluded.official_source,
  mission_critical_allowed = excluded.mission_critical_allowed,
  notes = excluded.notes;

insert into public.source_systems (
  source_system_id,
  display_name,
  trust_tier,
  official_source,
  mission_critical_allowed,
  category,
  notes
) values (
  'aviationweather_pirep',
  'AviationWeather PIREPs',
  1,
  true,
  true,
  'official',
  'Pilot Weather Reports (PIREPs/UAs) from AviationWeather.gov. '
  'Aviation Weather Truth — observational. Not delay forecasts.'
)
on conflict (source_system_id) do update set
  display_name = excluded.display_name,
  trust_tier = excluded.trust_tier,
  official_source = excluded.official_source,
  mission_critical_allowed = excluded.mission_critical_allowed,
  notes = excluded.notes;


-- ─── Table: taf_forecasts ──────────────────────────────────────────────────
-- One row per TAF bulletin per airport per issue time.

create table if not exists public.taf_forecasts (
  taf_id                  text primary key,
    -- Format: {ICAO}-{YYYYMMDD}-{HHMM}, e.g. KATL-20260620-0958

  airport_id              text not null,
  iata                    text not null,
  icao                    text not null,

  issue_time_utc          timestamptz,
  valid_from_utc          timestamptz,
  valid_to_utc            timestamptz,

  raw_taf                 text,
  remarks                 text,

  source_system_id        text not null default 'taf_timeline',
  source_url              text,
  fetched_at_utc          timestamptz not null default now(),
  updated_at              timestamptz not null default now()
);

create index if not exists idx_taf_forecasts_airport_id
  on public.taf_forecasts (airport_id);

create index if not exists idx_taf_forecasts_icao
  on public.taf_forecasts (icao);

create index if not exists idx_taf_forecasts_valid_from
  on public.taf_forecasts (valid_from_utc);


-- ─── Table: taf_forecast_periods ──────────────────────────────────────────
-- One row per forecast group within a TAF (BASE/FM/TEMPO/PROB/BECMG).

create table if not exists public.taf_forecast_periods (
  period_id               text primary key,
    -- Format: {taf_id}-{seq:02d}, e.g. KATL-20260620-0958-00

  taf_id                  text not null
    references public.taf_forecasts(taf_id) on delete cascade,

  airport_id              text not null,
  iata                    text not null,
  icao                    text not null,
  seq                     integer not null,

  -- Group type
  group_type              text not null,
    -- BASE, FM, TEMPO, PROB, BECMG

  probability             integer,
    -- Numeric probability value for PROB groups (e.g. 30 for PROB30); null otherwise

  -- Validity window
  valid_from_utc          timestamptz,
  valid_to_utc            timestamptz,
  become_time_utc         timestamptz,
    -- Relevant for BECMG groups

  -- Wind
  wind_dir                text,
    -- 'VRB' or zero-padded 3-digit string, e.g. '350'
  wind_speed_kt           integer,
  wind_gust_kt            integer,

  -- Visibility
  visibility_sm           text,
    -- Raw visibility string from source, e.g. '6+', '1/2', '1 3/4'

  -- Weather
  wx_string               text,
    -- Raw wx string from source, e.g. '-TSRA BR'

  -- Sky / clouds (raw JSON array from source)
  clouds_json             jsonb,
    -- [{cover: 'BKN', base: 3000}, ...] — base in feet
  ceiling_ft              integer,
    -- Lowest BKN or OVC layer in feet; null if no ceiling

  -- Implied flight category (computed cautiously from ceiling+vis)
  flight_category_implied text,
    -- VFR/MVFR/IFR/LIFR — prefixed 'implied'; not a certified determination

  -- Human-readable conditions summary (no interpretation beyond source text)
  conditions_text         text,

  -- Full raw period JSON for completeness
  raw_period_json         jsonb,

  created_at              timestamptz not null default now()
);

create index if not exists idx_taf_periods_taf_id
  on public.taf_forecast_periods (taf_id);

create index if not exists idx_taf_periods_airport_id
  on public.taf_forecast_periods (airport_id);

create index if not exists idx_taf_periods_valid_from
  on public.taf_forecast_periods (valid_from_utc);


-- ─── Table: pirep_reports ──────────────────────────────────────────────────
-- One row per PIREP. Keyed by deterministic hash of raw text.

create table if not exists public.pirep_reports (
  pirep_id                text primary key,
    -- 'pirep-{12-char md5 of rawOb}'

  report_type             text,
    -- 'UA' (routine PIREP) or 'UUA' (urgent PIREP) or 'AIREP'

  raw_pirep               text,
    -- Preserved raw PIREP text

  observed_at_utc         timestamptz,
  aircraft_type           text,
  altitude_ft             integer,
    -- Flight level converted to feet (fltLvl * 100); null if not parseable

  -- Location (source-provided only — do not invent from vague text)
  location_text           text,
    -- Raw location reference as provided by source
  latitude                numeric(10, 7),
    -- null if not safely provided by source
  longitude               numeric(11, 7),
    -- null if not safely provided by source
  is_geolocated           boolean not null default false,
    -- true only when lat/lon come from the source, not inferred

  -- Turbulence
  turbulence_intensity    text,
    -- NEG/NEGclr/LGT/LGT-MOD/MOD/MOD-SEV/SEV/EXTR
  turbulence_type         text,
    -- CAT/CHOP/LLWS/MECH etc.
  turbulence_frequency    text,

  -- Icing
  icing_intensity         text,
    -- NEG/TRC/LGT/MOD/HVY
  icing_type              text,
    -- RIME/MXD/CLR

  -- Sky / visibility
  sky_cover               text,
  visibility_sm           text,
  wx_string               text,

  -- Other
  temperature_c           text,
  wind_dir                text,
  wind_speed_kt           text,
  remarks                 text,

  -- Provenance
  source_system_id        text not null default 'aviationweather_pirep',
  source_url              text,
  fetched_at_utc          timestamptz not null default now(),
  updated_at              timestamptz not null default now()
);

create index if not exists idx_pirep_reports_observed_at
  on public.pirep_reports (observed_at_utc);

create index if not exists idx_pirep_reports_geolocated
  on public.pirep_reports (is_geolocated)
  where is_geolocated = true;


-- ─── Table: pirep_airport_associations ────────────────────────────────────
-- Links PIREPs to nearby TravelCast airports.

create table if not exists public.pirep_airport_associations (
  pirep_id                text not null
    references public.pirep_reports(pirep_id) on delete cascade,
  airport_id              text not null,
  iata                    text not null,
  icao                    text not null,

  distance_nm             numeric(8, 2),
    -- null if association is not geometry-based

  association_method      text not null,
    -- 'radius_match'   — lat/lon within configured NM radius
    -- 'fetch_target'   — airport was in the fetch batch but PIREP has no lat/lon
    -- 'manual'         — operator-assigned

  associated_at_utc       timestamptz not null default now(),

  primary key (pirep_id, airport_id)
);

create index if not exists idx_pirep_assoc_airport_id
  on public.pirep_airport_associations (airport_id);


-- ─── View: v_taf_timeline_current ─────────────────────────────────────────
-- Current (non-expired) TAF periods across all airports, with freshness flags.

create or replace view public.v_taf_timeline_current as
select
  p.period_id,
  p.taf_id,
  p.airport_id,
  p.iata,
  p.icao,
  p.seq,
  p.group_type,
  p.probability,
  p.valid_from_utc,
  p.valid_to_utc,
  p.wind_dir,
  p.wind_speed_kt,
  p.wind_gust_kt,
  p.visibility_sm,
  p.wx_string,
  p.ceiling_ft,
  p.flight_category_implied,
  p.conditions_text,
  f.issue_time_utc,
  f.raw_taf,
  f.fetched_at_utc,

  -- Staleness: data older than 8 hours is stale for TravelCast aviation-weather production
  case
    when f.fetched_at_utc < now() - interval '8 hours' then true
    else false
  end as is_stale,

  -- Whether this specific period window has already passed
  case
    when p.valid_to_utc is not null and p.valid_to_utc < now() then true
    else false
  end as is_expired,

  'Aviation Weather Truth — AviationWeather.gov' as source_label,
  'TAF is aviation forecast weather. It does not predict FAA operational delays, '
  'ground stops, ground delay programs, route closures, or AAR.'
    as taf_notice

from public.taf_forecast_periods p
join public.taf_forecasts f on f.taf_id = p.taf_id
where
  -- Exclude periods whose validity window has fully passed
  (p.valid_to_utc is null or p.valid_to_utc >= now() - interval '1 hour');


-- ─── View: v_airport_taf_periods_active ───────────────────────────────────
-- TAF periods with airport context, for dashboard/detail panel use.

create or replace view public.v_airport_taf_periods_active as
select
  t.period_id,
  t.taf_id,
  t.iata,
  t.icao,
  a.display_name,
  a.city,
  a.state,
  a.region,
  t.group_type,
  t.probability,
  t.valid_from_utc,
  t.valid_to_utc,
  t.wind_dir,
  t.wind_speed_kt,
  t.wind_gust_kt,
  t.visibility_sm,
  t.wx_string,
  t.ceiling_ft,
  t.flight_category_implied,
  t.conditions_text,
  t.issue_time_utc,
  t.fetched_at_utc,
  t.is_stale,
  t.is_expired,
  t.source_label,
  t.taf_notice
from public.v_taf_timeline_current t
left join public.airports a
  on a.airport_id = t.airport_id;


-- ─── View: v_pireps_active ─────────────────────────────────────────────────
-- Non-stale PIREPs, newest first.

create or replace view public.v_pireps_active as
select
  p.pirep_id,
  p.report_type,
  p.raw_pirep,
  p.observed_at_utc,
  p.aircraft_type,
  p.altitude_ft,
  p.location_text,
  p.latitude,
  p.longitude,
  p.is_geolocated,
  p.turbulence_intensity,
  p.turbulence_type,
  p.turbulence_frequency,
  p.icing_intensity,
  p.icing_type,
  p.sky_cover,
  p.visibility_sm,
  p.wx_string,
  p.wind_dir,
  p.wind_speed_kt,
  p.remarks,
  p.fetched_at_utc,

  -- PIREPs older than 2 hours are operationally stale for TravelCast use
  case
    when p.observed_at_utc < now() - interval '2 hours' then true
    else false
  end as is_operationally_stale,

  -- Data older than 8 hours should not be used in TravelCast aviation-weather production
  case
    when p.fetched_at_utc < now() - interval '8 hours' then true
    else false
  end as is_fetch_stale,

  'Aviation Weather Truth — AviationWeather.gov' as source_label,
  'PIREPs are pilot-reported observations of actual conditions. '
  'They are not FAA operational delay data, delay forecasts, or route closure information.'
    as pirep_notice

from public.pirep_reports p
where
  -- Exclude very old observations (older than 6 hours)
  (p.observed_at_utc is null or p.observed_at_utc >= now() - interval '6 hours')
order by p.observed_at_utc desc nulls last;


-- ─── View: v_airport_pireps_active ────────────────────────────────────────
-- PIREPs associated to TravelCast airports, with airport context.

create or replace view public.v_airport_pireps_active as
select
  m.airport_id,
  m.iata,
  m.icao,
  a.display_name,
  a.city,
  a.state,
  a.region,
  m.distance_nm,
  m.association_method,
  p.pirep_id,
  p.report_type,
  p.raw_pirep,
  p.observed_at_utc,
  p.aircraft_type,
  p.altitude_ft,
  p.location_text,
  p.is_geolocated,
  p.turbulence_intensity,
  p.turbulence_type,
  p.icing_intensity,
  p.icing_type,
  p.sky_cover,
  p.visibility_sm,
  p.wx_string,
  p.wind_dir,
  p.wind_speed_kt,
  p.remarks,
  p.fetched_at_utc,
  p.is_operationally_stale,
  p.is_fetch_stale,
  p.source_label,
  p.pirep_notice
from public.pirep_airport_associations m
join public.v_pireps_active p
  on p.pirep_id = m.pirep_id
left join public.airports a
  on a.airport_id = m.airport_id;


-- ─── Grants ────────────────────────────────────────────────────────────────

grant select on public.taf_forecasts             to anon, authenticated;
grant select on public.taf_forecast_periods      to anon, authenticated;
grant select on public.pirep_reports             to anon, authenticated;
grant select on public.pirep_airport_associations to anon, authenticated;
grant select on public.v_taf_timeline_current    to anon, authenticated;
grant select on public.v_airport_taf_periods_active to anon, authenticated;
grant select on public.v_pireps_active           to anon, authenticated;
grant select on public.v_airport_pireps_active   to anon, authenticated;

grant select, insert, update, delete
  on public.taf_forecasts, public.taf_forecast_periods,
     public.pirep_reports, public.pirep_airport_associations
  to service_role;
