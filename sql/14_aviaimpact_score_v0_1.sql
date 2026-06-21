-- sql/14_aviaimpact_score_v0_1.sql
-- Phase D2 — AviaImpact Score v0.1
--
-- DOCTRINE:
--   AviaImpact is a draft aviation impact scoring model, NOT a replacement
--   for FAA/NAS/ATCSCC truth.
--
--   FAA/NAS/ATCSCC/official airport sources control operational-delay truth.
--   AviationWeather.gov and official aviation-weather sources control
--     aviation-weather truth.
--   NWS CAP/public alerts provide public-weather-alert context ONLY.
--     They are NOT FAA operational delay truth.
--   RouteCast geometry provides corridor/route scaffold ONLY.
--     It is NOT delay truth.
--   C3 corridor matches provide advisory/hazard context ONLY.
--     Context is NOT impact.
--   Forecast proxy is NOT observation.
--   Missing source data must produce empty-state / do-not-score results.
--   All AviaImpact draft outputs require operator review before any use.
--   All AviaImpact outputs default to public_release_allowed = false.
--   AviaImpact draft scores are not FAA operational-delay claims.
--   Empty state is better than invented scoring data.
--
-- Tables:
--   aviaimpact_model_versions       — versioned model definitions with weight contracts
--   aviaimpact_component_definitions— per-model component registry
--   aviaimpact_draft_scores         — draft score output storage (no live rows in D2)
--
-- Views:
--   v_aviaimpact_model_registry     — model definitions for UI/audit
--   v_aviaimpact_component_registry — component definitions for UI/audit
--   v_aviaimpact_draft_review_queue — draft outputs pending operator review
--   v_aviaimpact_audit_summary      — row counts and release-flag audit
--
-- NOTE: Run after sql/13_shared_impact_scoring_framework.sql.
-- Safe to re-run — uses CREATE TABLE IF NOT EXISTS and CREATE OR REPLACE VIEW.
-- No destructive operations on prior tables.


-- ─── Table: aviaimpact_model_versions ────────────────────────────────────────
-- Versioned AviaImpact model definitions.
-- Stores weight contracts, partial scoring rules, and review defaults.
-- model_status = 'draft' in D2 — not a live production model.

create table if not exists public.aviaimpact_model_versions (
  id                        uuid primary key default gen_random_uuid(),
  model_key                 text unique not null,
    -- Stable machine key, e.g. 'aviaimpact_v0_1'
  model_version             text not null,
    -- Semantic version string, e.g. '0.1'
  model_status              text not null default 'draft',
    -- 'draft' / 'active' / 'deprecated'
    -- D2 v0.1 is 'draft' only
  description               text,
  weights                   jsonb not null,
    -- Component weight contract: {component_key: weight}
    -- Weights must sum to 1.0
  required_source_lanes     text[] not null default '{}',
    -- Source lanes this model requires as minimum input
  partial_scoring_allowed   boolean not null default true,
    -- If true, model may score with fewer than all components when rules are met
  minimum_available_weight  numeric not null default 0.60,
    -- Minimum total weight of available components to allow partial scoring
  operator_review_required  boolean not null default true,
    -- Operator review required before any output is used
  public_release_default    boolean not null default false,
    -- Default public release status for draft outputs (always false)
  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now()
);

comment on table public.aviaimpact_model_versions is
  'AviaImpact model version definitions for D2. '
  'D2 v0.1 model_status = ''draft'' — not a live production model. '
  'AviaImpact draft scores are not FAA operational-delay claims. '
  'Operator review required before any draft output is used. '
  'public_release_default = false on all model versions.';


-- ─── Table: aviaimpact_component_definitions ─────────────────────────────────
-- Per-model component registry.
-- Each component maps a source lane to a weight and declares
-- allowed/prohibited inputs and empty-state behavior.

