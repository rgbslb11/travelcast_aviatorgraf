-- ============================================================
-- TravelCast AviatorGraf Prep
-- 06_operational_intelligence.sql
-- ============================================================
-- PURPOSE
--   Adds the ATCSCC Operations Plan, Aviation Hazards, and
--   RouteCast tables plus all supporting views for the
--   Operational Intelligence layer of the TravelCast AviatorGraf
--   Prep application.
--
--   This file also REPLACES the two placeholder views created in
--   04_placeholder_views.sql:
--     v_aviation_hazards_latest  — now backed by aviation_hazard_products
--     v_routecast_routes         — now backed by routecast_routes
--
-- RUN ORDER
--   Run after 05_fix_source_health_freshness.sql.
--   Safe to rerun — all statements use CREATE TABLE IF NOT EXISTS
--   and CREATE OR REPLACE VIEW.  No destructive operations on
--   existing tables or views outside this file.
--
-- NEW TABLES
--   atcscc_operations_plans           — parsed ATCSCC daily ops plans
--   atcscc_operations_plan_sections   — parsed sections within each plan
--   aviation_hazard_products          — SIGMETs, AIRMETs, CWAs, PIREPs
--   routecast_routes                  — configured TravelCast broadcast routes
--
-- NEW / REPLACED VIEWS
--   v_atcscc_operations_plan_latest   — most recent ops plan row
--   v_atcscc_operations_plan_sections — sections for the latest plan
--   v_aviation_hazards_latest         — active hazards (REPLACES placeholder)
--   v_routecast_routes                — active routes joined to airports (REPLACES placeholder)
--   v_routecast_dashboard             — routes with live airport status from v_airport_status_dashboard
--
-- DOCTRINE LABELS (never alter)
--   Current Operational Impact — FAA NAS / ATCSCC
--   Forecast Weather Impact — NWS forecast proxy
--   Aviation Weather Truth — AviationWeather METAR/TAF
--   Commercial / Enrichment — Baron/OpenWeather/Synoptic/etc.
--   Graphics Output — TravelCast generated package
--
-- SECURITY
--   RLS enabled on all 4 new tables.  anon + authenticated roles
--   receive SELECT only.  Write operations (INSERT/UPDATE/DELETE)
--   are reserved for the service_role key used by backend pull
--   scripts — never exposed in browser code.
--
-- NO SECRETS IN THIS FILE
-- ============================================================


-- ============================================================
-- SECTION 1: TABLES
-- ============================================================

-- ──────────────────────────────────────────────────────────────
-- atcscc_operations_plans
-- One row per parsed ATCSCC daily operations plan.
-- Pull scripts populate this table; the view surfaces the latest.
-- parse_status values: ok | partial | failed | no_plan_found
-- ──────────────────────────────────────────────────────────────
create table if not exists atcscc_operations_plans (
  id               bigserial primary key,
  advisory_number  integer,
  advisory_date    date,
  title            text,
  event_time       text,          -- e.g. '0800Z-2000Z'
  raw_text         text,
  fetched_at_utc   timestamptz not null default now(),
  valid_from_utc   timestamptz,
  valid_until_utc  timestamptz,
  source_url       text,
  source_system_id text references source_systems(source_system_id),
  parse_status     text not null default 'ok',   -- ok|partial|failed|no_plan_found
  parse_warnings   text,
  unique (advisory_number, advisory_date)
);


-- ──────────────────────────────────────────────────────────────
-- atcscc_operations_plan_sections
-- One row per section within an ops plan (TERMINAL_ACTIVE, etc.).
-- section_key is a machine tag; section_display_name is UI copy.
-- translation is TravelCast plain-language summary for broadcast.
-- ──────────────────────────────────────────────────────────────
create table if not exists atcscc_operations_plan_sections (
  id                   bigserial primary key,
  plan_id              bigint references atcscc_operations_plans(id) on delete cascade,
  section_key          text,    -- e.g. 'TERMINAL_ACTIVE'
  section_display_name text,    -- e.g. 'Terminal Active'
  section_order        integer,
  raw_text             text,
  translation          text,    -- TravelCast plain-language summary
  has_content          boolean not null default false
);


