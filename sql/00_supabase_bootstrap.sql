-- ============================================================
-- TravelCast AviatorGraf Prep
-- 00_supabase_bootstrap.sql
-- ============================================================
-- PURPOSE
--   First and only SQL file to paste into Supabase SQL Editor
--   for initial setup. Creates all base tables, indexes, RLS,
--   views, function, and demo seed data.
--
-- RUN ORDER
--   Paste the entire file into Supabase SQL Editor and click Run.
--   This file is idempotent — safe to rerun.
--
-- AFTER THIS FILE
--   sql/live_views.sql   — upgrade path once separate METAR/TAF
--                          observation tables are populated by pull scripts
--   sql/functions_airport_impact.sql — already merged below
--   sql/sample_seed_airports.sql     — already merged below
--
-- SECURITY NOTE
--   RLS is enabled on all base tables. The policies below grant
--   the anon and authenticated roles SELECT access only — suitable
--   for local frontend testing with a public anon key.
--
--   BEFORE PUBLIC HOSTING: replace the permissive `USING (true)`
--   policies with conditions appropriate to your access model.
--   Never grant INSERT/UPDATE/DELETE to anon from the frontend.
--   Write operations must happen only through backend scripts
--   authenticated with the service-role key, which must never
--   appear in browser code.
--
-- NO SECRETS IN THIS FILE
--   No API keys, service-role keys, or private credentials.
-- ============================================================


-- ============================================================
-- SECTION 1: HELPER FUNCTION
-- ============================================================

create or replace function travelcast_impact_rank(color text)
returns integer language sql immutable as $$
  select case
    when lower(coalesce(color, '')) like '%red%'   then 3
    when lower(coalesce(color, '')) like '%amber%' then 2
    when lower(coalesce(color, '')) like '%green%' then 1
    else 0
  end;
$$;


-- ============================================================
-- SECTION 2: BASE TABLES
-- ============================================================

-- Source systems registry
-- Stores trust tier and operational role for every data source.
create table if not exists source_systems (
  source_system_id          text primary key,
  display_name              text not null,
  trust_tier                integer not null default 3,  -- 1=official, 2=enrichment, 3=commercial
  official_source           boolean not null default false,
  mission_critical_allowed  boolean not null default false,
  category                  text,
  notes                     text,
  created_at                timestamptz not null default now()
);

-- Airport reference table
-- Static or slow-changing metadata for each airport.
create table if not exists airports (
  airport_id    text primary key,        -- ICAO code, e.g. 'KDEN'
  iata          text,
  icao          text,
  faa_lid       text,
  display_name  text,
  airport_name  text,
  city          text,
  state         text,
  country       text not null default 'US',
  region        text,
  timezone      text,
  latitude      numeric(9, 6),
  longitude     numeric(9, 6),
  elevation_ft  integer,
  active        boolean not null default true,
  created_at    timestamptz not null default now()
);

-- Airport status snapshots
-- One row per pull cycle per airport. Views read the latest row.
-- Carries METAR/TAF as snapshot fields so the view works without
-- separate observation tables. Pull scripts populate these after
-- fetching from AviationWeather.gov and FAA NAS Status.
-- snapshot_source = 'demo'  for seed rows (DELETE+reinsert on rerun)
-- snapshot_source = 'live'  for rows written by pull scripts
create table if not exists airport_status_snapshots (
  id                    bigserial primary key,
  airport_id            text not null references airports(airport_id),
  snapshot_source       text not null default 'live',
  generated_at          timestamptz not null default now(),
  freshness_status      text not null default 'fresh',  -- fresh|aging|stale|unknown

  -- Sky / NWS forecast impact
  sky_condition         text,                 -- dominant_sky_condition in view
  high_temperature_f    integer,
  low_temperature_f     integer,
  forecast_impact_color text,                 -- Red|Amber|Green|Gray
  forecast_impact_label text,
  forecast_impact_reasons text,
  forecast_icon_id      text,                 -- canonical icon ID, e.g. '04'
  forecast_icon_url     text,

  -- FAA NAS / ATCSCC operational status
  current_delay_type    text,                 -- 'Ground Delay Program' | 'Departure Delay' | 'Airport Closure' | 'None'
  current_status_code   text,                 -- 'GROUND_DELAY_PROGRAM' | 'DELAY' | 'CLOSURE' | 'NORMAL'
  current_reason        text,
  avg_delay_minutes     integer,
  max_delay_minutes     integer,
  delay_summary         text,
  arrival_runway        text,
  departure_runway      text,
  aar                   integer,              -- Airport Arrival Rate
  current_impact_color  text,                 -- operational impact color

  -- METAR snapshot (from AviationWeather.gov pull)
  metar_condition       text,
  flight_category       text,                 -- VFR|MVFR|IFR|LIFR
  metar_wind            text,
  metar_visibility      text,
  metar_observed_at     timestamptz,

  -- TAF snapshot
  taf_trend             text,
  taf_next_risk_window  text,

  -- Composite
  source_summary        text
);


