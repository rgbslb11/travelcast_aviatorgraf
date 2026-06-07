-- ============================================================
-- TravelCast AviatorGraf Prep
-- 03_add_detail_views.sql
-- ============================================================
-- PURPOSE
--   Add five new detail views used by Airport Detail panel,
--   RouteCast, and export pipeline.
--   Existing four views in 00_supabase_bootstrap.sql are preserved
--   and unchanged.
--
-- RUN ORDER
--   Run after 00_supabase_bootstrap.sql (and 01/02 if applicable).
--   Safe to rerun — all statements use CREATE OR REPLACE VIEW.
--
-- NEW VIEWS
--   v_airport_detail_current         — full detail row per active airport
--   v_airport_metar_latest           — METAR fields only, latest per airport
--   v_airport_taf_latest             — TAF fields only, latest per airport
--   v_airport_operational_events_latest — FAA/NAS operational fields only
--   v_airport_runway_context         — runway config and AAR only
--
-- DOCTRINE LABELS (never alter)
--   Current Operational Impact — FAA NAS Status
--   Aviation Weather Truth — AviationWeather.gov
--   Forecast Weather Impact — NWS forecast proxy
--   Graphics Output — TravelCast generated package
--
-- NO SECRETS IN THIS FILE
-- ============================================================


-- ──────────────────────────────────────────────────────────────
-- v_airport_detail_current
-- Full detail for a single airport's latest snapshot.
-- Combines all sources: FAA/NAS, METAR, TAF, NWS forecast.
-- Used by: Airport Detail panel, export pipeline.
-- ──────────────────────────────────────────────────────────────
create or replace view v_airport_detail_current as
select
  -- Airport identity
  a.airport_id,
  a.iata,
  a.icao,
  a.faa_lid,
  a.display_name,
  a.airport_name,
  a.city,
  a.state,
  a.country,
  a.region,
  a.timezone,
  a.latitude,
  a.longitude,
  a.elevation_ft,

  -- Current Operational Impact — FAA NAS Status
  s.current_delay_type,
  s.current_status_code,
  s.current_reason,
  s.avg_delay_minutes,
  s.max_delay_minutes,
  s.delay_summary,
  s.current_impact_color,
  s.arrival_runway,
  s.departure_runway,
  s.aar,

  -- Aviation Weather Truth — AviationWeather.gov
  s.metar_condition,
  s.flight_category,
  s.metar_wind,
  s.metar_visibility,
  s.metar_observed_at,
  s.taf_trend,
  s.taf_next_risk_window,

  -- Forecast Weather Impact — NWS forecast proxy
  s.sky_condition                   as dominant_sky_condition,
  s.high_temperature_f,
  s.low_temperature_f,
  s.forecast_impact_color,
  s.forecast_impact_label,
  s.forecast_impact_reasons,
  s.forecast_icon_id,
  s.forecast_icon_url,

  -- Composite
  coalesce(s.current_impact_color, s.forecast_impact_color, 'Gray')    as overall_impact_color,
  coalesce(s.current_delay_type, s.forecast_impact_label, 'Monitor')   as overall_impact_label,
  s.generated_at                    as last_updated_at,
  s.snapshot_source,
  s.freshness_status,
  coalesce(s.source_summary, 'TravelCast AviatorGraf Prep')            as source_summary

from airports a
left join lateral (
  select *
  from airport_status_snapshots x
  where x.airport_id = a.airport_id
  order by generated_at desc
  limit 1
) s on true
where a.active = true;

grant select on v_airport_detail_current to anon, authenticated;


-- ──────────────────────────────────────────────────────────────
-- v_airport_metar_latest
-- Aviation Weather Truth — AviationWeather.gov METAR fields only.
-- Used by: METAR tiles, broadcast weather cards.
-- ──────────────────────────────────────────────────────────────
create or replace view v_airport_metar_latest as
select
  a.airport_id,
  a.iata,
  a.icao,
  a.display_name,
  a.city,
  a.region,
  s.metar_condition,
  s.flight_category,
  s.metar_wind,
  s.metar_visibility,
  s.metar_observed_at,
  s.generated_at        as snapshot_at,
  s.freshness_status,
  'Aviation Weather Truth — AviationWeather.gov'::text as source_label