-- ──────────────────────────────────────────────────────────────
-- aviation_hazard_products
-- SIGMETs, AIRMETs, CWAs, and PIREPs from AviationWeather.gov.
-- hazard_id is the canonical product identifier (e.g. 'SIGA05W').
-- Upsert on hazard_id so reruns from pull scripts stay idempotent.
-- parse_status values: ok | partial | failed
-- ──────────────────────────────────────────────────────────────
create table if not exists aviation_hazard_products (
  id                    bigserial primary key,
  hazard_id             text unique,          -- e.g. 'SIGA05W'
  hazard_type           text not null,        -- SIGMET|AIRMET|CWA|PIREP
  subtype               text,                 -- CONVECTIVE|ICE|TURB|IFR|MTN_OBSCN|LLWS|etc.
  raw_text              text,
  begins_at_utc         timestamptz,
  ends_at_utc           timestamptz,
  issued_at_utc         timestamptz,
  altitude_top_ft       integer,
  altitude_bottom_ft    integer,
  movement_from_degrees integer,
  movement_speed_kt     integer,
  hazard_summary        text,
  translation           text,                 -- TravelCast plain-language summary
  geometry_geojson      jsonb,
  affected_airports     text[],
  affected_regions      text[],
  source_url            text,
  source_system_id      text references source_systems(source_system_id),
  fetched_at_utc        timestamptz not null default now(),
  parse_status          text not null default 'ok',
  parse_warnings        text
);


-- ──────────────────────────────────────────────────────────────
-- routecast_routes
-- Configured TravelCast broadcast route pairs.
-- route_id is the primary key (e.g. 'DFW-JFK').
-- active=false hides a route from the dashboard without deleting.
-- sort_order controls display order in the RouteCast view.
-- ──────────────────────────────────────────────────────────────
create table if not exists routecast_routes (
  route_id               text primary key,        -- e.g. 'DFW-JFK'
  route_name             text not null,            -- e.g. 'DFW → JFK'
  origin_airport_id      text references airports(airport_id),
  destination_airport_id text references airports(airport_id),
  route_string           text,                     -- waypoints string, null OK for simple O/D
  active                 boolean not null default true,
  sort_order             integer not null default 0,
  notes                  text,
  created_at             timestamptz not null default now()
);


-- ============================================================
-- SECTION 2: INDEXES
-- ============================================================

create index if not exists idx_atcscc_plans_date
  on atcscc_operations_plans(advisory_date desc);

create index if not exists idx_hazards_type_time
  on aviation_hazard_products(hazard_type, begins_at_utc desc);

create index if not exists idx_hazards_ends
  on aviation_hazard_products(ends_at_utc);


-- ============================================================
-- SECTION 3: ROW LEVEL SECURITY
-- ============================================================
-- Enable RLS on all 4 new tables. anon and authenticated roles
-- receive SELECT only via the policies below.
-- service_role receives INSERT/UPDATE/DELETE for backend pull
-- scripts — the service-role key must never appear in browser code.

alter table atcscc_operations_plans enable row level security;
alter table atcscc_operations_plan_sections enable row level security;
alter table aviation_hazard_products enable row level security;
alter table routecast_routes enable row level security;

-- Drop before recreate so this block is safe to rerun.
do $$ begin
  drop policy if exists "tc_anon_read_atcscc_operations_plans"
    on atcscc_operations_plans;
  drop policy if exists "tc_anon_read_atcscc_operations_plan_sections"
    on atcscc_operations_plan_sections;
  drop policy if exists "tc_anon_read_aviation_hazard_products"
    on aviation_hazard_products;
  drop policy if exists "tc_anon_read_routecast_routes"
    on routecast_routes;
end $$;

create policy "tc_anon_read_atcscc_operations_plans"
  on atcscc_operations_plans for select
  to anon, authenticated
  using (true);