-- Feed run log
-- One row per pull script execution. Powers v_source_health_dashboard.
create table if not exists feed_runs (
  id                  bigserial primary key,
  source_system_id    text not null references source_systems(source_system_id),
  retrieved_at_utc    timestamptz not null default now(),
  live_fetch_success  boolean not null default false,
  records_retrieved   integer,
  error               text
);


-- Weather icon assets
-- Canonical icon IDs referenced by airport_status_snapshots.forecast_icon_id.
create table if not exists weather_icon_assets (
  icon_id     text primary key,
  label       text not null,
  description text,
  night_variant boolean not null default false,
  url         text
);


-- ============================================================
-- SECTION 3: INDEXES
-- ============================================================

-- Efficient latest-snapshot lookup per airport
create index if not exists idx_snapshots_airport_generated
  on airport_status_snapshots(airport_id, generated_at desc);

-- Feed run lookup by source
create index if not exists idx_feed_runs_source_time
  on feed_runs(source_system_id, retrieved_at_utc desc);

-- IATA lookups
create index if not exists idx_airports_iata
  on airports(iata);


-- ============================================================
-- SECTION 4: ROW LEVEL SECURITY
-- ============================================================
-- Enable RLS on all base tables. Only SELECT is granted to
-- anon / authenticated. Write operations require the service-role
-- key and must happen in backend scripts only.
--
-- WARNING: `USING (true)` allows all rows to be read by anyone
-- with the anon key. For a public-facing deployment this is
-- acceptable for read-only aviation data. Tighten as needed.

alter table source_systems enable row level security;
alter table airports enable row level security;
alter table airport_status_snapshots enable row level security;
alter table feed_runs enable row level security;
alter table weather_icon_assets enable row level security;

-- Drop existing policies before recreating so this block is
-- safe to rerun.
do $$ begin
  drop policy if exists "tc_anon_read_source_systems"           on source_systems;
  drop policy if exists "tc_anon_read_airports"                 on airports;
  drop policy if exists "tc_anon_read_airport_status_snapshots" on airport_status_snapshots;
  drop policy if exists "tc_anon_read_feed_runs"                on feed_runs;
  drop policy if exists "tc_anon_read_weather_icon_assets"      on weather_icon_assets;
end $$;

create policy "tc_anon_read_source_systems"
  on source_systems for select
  to anon, authenticated
  using (true);

create policy "tc_anon_read_airports"
  on airports for select
  to anon, authenticated
  using (true);

create policy "tc_anon_read_airport_status_snapshots"
  on airport_status_snapshots for select
  to anon, authenticated
  using (true);

create policy "tc_anon_read_feed_runs"
  on feed_runs for select
  to anon, authenticated
  using (true);

create policy "tc_anon_read_weather_icon_assets"
  on weather_icon_assets for select
  to anon, authenticated
  using (true);


-- ============================================================
-- SECTION 5: VIEWS
-- ============================================================
-- Frontend reads these views, not raw tables.
-- Grant SELECT on views explicitly so PostgREST can expose them.

-- Primary dashboard view: one row per active airport, latest snapshot.
create or replace view v_airport_status_dashboard as
select
  a.airport_id,
  a.iata,
  a.icao,
  a.region,
  a.display_name,
  a.airport_name,
  a.city,
  a.state,
  a.latitude,
  a.longitude,
  s.sky_condition                                               as dominant_sky_condition,
  s.high_temperature_f,
  s.low_temperature_f,
  s.forecast_impact_color,
  s.forecast_impact_label,
  s.forecast_impact_reasons,
  s.forecast_icon_id,
  s.forecast_icon_url,
  s.current_delay_type,
  s.current_status_code,
  s.current_reason,
  s.avg_delay_minutes,
  s.max_delay_minutes,
  s.delay_summary,
  s.arrival_runway,
  s.departure_runway,
  s.aar,
  s.metar_condition,
  s.flight_category,
  s.metar_wind,
  s.metar_visibility,
  s.metar_observed_at,
  s.taf_trend,
  s.taf_next_risk_window,
  coalesce(s.current_impact_color, s.forecast_impact_color, 'Gray')   as overall_impact_color,
  coalesce(s.current_delay_type,   s.forecast_impact_label, 'Monitor') as overall_impact_label,
  s.generated_at                                                as last_updated_at,
  s.freshness_status,
  coalesce(s.source_summary, 'TravelCast AviatorGraf Prep')    as source_summary
