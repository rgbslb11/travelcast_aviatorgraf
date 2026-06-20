-- sql/10_public_alert_ontology.sql
-- Phase C1 — NWS CAP / WEA Public Alert Ontology
--
-- DOCTRINE:
--   NWS CAP / WEA = Public Weather Alert Truth.
--   NWS alerts are NOT FAA operational delay truth.
--   NWS alerts provide public weather hazard context only.
--   FAA NAS / ATCSCC / official airport / NOTAM sources remain operational truth.
--   AviationWeather.gov = Aviation Weather Truth (METAR, TAF, PIREP, SIGMET, AIRMET).
--   NWS forecast impact remains forecast proxy only — separate lane.
--   Empty state is better than invented data.
--   Do not invent alerts, polygons, WEA status, hazards, or impacts.
--
-- Staleness rules:
--   Alert native expiry: expires_at_utc < now() → is_expired
--   Data freshness: fetched_at_utc >= 8 hours ago → is_stale
--   Alerts should be refreshed every 10–30 minutes in production.
--
-- On-air label:
--   Source: 'Public Weather Alert — NWS CAP'
--   Notice: 'NWS public weather alerts indicate weather hazards. They are
--            not FAA operational delay data, ground stops, GDPs, or route closures.'
--
-- Airport matching confidence levels:
--   geometry_intersection — airport point inside alert polygon (high confidence)
--   zone_text_match       — alert zone text matches airport zone (medium, scaffold only)
--   area_text_match       — area_desc text heuristic (low confidence)
--
-- Populated by:
--   scripts/pull/pull_nws_alerts.py
-- Audited by:
--   scripts/audit/audit_public_alert_ontology.py


-- ─── Source System ────────────────────────────────────────────────────────────

insert into public.source_systems (
  source_system_id,
  display_name,
  trust_tier,
  official_source,
  mission_critical_allowed,
  category,
  notes
) values (
  'nws_alerts',
  'NWS CAP / Public Weather Alerts',
  1,
  true,
  true,
  'official',
  'NWS Common Alerting Protocol (CAP) public weather alerts via api.weather.gov. '
  'Public Weather Alert Truth. Does NOT represent FAA operational delay data, '
  'ground stops, ground delay programs, route closures, or AAR.'
)
on conflict (source_system_id) do update set
  display_name             = excluded.display_name,
  trust_tier               = excluded.trust_tier,
  official_source          = excluded.official_source,
  mission_critical_allowed = excluded.mission_critical_allowed,
  notes                    = excluded.notes;


-- ─── Table: public_weather_alerts ─────────────────────────────────────────────
-- One row per NWS CAP alert. Keyed by the NWS alert URN (properties.id).
-- No sample or invented rows — empty state is correct before first live pull.

create table if not exists public.public_weather_alerts (
  alert_id              text primary key,
    -- NWS alert URN, e.g. urn:oid:2.49.0.1.840.0.xxxx

  -- Classification
  status                text,
    -- Actual / Exercise / System / Test / Draft
  message_type          text,
    -- Alert / Update / Cancel / Ack / Error
  category              text,
    -- Met / Geo / Safety / Security / Rescue / Fire / Health / Env
    -- Transport / Infra / CBRNE / Other
  severity              text,
    -- Extreme / Severe / Moderate / Minor / Unknown
  urgency               text,
    -- Immediate / Expected / Future / Past / Unknown
  certainty             text,
    -- Observed / Likely / Possible / Unlikely / Unknown
  event_type            text,
    -- Human-readable event name, e.g. 'Tornado Warning', 'Winter Storm Warning'
  response              text,
    -- Recommended public response type

  -- Timing
  sent_at_utc           timestamptz,
  effective_at_utc      timestamptz,
  onset_at_utc          timestamptz,
  expires_at_utc        timestamptz,
  ends_at_utc           timestamptz,
    -- ends_at_utc: final end time (may differ from expires for multi-period events)

  -- Location
  area_desc             text,
    -- Human-readable area description from NWS
  sender                text,
    -- NWS WFO identifier (e.g. 'w-nws.webmaster@noaa.gov')
  sender_name           text,
    -- e.g. 'NWS Dallas TX'
  affected_zones        jsonb,
    -- Array of NWS zone API URLs
  geocode_ugc           jsonb,
    -- Array of UGC zone codes, e.g. ['TXZ105', 'TXZ106']
  geocode_same          jsonb,
    -- Array of FIPS codes, e.g. ['048113']

  -- Content
  headline              text,
  description           text,
  instruction           text,
  parameters_json       jsonb,
    -- Additional NWS parameters dict

  -- Geometry
  geometry_json         jsonb,
    -- Raw GeoJSON geometry (Polygon, MultiPolygon) from NWS; null if zone-based.
    -- Do not invent geometry if NWS does not provide it.
  has_geometry          boolean not null default false,
    -- true only when NWS provided explicit polygon geometry

  -- Provenance
  raw_cap_json          jsonb,
    -- Full raw NWS alert feature JSON preserved from source
  nws_alert_url         text,
    -- Source URL (the NWS API URL for this alert)
  source_system_id      text not null default 'nws_alerts',
  fetched_at_utc        timestamptz not null default now(),
  updated_at            timestamptz not null default now()
);