create policy "tc_anon_read_atcscc_operations_plan_sections"
  on atcscc_operations_plan_sections for select
  to anon, authenticated
  using (true);

create policy "tc_anon_read_aviation_hazard_products"
  on aviation_hazard_products for select
  to anon, authenticated
  using (true);

create policy "tc_anon_read_routecast_routes"
  on routecast_routes for select
  to anon, authenticated
  using (true);

-- Write grants for service_role (pull scripts only)
grant insert, update, delete on atcscc_operations_plans          to service_role;
grant insert, update, delete on atcscc_operations_plan_sections  to service_role;
grant insert, update, delete on aviation_hazard_products         to service_role;
grant insert, update, delete on routecast_routes                 to service_role;

grant usage, select on sequence atcscc_operations_plans_id_seq          to service_role;
grant usage, select on sequence atcscc_operations_plan_sections_id_seq  to service_role;
grant usage, select on sequence aviation_hazard_products_id_seq         to service_role;


-- ============================================================
-- SECTION 4: VIEWS
-- ============================================================

-- ──────────────────────────────────────────────────────────────
-- v_atcscc_operations_plan_latest
-- Most recent ATCSCC ops plan, ordered by advisory_date desc,
-- then id desc to break same-day ties.
-- Returns a single row (or zero rows if the table is empty).
-- Used by: ATCSCC / FAA Ops Plan panel.
-- ──────────────────────────────────────────────────────────────
create or replace view v_atcscc_operations_plan_latest as
select *
from atcscc_operations_plans
where id = (
  select id
  from atcscc_operations_plans
  order by advisory_date desc, id desc
  limit 1
);

grant select on v_atcscc_operations_plan_latest to anon, authenticated;


-- ──────────────────────────────────────────────────────────────
-- v_atcscc_operations_plan_sections
-- All sections for the latest ops plan, ordered by section_order.
-- Denormalised with plan header fields for frontend convenience.
-- Used by: ATCSCC / FAA Ops Plan detail panel.
-- ──────────────────────────────────────────────────────────────
create or replace view v_atcscc_operations_plan_sections as
select
  s.id,
  s.plan_id,
  s.section_key,
  s.section_display_name,
  s.section_order,
  s.raw_text,
  s.translation,
  s.has_content,
  p.advisory_number,
  p.advisory_date,
  p.title,
  p.event_time,
  p.source_url,
  p.fetched_at_utc
from atcscc_operations_plan_sections s
join atcscc_operations_plans p on p.id = s.plan_id
where p.id = (
  select id
  from atcscc_operations_plans
  order by advisory_date desc, id desc
  limit 1
)
order by s.section_order;

grant select on v_atcscc_operations_plan_sections to anon, authenticated;


-- ──────────────────────────────────────────────────────────────
-- v_aviation_hazards_latest  (REPLACES 04_placeholder_views.sql)
-- Active hazards from aviation_hazard_products.
-- A hazard is active when ends_at_utc is in the future or unset.
-- Ordered by hazard_type then begins_at_utc desc for deterministic
-- frontend rendering.
-- Source label: Aviation Weather Truth — AviationWeather METAR/TAF
-- ──────────────────────────────────────────────────────────────
create or replace view v_aviation_hazards_latest as
select *
from aviation_hazard_products
where ends_at_utc > now()
   or ends_at_utc is null
order by hazard_type, begins_at_utc desc;

grant select on v_aviation_hazards_latest to anon, authenticated;


-- ──────────────────────────────────────────────────────────────
-- v_routecast_routes  (REPLACES 04_placeholder_views.sql)
-- Active configured routes joined to airport display info.
-- Provides origin/destination display fields for the frontend
-- without requiring a second round-trip.
-- Used by: RouteCast configuration panel.
-- ──────────────────────────────────────────────────────────────
create or replace view v_routecast_routes as
select
  r.route_id,
  r.route_name,
  r.route_string,
  r.active,
  r.sort_order,
  r.notes,
  r.origin_airport_id,
  oa.iata          as origin_iata,
  oa.display_name  as origin_name,
  oa.city          as origin_city,
  r.destination_airport_id,
  da.iata          as destination_iata,
  da.display_name  as destination_name,
  da.city          as destination_city