create table if not exists public.aviaimpact_component_definitions (
  id                  uuid primary key default gen_random_uuid(),
  model_key           text not null,
    -- References aviaimpact_model_versions.model_key
  component_key       text not null,
    -- Stable key for the component
  component_label     text not null,
    -- Display label
  source_lane_key     text not null,
    -- References impact_score_source_lanes.source_lane_key
  weight              numeric not null,
    -- This component's contribution weight in [0, 1]
  allowed_inputs      text[] not null default '{}',
    -- Signal types this component may consume
  prohibited_claims   text[] not null default '{}',
    -- Claims this component must never produce
  empty_state_behavior text not null default 'do_not_score',
    -- 'do_not_score' (default) / 'use_zero' / 'warn_and_score'
    -- 'do_not_score' means: if source is missing/stale, this component is unavailable
  created_at          timestamptz not null default now(),
  unique (model_key, component_key)
);

comment on table public.aviaimpact_component_definitions is
  'AviaImpact v0.1 component definitions. '
  'empty_state_behavior = ''do_not_score'' is the required default. '
  'prohibited_claims are doctrine-in-schema. '
  'NWS alerts are context only — not FAA delay truth. '
  'RouteCast geometry is context/scaffold only — not delay truth. '
  'Context match is not impact. Forecast proxy is not observation.';


-- ─── Table: aviaimpact_draft_scores ──────────────────────────────────────────
-- Draft AviaImpact score output storage.
-- D2 creates this table but does NOT insert live draft scores.
-- All outputs must default to operator_review_status='draft'
-- and public_release_allowed=false.

create table if not exists public.aviaimpact_draft_scores (
  id                     uuid primary key default gen_random_uuid(),
  model_key              text not null,
    -- References aviaimpact_model_versions.model_key
  model_version          text not null,
  entity_type            text not null,
    -- 'airport' / 'corridor' / 'region'
  entity_key             text not null,
    -- Stable entity identifier (e.g. airport IATA, corridor_key)
  score_level            integer,
    -- 0–5 from generic_0_5 scale; null if do_not_score
  score_value            numeric,
    -- Raw weighted float score; null if do_not_score
  score_label            text,
    -- Display label; null if do_not_score
  score_confidence       text,
    -- 'high' / 'medium' / 'low' / 'insufficient_data'
  score_mode             text not null default 'draft_internal',
    -- 'draft_internal' / 'weather_context_only' / 'do_not_score'
  available_weight       numeric,
    -- Sum of weights from available components
  missing_components     text[] not null default '{}',
    -- Component keys not available for this scoring run
  component_scores       jsonb not null default '{}'::jsonb,
    -- Per-component scoring detail
  source_summary         jsonb not null default '{}'::jsonb,
    -- Which sources contributed and their freshness
  explanation            jsonb not null default '{}'::jsonb,
    -- Structured explanation for operator review
  operator_review_status text not null default 'draft',
    -- 'draft' / 'reviewed' / 'accepted' / 'rejected'
    -- All system-generated outputs start as 'draft'
  public_release_allowed boolean not null default false,
    -- Must be explicitly set true by operator after review
    -- Never set automatically
  created_at             timestamptz not null default now()
);

comment on table public.aviaimpact_draft_scores is
  'AviaImpact draft score output storage. '
  'D2 does NOT insert live draft scores — table created for future use. '
  'operator_review_status = ''draft'' on all system-generated rows. '
  'public_release_allowed = false on all rows — operator must explicitly approve. '
  'AviaImpact draft scores are not FAA operational-delay claims.';


-- ─── Seed: aviaimpact_model_versions ─────────────────────────────────────────
-- One draft model version: aviaimpact_v0_1.
-- Weights must sum to 1.0.