create index if not exists idx_public_weather_alerts_status
  on public.public_weather_alerts (status);

create index if not exists idx_public_weather_alerts_expires
  on public.public_weather_alerts (expires_at_utc);

create index if not exists idx_public_weather_alerts_event_type
  on public.public_weather_alerts (event_type);

create index if not exists idx_public_weather_alerts_severity
  on public.public_weather_alerts (severity);

create index if not exists idx_public_weather_alerts_sent
  on public.public_weather_alerts (sent_at_utc);


-- ─── Table: airport_public_alert_matches ──────────────────────────────────────
-- Links NWS alerts to TravelCast airports when geographic evidence supports it.
--
-- IMPORTANT: An association indicates weather hazard context only.
-- It does NOT indicate FAA operational delays, ground stops, or route impacts.
-- match_confidence distinguishes geometry (high), zone (medium), text (low).

create table if not exists public.airport_public_alert_matches (
  alert_id              text not null
    references public.public_weather_alerts(alert_id) on delete cascade,
  airport_id            text not null,
  iata                  text not null,
  icao                  text not null,

  match_method          text not null,
    -- 'geometry_intersection' — airport lat/lon inside alert polygon (high confidence)
    -- 'zone_text_match'       — alert UGC zone known to contain airport (medium confidence)
    -- 'area_text_match'       — area_desc text heuristic only (low confidence)

  match_confidence      text not null,
    -- 'high'   — geometry_intersection
    -- 'medium' — zone_text_match
    -- 'low'    — area_text_match

  distance_km           numeric(10, 2),
    -- Distance from airport to nearest polygon point (geometry matches only)
    -- null for non-geometry associations

  associated_at_utc     timestamptz not null default now(),

  primary key (alert_id, airport_id)
);

create index if not exists idx_airport_public_alert_matches_airport_id
  on public.airport_public_alert_matches (airport_id);

create index if not exists idx_airport_public_alert_matches_alert_id
  on public.airport_public_alert_matches (alert_id);


-- ─── View: v_public_weather_alerts_dashboard ──────────────────────────────────
-- Current (non-expired, Actual-status) NWS alerts with freshness flags.
-- Dashboard-ready: includes source_label, alert_notice, severity_rank, is_expired.

create or replace view public.v_public_weather_alerts_dashboard as
select
  p.alert_id,
  p.status,
  p.message_type,
  p.category,
  p.severity,
  p.urgency,
  p.certainty,
  p.event_type,
  p.area_desc,
  p.sender_name,
  p.sent_at_utc,
  p.effective_at_utc,
  p.onset_at_utc,
  p.expires_at_utc,
  p.ends_at_utc,
  p.headline,
  p.description,
  p.instruction,
  p.geocode_ugc,
  p.has_geometry,
  p.nws_alert_url,
  p.fetched_at_utc,

  -- Alert native expiry flag — use expires_at_utc from NWS as authoritative
  case
    when p.expires_at_utc is not null and p.expires_at_utc < now() then true
    else false
  end as is_expired,

  -- Data freshness — data fetched 8+ hours ago may not reflect latest NWS issuances
  case
    when p.fetched_at_utc < now() - interval '8 hours' then true
    else false
  end as is_stale,

  -- Severity rank for sorting (higher = more severe); not an FAA impact rank
  case p.severity
    when 'Extreme'  then 4
    when 'Severe'   then 3
    when 'Moderate' then 2
    when 'Minor'    then 1
    else 0
  end as severity_rank,

  'Public Weather Alert — NWS CAP' as source_label,
  'NWS public weather alerts indicate weather hazards. They are not FAA operational '
  'delay data, ground stops, ground delay programs, route closures, or AAR.'
    as alert_notice

from public.public_weather_alerts p
where
  p.status       = 'Actual'
  and p.message_type != 'Cancel'
  and (p.expires_at_utc is null or p.expires_at_utc >= now() - interval '1 hour');


-- ─── View: v_airport_public_alert_context ─────────────────────────────────────
-- Active NWS alerts matched to TravelCast airports, with airport context.
-- Association indicates weather hazard context only — not FAA operational impact.
-- match_confidence: 'high' (geometry), 'medium' (zone, future), 'low' (text, future).