from airports a
left join lateral (
  select *
  from airport_status_snapshots x
  where x.airport_id = a.airport_id
  order by generated_at desc
  limit 1
) s on true
where a.active = true;

grant select on v_airport_status_dashboard to anon, authenticated;


-- Source health view: one row per source system with latest feed run stats.
create or replace view v_source_health_dashboard as
select
  s.source_system_id,
  s.display_name,
  s.trust_tier,
  s.official_source,
  s.mission_critical_allowed,
  s.category,
  s.notes,
  max(f.retrieved_at_utc)                                               as latest_feed_run,
  max(f.retrieved_at_utc) filter (where f.live_fetch_success = true)   as last_success_at,
  max(f.error)            filter (where f.live_fetch_success = false)   as last_error,
  count(*)                filter (where f.retrieved_at_utc > now() - interval '24 hours') as runs_last_24h,
  case
    when max(f.retrieved_at_utc) > now() - interval '30 minutes' then 'fresh'
    when max(f.retrieved_at_utc) is null                          then 'no_runs'
    else 'unknown'
  end as freshness_status
from source_systems s
left join feed_runs f on f.source_system_id = s.source_system_id
group by
  s.source_system_id, s.display_name, s.trust_tier, s.official_source,
  s.mission_critical_allowed, s.category, s.notes;

grant select on v_source_health_dashboard to anon, authenticated;


-- Broadcast card view: pre-formatted graphics copy derived from dashboard view.
create or replace view v_airport_broadcast_cards as
select
  airport_id,
  coalesce(iata, airport_id)                                                      as airport_code,
  concat(coalesce(iata, airport_id), ' ', coalesce(current_delay_type, forecast_impact_label, 'Monitor'))
                                                                                   as headline,
  coalesce(current_reason, forecast_impact_reasons, dominant_sky_condition, '—')  as subheadline,
  concat(coalesce(iata, airport_id), ' — ', coalesce(current_delay_type, forecast_impact_label, 'Monitor'))
                                                                                   as lower_third,
  concat(
    coalesce(airport_name, display_name, airport_id), ': ',
    coalesce(current_reason, forecast_impact_reasons, 'TravelCast monitoring.')
  )                                                                                as long_card_text,
  overall_impact_color                                                             as impact_color,
  source_summary                                                                   as source_footer,
  'airport_status_card'::text                                                      as recommended_layout,
  (last_updated_at + interval '10 minutes')                                        as valid_until,
  (freshness_status = 'fresh')                                                     as broadcast_ready_boolean
from v_airport_status_dashboard;

grant select on v_airport_broadcast_cards to anon, authenticated;


-- Graphics queue candidates: red/amber airports prioritized by impact.
create or replace view v_graphics_queue_candidates as
select
  airport_id,
  iata,
  airport_name,
  case
    when lower(coalesce(overall_impact_color,  '')) = 'red'   then 'Current red impact'
    when lower(coalesce(forecast_impact_color, '')) = 'amber' then 'Forecast weather impact'
    else 'Monitor'
  end                                                         as candidate_reason,
  travelcast_impact_rank(overall_impact_color)                as priority_score,
  'airport_status_card'::text                                 as recommended_product_type,
  freshness_status
from v_airport_status_dashboard
where lower(coalesce(overall_impact_color,  '')) in ('red', 'amber')
   or lower(coalesce(forecast_impact_color, '')) in ('red', 'amber');

grant select on v_graphics_queue_candidates to anon, authenticated;


-- ============================================================
-- SECTION 6: SEED — SOURCE SYSTEMS
-- ============================================================

insert into source_systems
  (source_system_id, display_name, trust_tier, official_source, mission_critical_allowed, category, notes)