insert into public.aviaimpact_model_versions (
  model_key, model_version, model_status, description,
  weights, required_source_lanes,
  partial_scoring_allowed, minimum_available_weight,
  operator_review_required, public_release_default
) values (
  'aviaimpact_v0_1',
  '0.1',
  'draft',
  'AviaImpact v0.1 draft aviation impact scoring model. '
  'Deterministic component-weighted model for internal aviation impact context. '
  'NOT a live scoring product. NOT an FAA operational-delay truth source. '
  'All outputs require operator review. Public release defaults false. '
  'Empty state is better than invented scoring data.',
  '{
    "official_operational_status_component": 0.35,
    "aviation_weather_component": 0.25,
    "public_alert_context_component": 0.15,
    "routecast_context_component": 0.15,
    "forecast_proxy_component": 0.10
  }'::jsonb,
  array[
    'faa_operational_truth',
    'aviation_weather_truth'
  ],
  true,
  0.60,
  true,
  false
)
on conflict (model_key) do nothing;


-- ─── Seed: aviaimpact_component_definitions ──────────────────────────────────
-- Five components for aviaimpact_v0_1.
-- Weights sum to 1.00:  0.35 + 0.25 + 0.15 + 0.15 + 0.10 = 1.00

insert into public.aviaimpact_component_definitions (
  model_key, component_key, component_label, source_lane_key,
  weight, allowed_inputs, prohibited_claims, empty_state_behavior
) values

(
  'aviaimpact_v0_1',
  'official_operational_status_component',
  'Official Operational Status',
  'faa_operational_truth',
  0.35,
  array[
    'explicit_ground_stop',
    'explicit_ground_delay_program',
    'explicit_airport_closure',
    'explicit_runway_airport_constraint',
    'explicit_atcscc_advisory_match',
    'explicit_official_delay_status',
    'explicit_traffic_management_initiative',
    'no_known_impact_from_official_source'
  ],
  array[
    'Do not infer operational delay from weather context',
    'Do not infer operational delay from RouteCast geometry',
    'Do not infer operational delay from NWS alerts',
    'Do not score from missing/stale official source',
    'Official operational source required for operational delay claims'
  ],
  'do_not_score'
),

(
  'aviaimpact_v0_1',
  'aviation_weather_component',
  'Aviation Weather Conditions',
  'aviation_weather_truth',
  0.25,
  array[
    'metar_taf_flight_category',
    'convective_weather_from_official_aviation_source',
    'wind_gust_thresholds_if_official_source_supports',
    'ceiling_visibility_constraints_if_official',
    'sigmet_airmet_convective_sigmet',
    'pirep_severity_if_available'
  ],
  array[
    'Do not fabricate METAR or TAF values',
    'Do not score from missing aviation-weather data',
    'Weather hazard does not equal FAA delay without official operational confirmation',
    'Forecast weather may only be used as forecast proxy if labeled as such'
  ],
  'do_not_score'
),

(
  'aviaimpact_v0_1',
  'public_alert_context_component',
  'Public Weather Alert Context',
  'public_weather_alert_truth',
  0.15,
  array[
    'active_nws_warning_watch_advisory_match_from_c1',
    'nws_alert_severity_urgency_certainty',
    'polygon_county_zone_corridor_context_if_available'
  ],
  array[
    'Public alerts are weather hazard context only',
    'NWS alerts are context only — not FAA delay truth',
    'Public alerts do not prove airport delay',
    'Public alerts do not prove route disruption',
    'Do not claim NWS alert causes FAA delay',
    'Missing or stale alert source must be empty-state not zero-as-fact'
  ],
  'do_not_score'
),

(
  'aviaimpact_v0_1',
  'routecast_context_component',
  'RouteCast Corridor Context',
  'routecast_context_match',
  0.15,
  array[
    'c3_atcscc_corridor_match_confidence',
    'c3_hazard_context_match_confidence',
    'routecast_corridor_geometry_confidence',
    'airport_fix_overlap_confidence'
  ],
  array[
    'Context match is not impact',
    'RouteCast geometry is context/scaffold only — not delay truth',
    'Do not produce severe score from context match alone',
    'Low-text context match must require operator review',
    'Missing context must not be scored as no impact unless source freshness confirms coverage'
  ],
  'do_not_score'
),