from airports a
left join lateral (
  select metar_condition, flight_category, metar_wind, metar_visibility,
         metar_observed_at, generated_at, freshness_status
  from airport_status_snapshots x
  where x.airport_id = a.airport_id
    and x.metar_condition is not null
  order by generated_at desc
  limit 1
) s on true
where a.active = true;

grant select on v_airport_metar_latest to anon, authenticated;


-- ──────────────────────────────────────────────────────────────
-- v_airport_taf_latest
-- Aviation Weather Truth — AviationWeather.gov TAF fields only.
-- Used by: TAF tiles, RouteCast trend cards.
-- ──────────────────────────────────────────────────────────────
create or replace view v_airport_taf_latest as
select
  a.airport_id,
  a.iata,
  a.icao,
  a.display_name,
  a.city,
  a.region,
  s.taf_trend,
  s.taf_next_risk_window,
  s.generated_at        as snapshot_at,
  s.freshness_status,
  'Aviation Weather Truth — AviationWeather.gov'::text as source_label

from airports a
left join lateral (
  select taf_trend, taf_next_risk_window, generated_at, freshness_status
  from airport_status_snapshots x
  where x.airport_id = a.airport_id
    and x.taf_trend is not null
  order by generated_at desc
  limit 1
) s on true
where a.active = true;

grant select on v_airport_taf_latest to anon, authenticated;


-- ──────────────────────────────────────────────────────────────
-- v_airport_operational_events_latest
-- Current Operational Impact — FAA NAS Status fields only.
-- Used by: Operational Impact tiles, ATCSCC events summary.
-- Shows all active airports, including those with no active event.
-- ──────────────────────────────────────────────────────────────
create or replace view v_airport_operational_events_latest as
select
  a.airport_id,
  a.iata,
  a.icao,
  a.display_name,
  a.city,
  a.region,
  coalesce(s.current_delay_type,  'None')   as current_delay_type,
  coalesce(s.current_status_code, 'NORMAL') as current_status_code,
  s.current_reason,
  s.avg_delay_minutes,
  s.max_delay_minutes,
  s.delay_summary,
  s.current_impact_color,
  s.generated_at                            as snapshot_at,
  s.freshness_status,
  'Current Operational Impact — FAA NAS Status'::text as source_label

from airports a
left join lateral (
  select current_delay_type, current_status_code, current_reason,
         avg_delay_minutes, max_delay_minutes, delay_summary,
         current_impact_color, generated_at, freshness_status
  from airport_status_snapshots x
  where x.airport_id = a.airport_id
  order by generated_at desc
  limit 1
) s on true
where a.active = true;

grant select on v_airport_operational_events_latest to anon, authenticated;


-- ──────────────────────────────────────────────────────────────
-- v_airport_runway_context
-- Runway configuration and AAR from latest FAA snapshot.
-- Used by: Airport Detail runway section, RouteCast capacity context.
-- ──────────────────────────────────────────────────────────────
create or replace view v_airport_runway_context as
select
  a.airport_id,
  a.iata,
  a.icao,
  a.display_name,
  a.city,
  a.region,
  a.elevation_ft,
  s.arrival_runway,
  s.departure_runway,
  s.aar,
  s.current_status_code,
  s.generated_at                            as snapshot_at,
  s.freshness_status,
  'Current Operational Impact — FAA NAS Status'::text as source_label

from airports a
left join lateral (
  select arrival_runway, departure_runway, aar, current_status_code,
         generated_at, freshness_status
  from airport_status_snapshots x
  where x.airport_id = a.airport_id
  order by generated_at desc
  limit 1
) s on true
where a.active = true;

grant select on v_airport_runway_context to anon, authenticated;


-- ──────────────────────────────────────────────────────────────
-- Verify new views are accessible
-- ──────────────────────────────────────────────────────────────
select
  schemaname,
  viewname
from pg_views
where schemaname = 'public'
  and viewname like 'v_%'
order by viewname;