values
  ('faa_nas_status',
   'FAA NAS Status',
   1, true, true,
   'traffic_management',
   'Operational traffic-management truth. Airport events, GDPs, ground stops, closures.'),
  ('atcscc_advisories',
   'FAA ATCSCC Advisories',
   1, true, true,
   'traffic_management',
   'Operations plans, terminal/enroute planned events, SWAP/CDR/capping/tunneling context.'),
  ('aviationweather_api',
   'AviationWeather.gov API',
   1, true, true,
   'aviation_weather',
   'METAR, TAF, PIREP, AIRMET/SIGMET, CWA. Aviation weather truth.'),
  ('nws_api',
   'NWS API / api.weather.gov',
   1, true, true,
   'public_weather',
   'Public forecasts, alerts, CAP/WEA, grid forecast. Used as forecast-impact proxy only — not an official FAA delay forecast.'),
  ('baron_weather_api',
   'Baron Weather API',
   3, false, false,
   'commercial_enrichment',
   'Commercial enrichment and archive only. Not FAA/NWS operational truth.'),
  ('open_meteo',
   'Open-Meteo',
   2, false, false,
   'enrichment',
   'Open-source weather API. Enrichment and development use only.'),
  ('synoptic_data',
   'Synoptic Data / Mesonet',
   2, false, false,
   'enrichment',
   'Observation network. Enrichment and archive use only.')
on conflict (source_system_id) do update set
  display_name             = excluded.display_name,
  trust_tier               = excluded.trust_tier,
  official_source          = excluded.official_source,
  mission_critical_allowed = excluded.mission_critical_allowed,
  category                 = excluded.category,
  notes                    = excluded.notes;


-- ============================================================
-- SECTION 7: SEED — WEATHER ICON ASSETS
-- ============================================================
-- Canonical icon IDs used in demo and live data.
-- icon_id matches forecast_icon_id in airport_status_snapshots.

insert into weather_icon_assets (icon_id, label, description)
values
  ('04',  'Thunderstorms',           'Thunderstorms. Icon 04 is the canonical severe-convection ID.'),
  ('11',  'Showers',                 'Showers / rain showers.'),
  ('26',  'Low Clouds',              'Overcast or broken low clouds. IFR/MVFR risk.'),
  ('30',  'Partly Cloudy',           'Partly cloudy sky conditions.'),
  ('32',  'Sunny',                   'Clear or mostly clear.'),
  ('34',  'Mostly Sunny',            'Mostly clear, few clouds.'),
  ('38',  'Scattered Thunderstorms', 'Scattered convective activity.'),
  ('39',  'Chance Showers',          'Chance of showers, not widespread.'),
  ('na',  'Not Available',           'No icon available or condition undetermined.')
on conflict (icon_id) do update set
  label       = excluded.label,
  description = excluded.description;


-- ============================================================
-- SECTION 8: SEED — AIRPORTS
-- ============================================================

insert into airports
  (airport_id, iata, icao, faa_lid, display_name, airport_name,
   city, state, country, region, timezone, latitude, longitude, elevation_ft, active)
values
  ('KDEN','DEN','KDEN','DEN','Denver','Denver International Airport',
   'Denver','CO','US','Rocky Mountains','America/Denver',39.8561,-104.6737,5434,true),
  ('KDFW','DFW','KDFW','DFW','Dallas/Fort Worth','Dallas Fort Worth International Airport',
   'Dallas','TX','US','Southern Plains','America/Chicago',32.8998,-97.0403,607,true),
  ('KATL','ATL','KATL','ATL','Atlanta','Hartsfield-Jackson Atlanta International Airport',
   'Atlanta','GA','US','Southeast','America/New_York',33.6367,-84.4281,1026,true),
  ('KMIA','MIA','KMIA','MIA','Miami','Miami International Airport',
   'Miami','FL','US','Florida','America/New_York',25.7959,-80.2870,8,true),
  ('KSFO','SFO','KSFO','SFO','San Francisco','San Francisco International Airport',
   'San Francisco','CA','US','West Coast','America/Los_Angeles',37.6213,-122.3790,13,true),
  ('KLAS','LAS','KLAS','LAS','Las Vegas','Harry Reid International Airport',
   'Las Vegas','NV','US','Desert Southwest','America/Los_Angeles',36.0840,-115.1537,2181,true),
  ('KLAX','LAX','KLAX','LAX','Los Angeles','Los Angeles International Airport',
   'Los Angeles','CA','US','West Coast','America/Los_Angeles',33.9416,-118.4085,128,true),
  ('KJFK','JFK','KJFK','JFK','New York JFK','John F. Kennedy International Airport',
   'New York','NY','US','Northeast','America/New_York',40.6413,-73.7781,13,true),
  ('KORD','ORD','KORD','ORD','Chicago O''Hare','Chicago O''Hare International Airport',
   'Chicago','IL','US','Great Lakes','America/Chicago',41.9742,-87.9073,672,true),
  ('KIAH','IAH','KIAH','IAH','Houston Intercontinental','George Bush Intercontinental Airport',
   'Houston','TX','US','Southern Plains','America/Chicago',29.9902,-95.3368,97,true)