from routecast_routes r
left join airports oa on oa.airport_id = r.origin_airport_id
left join airports da on da.airport_id = r.destination_airport_id
where r.active = true
order by r.sort_order, r.route_id;

grant select on v_routecast_routes to anon, authenticated;


-- ──────────────────────────────────────────────────────────────
-- v_routecast_dashboard
-- Active routes with live airport status from
-- v_airport_status_dashboard for both origin and destination.
--
-- route_impact_color — composite Red/Amber/Green across both ends:
--   Red   if either endpoint is Red
--   Amber if either endpoint is Amber (and neither is Red)
--   Green otherwise
--
-- prep_status — broadcast readiness signal:
--   Significant — Red route and at least one non-NORMAL endpoint
--   Elevated    — Red route (forecast only, no active event)
--   Monitor     — Amber route
--   Normal      — all Green
--
-- Source labels follow doctrine: labels come from underlying views.
-- Used by: RouteCast dashboard panel, graphics queue.
-- ──────────────────────────────────────────────────────────────
create or replace view v_routecast_dashboard as
select
  r.route_id,
  r.route_name,
  r.route_string,
  r.notes                           as route_notes,

  -- Origin
  r.origin_airport_id,
  o.iata                            as origin_iata,
  o.display_name                    as origin_name,
  o.city                            as origin_city,
  o.region                          as origin_region,
  os.current_delay_type             as origin_op_label,
  os.current_status_code            as origin_status_code,
  os.avg_delay_minutes              as origin_avg_delay,
  os.overall_impact_color           as origin_op_color,
  os.forecast_impact_color          as origin_fcst_color,
  os.forecast_impact_label          as origin_fcst_label,
  os.freshness_status               as origin_freshness,

  -- Destination
  r.destination_airport_id,
  d.iata                            as dest_iata,
  d.display_name                    as dest_name,
  d.city                            as dest_city,
  d.region                          as dest_region,
  ds.current_delay_type             as dest_op_label,
  ds.current_status_code            as dest_status_code,
  ds.avg_delay_minutes              as dest_avg_delay,
  ds.overall_impact_color           as dest_op_color,
  ds.forecast_impact_color          as dest_fcst_color,
  ds.forecast_impact_label          as dest_fcst_label,
  ds.freshness_status               as dest_freshness,

  -- Composite route impact color
  case
    when 'Red'   in (os.overall_impact_color, ds.overall_impact_color) then 'Red'
    when 'Amber' in (os.overall_impact_color, ds.overall_impact_color) then 'Amber'
    else 'Green'
  end                               as route_impact_color,

  -- Broadcast readiness / prep status
  case
    when 'Red' in (os.overall_impact_color, ds.overall_impact_color)
         and (
           coalesce(os.current_status_code, 'NORMAL') != 'NORMAL'
           or coalesce(ds.current_status_code, 'NORMAL') != 'NORMAL'
         )                          then 'Significant'
    when 'Red'   in (os.overall_impact_color, ds.overall_impact_color) then 'Elevated'
    when 'Amber' in (os.overall_impact_color, ds.overall_impact_color) then 'Monitor'
    else 'Normal'
  end                               as prep_status

from routecast_routes r
left join airports o                  on o.airport_id = r.origin_airport_id
left join airports d                  on d.airport_id = r.destination_airport_id
left join v_airport_status_dashboard os on os.airport_id = r.origin_airport_id
left join v_airport_status_dashboard ds on ds.airport_id = r.destination_airport_id
where r.active = true
order by r.sort_order, r.route_id;

grant select on v_routecast_dashboard to anon, authenticated;


