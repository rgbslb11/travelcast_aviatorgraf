-- ============================================================
-- TravelCast AviatorGraf Prep
-- 04_placeholder_views.sql
-- ============================================================
-- PURPOSE
--   Create placeholder views for features not yet implemented.
--   Views are valid PostgREST targets but always return zero rows
--   (WHERE false) until the underlying tables and pull scripts
--   are built.
--
--   ATCSCC/FAA Ops uses the existing v_airport_operational_events_latest
--   view (from 03_add_detail_views.sql) — no new view needed there.
--
-- RUN ORDER
--   Run after 03_add_detail_views.sql.
--   Safe to rerun — all statements use CREATE OR REPLACE VIEW.
--
-- NO SECRETS IN THIS FILE
-- ============================================================


-- ──────────────────────────────────────────────────────────────
-- v_aviation_hazards_latest
-- Placeholder for SIGMETs, AIRMETs, CWAs, and PIREPs.
-- Always empty until a hazards table and pull script are built.
-- Frontend queries this view; empty result = honest empty-state.
-- ──────────────────────────────────────────────────────────────
create or replace view v_aviation_hazards_latest as
select
  null::text        as hazard_id,
  null::text        as hazard_type,
  null::text        as affected_area,
  null::timestamptz as valid_from,
  null::timestamptz as valid_to,
  null::text        as flight_levels,
  null::text        as movement,
  null::text        as hazard_text,
  'Aviation Weather Truth — AviationWeather.gov'::text as source_label
where false;

grant select on v_aviation_hazards_latest to anon, authenticated;


-- ──────────────────────────────────────────────────────────────
-- v_routecast_routes
-- Placeholder for configured TravelCast broadcast routes.
-- Always empty until a routes table and configuration UI are built.
-- Frontend queries this view; empty result = honest empty-state.
-- ──────────────────────────────────────────────────────────────
create or replace view v_routecast_routes as
select
  null::text        as route_id,
  null::text        as origin_iata,
  null::text        as destination_iata,
  null::text        as label,
  null::text        as overall_impact_color,
  null::text        as overall_impact_label,
  null::text        as impact_summary,
  null::text        as route_string,
  null::timestamptz as estimated_departure,
  null::text        as source
where false;

grant select on v_routecast_routes to anon, authenticated;


-- ──────────────────────────────────────────────────────────────
-- Verify
-- ──────────────────────────────────────────────────────────────
select schemaname, viewname
from pg_views
where schemaname = 'public'
  and viewname in (
    'v_aviation_hazards_latest',
    'v_routecast_routes',
    'v_airport_operational_events_latest'
  )
order by viewname;