create or replace view public.v_airport_public_alert_context as
select
  m.airport_id,
  m.iata,
  m.icao,
  a.display_name,
  a.city,
  a.state,
  a.region,
  m.match_method,
  m.match_confidence,
  m.distance_km,
  pa.alert_id,
  pa.severity,
  pa.urgency,
  pa.certainty,
  pa.event_type,
  pa.area_desc,
  pa.sender_name,
  pa.sent_at_utc,
  pa.effective_at_utc,
  pa.onset_at_utc,
  pa.expires_at_utc,
  pa.headline,
  pa.instruction,
  pa.has_geometry,
  pa.fetched_at_utc,
  pa.is_expired,
  pa.is_stale,
  pa.severity_rank,
  pa.source_label,
  pa.alert_notice
from public.airport_public_alert_matches m
join public.v_public_weather_alerts_dashboard pa
  on pa.alert_id = m.alert_id
left join public.airports a
  on a.airport_id = m.airport_id;


-- ─── View: v_public_alert_source_health ───────────────────────────────────────
-- Source health monitoring for NWS alert ingestion.
-- Reports freshness, alert counts, staleness, and geometry coverage.
-- Used by dashboard header and source health panel.

create or replace view public.v_public_alert_source_health as
select
  'nws_alerts'                      as source_system_id,
  'NWS CAP / Public Weather Alerts' as display_name,
  'Public Weather Alert — NWS CAP'  as source_label,

  count(*)                          as total_alerts_stored,

  count(*) filter (
    where p.status       = 'Actual'
    and   p.message_type != 'Cancel'
    and   (p.expires_at_utc is null or p.expires_at_utc >= now())
  )                                 as active_alerts,

  count(*) filter (
    where p.expires_at_utc is not null and p.expires_at_utc < now()
  )                                 as expired_alerts,

  count(*) filter (
    where p.has_geometry = true
  )                                 as alerts_with_geometry,

  max(p.fetched_at_utc)             as last_fetched_at_utc,

  case
    when max(p.fetched_at_utc) is null
      then true
    when max(p.fetched_at_utc) < now() - interval '8 hours'
      then true
    else false
  end                               as is_stale,

  case
    when max(p.fetched_at_utc) is null
      then 'No data — run pull_nws_alerts.py first.'
    when max(p.fetched_at_utc) < now() - interval '8 hours'
      then 'STALE — last fetch > 8 hours ago; data may be outdated.'
    else 'Current'
  end                               as freshness_label,

  'NWS public weather alerts indicate weather hazards. '
  'They are not FAA operational delay data, ground stops, GDPs, or route closures.'
                                    as alert_notice

from public.public_weather_alerts p;


-- ─── View: v_public_alerts_aviation_context ───────────────────────────────────
-- Active alerts for weather event types that create aviation hazard context.
-- These alerts may affect visibility, ceiling, wind, or surface conditions
-- at or near TravelCast airports.
--
-- NOTICE: These events provide weather hazard CONTEXT only.
-- They do NOT constitute FAA operational data.

create or replace view public.v_public_alerts_aviation_context as
select
  pa.*
from public.v_public_weather_alerts_dashboard pa
where pa.event_type in (
  -- Severe convective
  'Tornado Warning',
  'Tornado Watch',
  'Severe Thunderstorm Warning',
  'Severe Thunderstorm Watch',
  'Special Marine Warning',
  -- Winter / precipitation
  'Winter Storm Warning',
  'Winter Storm Watch',
  'Winter Storm Advisory',
  'Winter Weather Advisory',
  'Blizzard Warning',
  'Ice Storm Warning',
  'Freezing Rain Advisory',
  'Freezing Drizzle Advisory',
  'Heavy Snow Warning',
  -- Visibility
  'Dense Fog Advisory',
  'Dense Fog Warning',
  'Dust Storm Warning',
  'Dust Advisory',
  'Smoke Advisory',
  'Air Quality Alert',
  'Freezing Fog Advisory',
  -- Wind
  'High Wind Warning',
  'High Wind Watch',
  'Wind Advisory',
  'Extreme Wind Warning',
  -- Other
  'Flash Flood Warning',
  'Flash Flood Watch',
  'Special Weather Statement'
);


-- ─── Grants ───────────────────────────────────────────────────────────────────

grant select on public.public_weather_alerts               to anon, authenticated;
grant select on public.airport_public_alert_matches        to anon, authenticated;
grant select on public.v_public_weather_alerts_dashboard   to anon, authenticated;
grant select on public.v_airport_public_alert_context      to anon, authenticated;
grant select on public.v_public_alert_source_health        to anon, authenticated;
grant select on public.v_public_alerts_aviation_context    to anon, authenticated;

grant select, insert, update, delete
  on public.public_weather_alerts, public.airport_public_alert_matches
  to service_role;
