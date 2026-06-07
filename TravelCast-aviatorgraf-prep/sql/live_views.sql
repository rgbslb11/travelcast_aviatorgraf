-- TravelCast AviatorGraf Prep live views.
-- These views expect the broader TravelCast ontology tables to exist.

create or replace view v_airport_metar_latest as
select distinct on (airport_id)
  airport_id,
  raw_metar,
  observed_at,
  flight_category,
  weather_tokens,
  wind_direction_deg,
  wind_speed_kt,
  wind_gust_kt,
  visibility_sm,
  ceiling_ft,
  canonical_condition,
  icon_id
from airport_metar_observations
order by airport_id, observed_at desc;

create or replace view v_airport_operational_events_latest as
select distinct on (airport_id)
  *
from airport_operational_events
where is_active = true
order by airport_id, created_at desc;

create or replace view v_airport_taf_latest as
select distinct on (airport_id)
  *
from airport_taf_forecasts
order by airport_id, issued_at desc;

create or replace view v_airport_taf_timeline as
select *
from airport_taf_forecast_periods
order by airport_id, valid_start;

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
  s.sky_condition as dominant_sky_condition,
  s.high_temperature_f,
  s.low_temperature_f,
  s.forecast_impact_color,
  s.forecast_impact_label,
  s.forecast_impact_reasons,
  s.forecast_icon_id,
  s.forecast_icon_url,
  s.current_impact_label as current_delay_type,
  null::text as current_status_code,
  s.current_reason,
  s.current_delay_minutes as avg_delay_minutes,
  null::integer as max_delay_minutes,
  null::text as delay_summary,
  null::text as arrival_runway,
  null::text as departure_runway,
  null::integer as aar,
  m.canonical_condition as metar_condition,
  m.flight_category,
  concat(coalesce(m.wind_direction_deg::text,'VRB'), '/', coalesce(m.wind_speed_kt::text,'?'), 'KT') as metar_wind,
  m.visibility_sm::text as metar_visibility,
  m.observed_at as metar_observed_at,
  null::text as taf_trend,
  null::text as taf_next_risk_window,
  coalesce(s.current_impact_color, s.forecast_impact_color, 'Gray') as overall_impact_color,
  coalesce(s.current_impact_label, s.forecast_impact_label, 'Monitor') as overall_impact_label,
  s.generated_at as last_updated_at,
  s.freshness_status,
  'TravelCast generated view'::text as source_summary
from airports a
left join lateral (
  select * from airport_status_snapshots x where x.airport_id = a.airport_id order by generated_at desc limit 1
) s on true
left join v_airport_metar_latest m on m.airport_id = a.airport_id
where a.active = true;

create or replace view v_airport_broadcast_cards as
select
  airport_id,
  coalesce(iata, airport_id) as airport_code,
  concat(coalesce(iata, airport_id), ' ', coalesce(current_delay_type, forecast_impact_label, 'Monitor')) as headline,
  coalesce(current_reason, forecast_impact_reasons, dominant_sky_condition) as subheadline,
  concat(coalesce(iata, airport_id), ' — ', coalesce(current_delay_type, forecast_impact_label, 'Monitor')) as lower_third,
  concat(coalesce(airport_name, display_name), ': ', coalesce(current_reason, forecast_impact_reasons, 'TravelCast monitoring.')) as long_card_text,
  overall_impact_color as impact_color,
  source_summary as source_footer,
  'airport_status_card'::text as recommended_layout,
  (last_updated_at + interval '10 minutes') as valid_until,
  freshness_status = 'fresh' as broadcast_ready_boolean
from v_airport_status_dashboard;

create or replace view v_graphics_queue_candidates as
select
  airport_id,
  iata,
  airport_name,
  case
    when lower(coalesce(overall_impact_color,'')) = 'red' then 'Current red impact'
    when lower(coalesce(forecast_impact_color,'')) = 'amber' then 'Forecast weather impact'
    else 'Monitor'
  end as candidate_reason,
  travelcast_impact_rank(overall_impact_color) as priority_score,
  'airport_status_card'::text as recommended_product_type,
  'airport_delay_map'::text as recommended_layout,
  jsonb_build_object('airport_id', airport_id) as source_object_ids,
  freshness_status
from v_airport_status_dashboard
where lower(coalesce(overall_impact_color,'')) in ('red','amber')
   or lower(coalesce(forecast_impact_color,'')) in ('red','amber');

create or replace view v_source_health_dashboard as
select
  s.source_system_id,
  s.display_name,
  s.trust_tier,
  s.official_source,
  s.mission_critical_allowed,
  max(f.retrieved_at_utc) as latest_feed_run,
  max(f.retrieved_at_utc) filter (where f.live_fetch_success = true) as last_success_at,
  max(f.error) filter (where f.live_fetch_success = false) as last_error,
  count(*) filter (where f.retrieved_at_utc > now() - interval '24 hours') as runs_last_24h,
  case when max(f.retrieved_at_utc) > now() - interval '30 minutes' then 'fresh' else 'unknown' end as freshness_status
from source_systems s
left join feed_runs f on f.source_system_id = s.source_system_id
group by s.source_system_id, s.display_name, s.trust_tier, s.official_source, s.mission_critical_allowed;