-- ============================================================
-- SECTION 5: SEED — ROUTECAST ROUTES
-- ============================================================
-- Starter routes covering major TravelCast focus markets.
-- ON CONFLICT DO NOTHING so reruns are safe and manual edits
-- via the UI (future feature) are preserved.

insert into routecast_routes
  (route_id, route_name, origin_airport_id, destination_airport_id,
   route_string, active, sort_order, notes)
values
  ('DFW-JFK', 'DFW → JFK', 'KDFW', 'KJFK', null, true, 10,
   'Dallas Fort Worth to New York JFK'),
  ('DFW-ORD', 'DFW → ORD', 'KDFW', 'KORD', null, true, 20,
   'Dallas Fort Worth to Chicago O''Hare'),
  ('DFW-ATL', 'DFW → ATL', 'KDFW', 'KATL', null, true, 30,
   'Dallas Fort Worth to Atlanta'),
  ('SFO-ORD', 'SFO → ORD', 'KSFO', 'KORD', null, true, 40,
   'San Francisco to Chicago O''Hare'),
  ('JFK-MIA', 'JFK → MIA', 'KJFK', 'KMIA', null, true, 50,
   'New York JFK to Miami'),
  ('DEN-DTW', 'DEN → DTW', 'KDEN', 'KDTW', null, true, 60,
   'Denver to Detroit')
on conflict (route_id) do nothing;


-- ============================================================
-- SECTION 6: VERIFICATION QUERIES
-- ============================================================
-- Paste any of these into Supabase SQL Editor after running this
-- file to confirm correct setup.
--
-- -- 1. Confirm all 4 new tables exist
-- select tablename
-- from pg_tables
-- where schemaname = 'public'
--   and tablename in (
--     'atcscc_operations_plans',
--     'atcscc_operations_plan_sections',
--     'aviation_hazard_products',
--     'routecast_routes'
--   )
-- order by tablename;
-- -- Expected: 4 rows
--
-- -- 2. Confirm all 5 new / replaced views exist
-- select viewname
-- from pg_views
-- where schemaname = 'public'
--   and viewname in (
--     'v_atcscc_operations_plan_latest',
--     'v_atcscc_operations_plan_sections',
--     'v_aviation_hazards_latest',
--     'v_routecast_routes',
--     'v_routecast_dashboard'
--   )
-- order by viewname;
-- -- Expected: 5 rows
--
-- -- 3. Confirm 6 starter routes seeded
-- select route_id, route_name, origin_airport_id, destination_airport_id,
--        active, sort_order
-- from routecast_routes
-- order by sort_order;
-- -- Expected: 6 rows (DFW-JFK, DFW-ORD, DFW-ATL, SFO-ORD, JFK-MIA, DEN-DTW)
--
-- -- 4. RouteCast dashboard — should show 5 routes (DTW not in airports seed)
-- select route_id, route_name, origin_iata, dest_iata,
--        origin_op_color, dest_op_color,
--        route_impact_color, prep_status
-- from v_routecast_dashboard
-- order by sort_order;
--
-- -- 5. Hazards — empty result is expected until pull scripts run
-- select hazard_id, hazard_type, subtype, begins_at_utc, ends_at_utc
-- from v_aviation_hazards_latest
-- order by hazard_type;
-- -- Expected: 0 rows (no pull data yet) — empty state is correct
--
-- -- 6. Ops plan — empty result is expected until pull scripts run
-- select id, advisory_number, advisory_date, title, parse_status
-- from v_atcscc_operations_plan_latest;
-- -- Expected: 0 rows (no pull data yet) — empty state is correct
--
-- -- 7. RLS policy check — confirm anon-read policies exist
-- select tablename, policyname, roles
-- from pg_policies
-- where schemaname = 'public'
--   and tablename in (
--     'atcscc_operations_plans',
--     'atcscc_operations_plan_sections',
--     'aviation_hazard_products',
--     'routecast_routes'
--   )
-- order by tablename, policyname;
-- -- Expected: 4 rows, one policy per table, roles = {anon,authenticated}
-- ============================================================