on conflict (airport_id) do update set
  airport_name = excluded.airport_name,
  display_name = excluded.display_name,
  region       = excluded.region,
  timezone     = excluded.timezone,
  active       = excluded.active;


-- ============================================================
-- SECTION 9: SEED — DEMO AIRPORT STATUS SNAPSHOTS
-- ============================================================
-- Delete existing demo rows then reinsert so rerunning stays clean.
-- Live pull scripts write snapshot_source = 'live' rows and are
-- unaffected by this block.

delete from airport_status_snapshots where snapshot_source = 'demo';

insert into airport_status_snapshots (
  airport_id, snapshot_source, generated_at, freshness_status,
  sky_condition, high_temperature_f, low_temperature_f,
  forecast_impact_color, forecast_impact_label, forecast_impact_reasons,
  forecast_icon_id, forecast_icon_url,
  current_delay_type, current_status_code, current_reason,
  avg_delay_minutes, max_delay_minutes, delay_summary,
  arrival_runway, departure_runway, aar, current_impact_color,
  metar_condition, flight_category, metar_wind, metar_visibility, metar_observed_at,
  taf_trend, taf_next_risk_window,
  source_summary
)
values

-- DEN — Ground Delay Program / Thunderstorms
-- Matches ACCEPTANCE_CRITERIA.md: GDP, 63 min avg, 386 max, 16L/16R/17R, icon 04, Red
(
  'KDEN', 'demo', now(), 'fresh',
  'Thunderstorms', 74, 52,
  'Red', 'Major Issues Possible', 'Thunderstorms may reduce arrival throughput.',
  '04', '',
  'Ground Delay Program', 'GROUND_DELAY_PROGRAM', 'Weather / Thunderstorms',
  63, 386, 'GDP active. Avg delay 63 min, maximum delay 386 min.',
  '16L/16R/17R', '', 64, 'Red',
  'TSRA', 'IFR', '22015G28KT', '3SM', '2026-06-06T22:10:00Z',
  'Thunderstorms possible this evening', '2100Z-0300Z',
  'Current Operational Impact — FAA NAS Status; Forecast Weather Impact — NWS forecast proxy; Aviation Weather Truth — AviationWeather METAR/TAF'
),

-- DFW — Normal / Amber forecast
(
  'KDFW', 'demo', now(), 'fresh',
  'Partly Cloudy', 88, 70,
  'Amber', 'Monitor', 'Scattered storms possible near terminal airspace.',
  '30', '',
  'None', 'NORMAL', 'No active FAA/NAS event in demo data',
  null, null, 'No active operational impact in demo data.',
  '18R/17C', '18L/17R', 92, null,
  'VFR', 'VFR', '17012KT', '10SM', '2026-06-06T22:10:00Z',
  'VFR, thunder risk later', 'After 2300Z',
  'Forecast Weather Impact — NWS forecast proxy'
),

-- ATL — Normal / Amber forecast
(
  'KATL', 'demo', now(), 'fresh',
  'Scattered Thunderstorms', 84, 68,
  'Amber', 'Possible Delays', 'Thunderstorm language in forecast.',
  '38', '',
  'None', 'NORMAL', 'No active FAA/NAS event in demo data',
  null, null, 'No active operational impact in demo data.',
  '', '', null, null,
  'VFR', 'VFR', '21008KT', '10SM', '2026-06-06T22:10:00Z',
  'VCTS possible', 'Evening',
  'Forecast Weather Impact — NWS forecast proxy'
),

-- MIA — Departure Delay / volume
(
  'KMIA', 'demo', now(), 'fresh',
  'Showers', 86, 76,
  'Amber', 'Monitor', 'Showers and tropical moisture may affect throughput.',
  '11', '',
  'Departure Delay', 'DELAY', 'Volume / Multi-taxi',
  15, 30, 'Departure delay avg 15 min in demo data.',
  '09/12', '08R/12', 44, 'Amber',
  'SHRA', 'MVFR', '10014KT', '6SM', '2026-06-06T22:10:00Z',
  'Showers nearby', 'All afternoon',
  'Current Operational Impact — FAA NAS Status'
),