(
  'aviaimpact_v0_1',
  'forecast_proxy_component',
  'Forecast Weather Proxy',
  'forecast_proxy',
  0.10,
  array[
    'taf_forecast_hazard',
    'official_aviation_weather_forecast',
    'official_forecast_time_window',
    'model_guidance_if_labeled_forecast_proxy'
  ],
  array[
    'Forecast proxy is not observation',
    'Forecast proxy cannot override official current operational truth',
    'Forecast proxy cannot create delay claims',
    'Stale forecast data must be empty-state',
    'Forecast-only outputs must be labeled as forecast context'
  ],
  'do_not_score'
)

on conflict (model_key, component_key) do nothing;


-- ─── View: v_aviaimpact_model_registry ───────────────────────────────────────

create or replace view public.v_aviaimpact_model_registry as
select
  model_key,
  model_version,
  model_status,
  description,
  weights,
  required_source_lanes,
  partial_scoring_allowed,
  minimum_available_weight,
  operator_review_required,
  public_release_default,
  updated_at
from public.aviaimpact_model_versions
order by model_version desc;


-- ─── View: v_aviaimpact_component_registry ───────────────────────────────────

create or replace view public.v_aviaimpact_component_registry as
select
  c.model_key,
  c.component_key,
  c.component_label,
  c.source_lane_key,
  c.weight,
  c.allowed_inputs,
  c.prohibited_claims,
  c.empty_state_behavior,
  c.created_at
from public.aviaimpact_component_definitions c
order by c.model_key, c.weight desc;


-- ─── View: v_aviaimpact_draft_review_queue ───────────────────────────────────
-- Draft scores pending operator review.
-- All outputs require operator review before any use.
-- public_release_allowed is never set automatically.

create or replace view public.v_aviaimpact_draft_review_queue as
select
  s.model_key,
  s.entity_type,
  s.entity_key,
  s.score_level,
  s.score_label,
  s.score_confidence,
  s.score_mode,
  s.available_weight,
  s.missing_components,
  s.operator_review_status,
  s.public_release_allowed,
  s.created_at,
  'AviaImpact draft scores require operator review and are not FAA operational-delay claims.'::text
    as disclaimer
from public.aviaimpact_draft_scores s
where s.operator_review_status = 'draft'
order by s.created_at desc;


-- ─── View: v_aviaimpact_audit_summary ────────────────────────────────────────
-- Row counts and release-flag audit for monitoring.

create or replace view public.v_aviaimpact_audit_summary as
select
  m.model_key,
  m.model_version,
  m.model_status,
  count(distinct c.component_key)::integer as component_count,
  (select count(*) from public.aviaimpact_draft_scores ds where ds.model_key = m.model_key)::integer
    as draft_score_count,
  (select count(*) from public.aviaimpact_draft_scores ds
   where ds.model_key = m.model_key and ds.public_release_allowed = true)::integer
    as public_release_count,
  (select count(*) from public.aviaimpact_draft_scores ds
   where ds.model_key = m.model_key
     and ds.public_release_allowed = true
     and ds.operator_review_status != 'accepted')::integer
    as invalid_release_count
from public.aviaimpact_model_versions m
left join public.aviaimpact_component_definitions c on c.model_key = m.model_key
group by m.model_key, m.model_version, m.model_status;


-- ─── Grants ───────────────────────────────────────────────────────────────────

grant select on public.aviaimpact_model_versions        to anon, authenticated;
grant select on public.aviaimpact_component_definitions  to anon, authenticated;
grant select on public.aviaimpact_draft_scores           to anon, authenticated;
grant select on public.v_aviaimpact_model_registry       to anon, authenticated;
grant select on public.v_aviaimpact_component_registry   to anon, authenticated;
grant select on public.v_aviaimpact_draft_review_queue   to anon, authenticated;
grant select on public.v_aviaimpact_audit_summary        to anon, authenticated;

grant select, insert, update, delete
  on public.aviaimpact_model_versions,
     public.aviaimpact_component_definitions,
     public.aviaimpact_draft_scores
  to service_role;