-- SFO — Ground Delay Program / Low ceiling
(
  'KSFO', 'demo', now(), 'fresh',
  'Low Clouds', 62, 54,
  'Amber', 'Ceiling Monitor', 'Low clouds/ceilings possible.',
  '26', '',
  'Ground Delay Program', 'GROUND_DELAY_PROGRAM', 'Other / Low ceiling demo context',
  65, 120, 'GDP demo record.',
  '28L/28R', '28L/28R', 36, 'Red',
  'BKN008', 'IFR', '28012KT', '8SM', '2026-06-06T22:10:00Z',
  'Low clouds', 'Morning/evening',
  'Current Operational Impact — FAA NAS Status'
),

-- LAS — Airport Closure (GA restriction) / Green forecast
(
  'KLAS', 'demo', now(), 'fresh',
  'Sunny', 98, 76,
  'Green', 'Good', 'No major weather-impact language detected.',
  '32', '',
  'Airport Closure', 'CLOSURE', 'GA restriction demo freeform',
  null, null, 'Closed to non-scheduled transient GA except PPR in demo data.',
  '19R/26L', '19L/26R', 56, 'Red',
  'VFR', 'VFR', '19010KT', '10SM', '2026-06-06T22:10:00Z',
  'VFR', 'None',
  'Current Operational Impact — FAA NAS Status'
),

-- LAX — Airport Closure (GA restriction) / Green forecast
(
  'KLAX', 'demo', now(), 'fresh',
  'Partly Cloudy', 70, 60,
  'Green', 'Good', 'No major weather-impact language detected.',
  '30', '',
  'Airport Closure', 'CLOSURE', 'GA restriction demo freeform',
  null, null, 'Closed to non-scheduled transient GA except PPR in demo data.',
  '25L/24R', '25R/24L', 66, 'Red',
  'VFR', 'VFR', '25009KT', '10SM', '2026-06-06T22:10:00Z',
  'VFR', 'None',
  'Current Operational Impact — FAA NAS Status'
),

-- JFK — Normal / Amber forecast
(
  'KJFK', 'demo', now(), 'fresh',
  'Chance Showers', 72, 58,
  'Amber', 'Monitor', 'Chance of showers may affect arrival spacing.',
  '39', '',
  'None', 'NORMAL', 'No active FAA/NAS event in demo data',
  null, null, 'No active operational impact in demo data.',
  '', '', null, null,
  'VFR', 'VFR', '18012KT', '10SM', '2026-06-06T22:10:00Z',
  'Showers possible', 'Afternoon',
  'Forecast Weather Impact — NWS forecast proxy'
),

-- ORD — Normal / Green forecast
(
  'KORD', 'demo', now(), 'fresh',
  'Mostly Sunny', 76, 55,
  'Green', 'Good', 'No major weather-impact language detected.',
  '34', '',
  'None', 'NORMAL', 'No active FAA/NAS event in demo data',
  null, null, 'No active operational impact in demo data.',
  '', '', null, null,
  'VFR', 'VFR', '27010KT', '10SM', '2026-06-06T22:10:00Z',
  'VFR', 'None',
  'Forecast Weather Impact — NWS forecast proxy'
),

-- IAH — Normal / Amber forecast
(
  'KIAH', 'demo', now(), 'fresh',
  'Thunderstorms Possible', 90, 74,
  'Amber', 'Possible Delays', 'Thunderstorm potential in terminal area.',
  '38', '',
  'None', 'NORMAL', 'No active FAA/NAS event in demo data',
  null, null, 'No active operational impact in demo data.',
  '', '', null, null,
  'VFR', 'VFR', '16012KT', '10SM', '2026-06-06T22:10:00Z',
  'VCTS later', 'Evening',
  'Forecast Weather Impact — NWS forecast proxy'
);


-- ============================================================
-- SECTION 10: VERIFICATION QUERY
-- ============================================================
-- Run this after applying the file to confirm all 10 airports
-- are visible through the view.
--
-- select iata, current_delay_type, avg_delay_minutes,
--        max_delay_minutes, arrival_runway, forecast_icon_id,
--        overall_impact_color, freshness_status
-- from v_airport_status_dashboard
-- order by iata;
--
-- Expected: 10 rows. DEN row shows:
--   current_delay_type = 'Ground Delay Program'
--   avg_delay_minutes  = 63
--   max_delay_minutes  = 386
--   arrival_runway     = '16L/16R/17R'
--   forecast_icon_id   = '04'
--   overall_impact_color = 'Red'
-- ============================================================
