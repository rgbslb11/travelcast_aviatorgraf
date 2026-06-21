-- sql/13_shared_impact_scoring_framework.sql
-- Phase D1 — Shared Impact Scoring Framework
--
-- DOCTRINE:
--   FAA NAS / ATCSCC / NOTAM / official airport sources
--     = CURRENT OPERATIONAL IMPACT — operational aviation truth.
--   AviationWeather.gov / official aviation-weather sources
--     = AVIATION WEATHER TRUTH.
--   NWS CAP / WEA public alerts = PUBLIC WEATHER ALERT TRUTH ONLY.
--     Not FAA operational delay truth.
--   NWS forecast = FORECAST WEATHER IMPACT PROXY ONLY. Not observation truth.
--   RouteCast corridor geometry = PLANNING/DISPLAY SCAFFOLD. Not delay truth.
--   C3 corridor × advisory / hazard matches = CONTEXT MATCHES. Not impact scores.
--   Scoring frameworks may organize signals, weights, labels, and explanations,
--     but must NOT invent observations or operational claims.
--   D1 defines scoring models, lanes, weights, input requirements, guardrails.
--   D1 does NOT produce AviaImpact scores.
--   D1 does NOT produce RoadCast scores.
--   D1 does NOT publish graphics or broadcast outputs.
--   D1 does NOT generate live operational assertions.
--   Operator review is required before any draft score becomes a public claim.
--   Empty state is better than invented scoring data.
--
-- Tables:
--   impact_score_models              — scoring model definitions and versioning
--   impact_score_source_lanes        — source lane registry with claim boundaries
--   impact_score_scale_definitions   — shared 0–5 score scale
--   impact_score_guardrails          — prohibited claim patterns and rules
--   impact_score_input_requirements  — per-model input requirements
--   impact_score_draft_outputs       — draft score output storage (no live rows in D1)
--
-- Views:
--   v_impact_score_model_registry    — model registry for UI/audit
--   v_impact_score_source_lane_registry — source lane definitions
--   v_impact_score_guardrails        — guardrail registry
--   v_impact_score_draft_review_queue — draft outputs pending operator review
--
-- NOTE: Run after sql/12_atcscc_playbook_corridor_matching.sql.
-- Safe to re-run — all statements use CREATE TABLE IF NOT EXISTS
-- and CREATE OR REPLACE VIEW. No destructive operations on existing tables.


-- ─── Table: impact_score_models ───────────────────────────────────────────────
-- Scoring model definitions and versioning.
-- Draft model definitions may be seeded here.
-- Actual score outputs are NOT generated in D1.
-- model_status = 'draft' or 'placeholder' means: not a live scoring product.

create table if not exists public.impact_score_models (
  id                uuid primary key default gen_random_uuid(),
  model_key         text unique not null,
    -- Stable machine key, e.g. 'shared_impact_scoring_framework_v0_1'
  model_name        text not null,
    -- Display name
  model_family      text not null,
    -- Family: 'shared_framework' / 'aviaimpact' / 'roadcast' / etc.
  model_version     text not null,
    -- Semantic version string, e.g. '0.1'
  model_status      text not null default 'draft',
    -- 'draft' / 'placeholder' / 'active' / 'deprecated'
    -- D1 models are 'draft' or 'placeholder' only — never 'active'
  intended_product  text,
    -- Product this model is designed for when active (e.g. 'AviaImpact', 'RoadCast')
    -- NULL for the shared framework itself
  description       text,
  source_truth_lanes text[] not null default '{}',
    -- Source lanes this model may consume (from impact_score_source_lanes)
  allowed_inputs    text[] not null default '{}',
    -- Allowed input signal types for this model
  prohibited_inputs text[] not null default '{}',
    -- Prohibited input signal types (enforced by guardrails)
  output_contract   jsonb not null default '{}'::jsonb,
    -- Schema/contract for what this model may output (not live output)
  guardrail_notes   text,
    -- Human-readable guardrail summary for this model
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

comment on table public.impact_score_models is
  'Scoring model definitions for the D1 shared impact scoring framework. '
  'D1 model_status values are ''draft'' or ''placeholder'' only — not live products. '
  'No AviaImpact scores generated in D1. No RoadCast scores generated in D1. '
  'Operator review is required before any model becomes a live scoring product.';


-- ─── Table: impact_score_source_lanes ─────────────────────────────────────────
-- Source lane registry with claim boundaries.
-- Each lane defines what may and may not be claimed from that data source.
-- This is doctrine-in-schema: prohibited_use enforces source truth boundaries.

create table if not exists public.impact_score_source_lanes (
  id                uuid primary key default gen_random_uuid(),
  source_lane_key   text unique not null,
    -- Stable machine key, e.g. 'faa_operational_truth'
  source_lane_label text not null,
    -- Display label, e.g. 'Current Operational Impact — FAA NAS / ATCSCC'
  truth_role        text not null,
    -- What this source IS: 'operational_truth' / 'weather_truth' / 'proxy' / 'scaffold' / etc.
  allowed_use       text not null,
    -- What may be claimed from this source
  prohibited_use    text not null,
    -- What must NOT be claimed from this source
  example_sources   text[] not null default '{}',
    -- Representative source systems for this lane
  claim_boundary    text not null,
    -- One-sentence boundary statement for operator display
  created_at        timestamptz not null default now()
);

comment on table public.impact_score_source_lanes is
  'Source lane registry for the D1 shared impact scoring framework. '
  'claim_boundary and prohibited_use are doctrine-in-schema. '
  'NWS public alerts are not FAA operational truth. '
  'RouteCast geometry is not delay truth. '
  'C3 context matches are not impact scores. '
  'Forecast proxy is not observation truth.';


-- ─── Table: impact_score_scale_definitions ────────────────────────────────────
-- Shared generic 0–5 score scale.
-- NOT a product scale yet (not AviaImpact scale, not RoadCast scale).
-- Provides a shared vocabulary for future D2/D3 product-specific scales.

create table if not exists public.impact_score_scale_definitions (
  id                   uuid primary key default gen_random_uuid(),
  scale_key            text not null,
    -- Stable key for the scale, e.g. 'generic_0_5'
  level                integer not null,
    -- Numeric level (0 = lowest, 5 = highest for generic_0_5)
  label                text not null,
    -- Display label, e.g. 'No Known Impact'
  description          text not null,
    -- What this level means in context
  color_hex            text,
    -- Suggested display color (not mandatory)
  allowed_language     text,
    -- Phrasing that is safe to use at this level
  prohibited_language  text,
    -- Phrasing that must NOT be used at this level without live FAA data
  created_at           timestamptz not null default now(),
  unique (scale_key, level)
);

comment on table public.impact_score_scale_definitions is
  'Shared 0–5 generic impact score scale for the D1 framework. '
  'This is a shared vocabulary — not a product scale. '
  'Not AviaImpact. Not RoadCast. '
  'prohibited_language must be respected before any public output.';


-- ─── Table: impact_score_guardrails ───────────────────────────────────────────
-- Prohibited claim patterns and enforcement rules.
-- doctrine-in-schema: rule_text and prohibited_language are authoritative.

create table if not exists public.impact_score_guardrails (
  id                  uuid primary key default gen_random_uuid(),
  guardrail_key       text unique not null,
    -- Stable machine key, e.g. 'no_nws_alert_causes_faa_delay'
  guardrail_type      text not null,
    -- 'prohibited_claim' / 'operator_control' / 'source_boundary' / 'product_boundary'
  applies_to          text[] not null default '{}',
    -- Which model families / lanes / products this guardrail applies to
  rule_text           text not null,
    -- Authoritative rule statement
  allowed_language    text,
    -- Safe phrasing when the relevant signal is present
  prohibited_language text,
    -- Phrasing that is never acceptable
  enforcement_level   text not null default 'audit',
    -- 'audit' / 'hard_block' / 'operator_flag'
  created_at          timestamptz not null default now()
);

comment on table public.impact_score_guardrails is
  'Prohibited claim patterns and enforcement rules for the D1 scoring framework. '
  'rule_text is authoritative doctrine-in-schema. '
  'No NWS alert may be claimed to cause FAA delay. '
  'No RouteCast geometry may be claimed to cause delay. '
  'No context match may be claimed as an impact score. '
  'Operator review is required before any draft score becomes a public claim.';


-- ─── Table: impact_score_input_requirements ───────────────────────────────────
-- Per-model input requirements: what signals a model needs, and how to handle
-- missing, stale, or low-confidence inputs.

create table if not exists public.impact_score_input_requirements (
  id                       uuid primary key default gen_random_uuid(),
  model_key                text not null,
    -- References impact_score_models.model_key
  input_key                text not null,
    -- Identifies the input signal (e.g. 'airport_nas_status', 'metar_flight_category')
  source_lane_key          text not null,
    -- References impact_score_source_lanes.source_lane_key
  required                 boolean not null default false,
    -- If true, model must not score without this input
  minimum_confidence       text,
    -- Minimum confidence level required from this input
  staleness_limit_minutes  integer,
    -- How old the input may be before it is treated as stale/missing
  empty_state_behavior     text not null default 'do_not_score',
    -- 'do_not_score' / 'use_default' / 'warn_and_score'
    -- Default is 'do_not_score': empty input must not generate a non-zero score
  created_at               timestamptz not null default now()
);

comment on table public.impact_score_input_requirements is
  'Per-model input signal requirements for the D1 framework. '
  'empty_state_behavior = ''do_not_score'' is the required default. '
  'Empty inputs must not produce non-zero scores. '
  'Stale inputs must be flagged, not silently used as current.';


-- ─── Table: impact_score_draft_outputs ────────────────────────────────────────
-- Draft score output storage for future D2/D3 use.
-- D1 does NOT insert live scoring rows into this table.
-- public_release_allowed defaults to false — operator must explicitly set.

create table if not exists public.impact_score_draft_outputs (
  id                     uuid primary key default gen_random_uuid(),
  model_key              text not null,
    -- References impact_score_models.model_key
  model_version          text not null,
  entity_type            text not null,
    -- 'airport' / 'corridor' / 'region' / etc.
  entity_key             text not null,
    -- Stable key for the entity (e.g. airport IATA, corridor_key)
  score_level            integer,
    -- 0–5 from impact_score_scale_definitions
  score_label            text,
    -- Human-readable label for the level
  score_confidence       text,
    -- 'high' / 'medium' / 'low' / 'insufficient_data'
  source_summary         jsonb not null default '{}'::jsonb,
    -- Summary of which source lanes contributed to this score
  explanation            jsonb not null default '{}'::jsonb,
    -- Structured explanation of score components and weights
  operator_review_status text not null default 'draft',
    -- 'draft' / 'reviewed' / 'accepted' / 'rejected'
    -- All system-generated outputs start as 'draft'
  public_release_allowed boolean not null default false,
    -- Must be explicitly set to true by operator after review
    -- Never set automatically by scoring engine
  created_at             timestamptz not null default now()
);

comment on table public.impact_score_draft_outputs is
  'Draft impact score output storage. D1 does NOT insert live scoring rows. '
  'public_release_allowed defaults to false — operator must explicitly approve. '
  'All system-generated outputs start as operator_review_status=''draft''. '
  'No automatic public release. No AviaImpact outputs in D1. No RoadCast outputs in D1.';


-- ─── Seed: impact_score_source_lanes ─────────────────────────────────────────
-- Eight source lanes with claim boundaries.
-- Each row is doctrine-in-schema.

insert into public.impact_score_source_lanes (
  source_lane_key, source_lane_label, truth_role,
  allowed_use, prohibited_use, example_sources, claim_boundary
) values

( 'faa_operational_truth',
  'Current Operational Impact — FAA NAS / ATCSCC',
  'operational_truth',
  'State current FAA-issued operational programs (GDP, GS, AFP, MIT, reroute). '
  'Reference official delay programs and ATC restrictions when advisory text supports it.',
  'Do not invent advisories. Do not claim delay without explicit advisory text. '
  'Do not derive operational programs from weather context or geometry.',
  array['FAA NAS Status', 'ATCSCC advisories', 'NOTAM', 'airport authority'],
  'Only FAA NAS / ATCSCC / NOTAM / official airport sources may be claimed as operational truth.'
),

( 'aviation_weather_truth',
  'Aviation Weather Truth — AviationWeather.gov',
  'aviation_weather_truth',
  'Report current aviation weather conditions (METAR, TAF, SIGMET, AIRMET, CWA, PIREP). '
  'Use to describe weather hazards near airports or corridors.',
  'Do not claim aviation weather causes FAA delay programs. '
  'Do not claim aviation hazards equal operational restrictions.',
  array['AviationWeather.gov METAR', 'TAF', 'SIGMET', 'AIRMET', 'CWA', 'PIREP'],
  'AviationWeather.gov sources are aviation-weather truth — not FAA operational delay truth.'
),

( 'public_weather_alert_truth',
  'Public Weather Alert — NWS CAP',
  'public_weather_alert_truth',
  'Describe public weather alert context near airports or corridors. '
  'Reference NWS CAP event type, area, and headline as weather context.',
  'Do not claim NWS public alerts cause FAA delay. '
  'Do not claim NWS alerts equal ground stops, GDPs, or arrival rate reductions. '
  'Public alerts are not FAA operational truth.',
  array['NWS CAP alerts', 'api.weather.gov/alerts', 'WEA alerts'],
  'NWS CAP public alerts are Public Weather Alert Truth — not FAA operational delay truth.'
),

( 'forecast_proxy',
  'Forecast Weather Impact — NWS forecast proxy',
  'forecast_proxy',
  'Describe NWS grid forecast impact as a forecast weather proxy. '
  'May inform anticipated weather conditions at airports.',
  'Do not describe forecast proxy output as observed weather. '
  'Do not describe forecast proxy as official FAA delay forecast. '
  'Forecast proxy is not observation truth.',
  array['NWS grid forecast', 'NWS point forecast', 'hourly forecast'],
  'NWS forecast proxy is a planning signal — not observation truth and not FAA delay truth.'
),

( 'routecast_geometry_scaffold',
  'RouteCast Corridor Geometry — Planning/Display Scaffold',
  'planning_scaffold',
  'Display RouteCast corridor routes on maps. '
  'Use corridor endpoints and waypoints to provide geographic context.',
  'Do not claim corridor geometry causes delay. '
  'Do not claim corridor geometry equals an ATC routing decision. '
  'RouteCast geometry is not delay truth and not FAA operational truth.',
  array['routecast_corridors', 'routecast_corridor_geometry', 'Top-50 route reference'],
  'RouteCast corridor geometry is a planning/display scaffold — not FAA operational delay truth.'
),

( 'routecast_context_match',
  'RouteCast Context Match — Advisory/Hazard Context Scaffold',
  'context_match',
  'Associate RouteCast corridors with nearby advisory or hazard context. '
  'Use as a display hint that advisory context is present near a corridor.',
  'Do not claim a context match is an impact score. '
  'Do not claim a context match proves delay or restriction. '
  'C3 context matches are not impact scores.',
  array['routecast_corridor_atcscc_matches', 'routecast_corridor_hazard_context_matches'],
  'C3 context matches are context scaffolds — not delay claims and not impact scores.'
),

( 'atcscc_context_match',
  'ATCSCC Advisory Context Match — C3 Scaffold',
  'context_match',
  'Reference that an ATCSCC advisory mentions airports or fixes near a corridor. '
  'Use as a context signal for operator review.',
  'Do not claim an ATCSCC advisory context match equals an active delay program. '
  'Do not generate impact scores solely from context matches. '
  'Context matches are not operational delay claims.',
  array['atcscc_advisories', 'routecast_corridor_atcscc_matches'],
  'ATCSCC advisory context matches are context scaffolds — not delay claims or impact scores.'
),

( 'manual_operator_review',
  'Manual Operator Review — Operator-Verified Signal',
  'operator_verified',
  'Record operator-confirmed signal values after human review. '
  'May upgrade draft output status after review.',
  'Do not auto-populate operator review signals from system scoring. '
  'Do not treat draft scoring output as operator-verified without explicit review.',
  array['operator_review_status field', 'public_release_allowed field'],
  'Operator review is a human gate — not an automated scoring signal.'
)

on conflict (source_lane_key) do nothing;


-- ─── Seed: impact_score_scale_definitions ────────────────────────────────────
-- Generic 0–5 shared scale.
-- NOT a product scale yet (not AviaImpact, not RoadCast).

insert into public.impact_score_scale_definitions (
  scale_key, level, label, description, color_hex,
  allowed_language, prohibited_language
) values

( 'generic_0_5', 0, 'No Known Impact',
  'No relevant signals present or all signals indicate normal operations. '
  'Not a claim that operations are confirmed normal — only that no adverse signals are present.',
  '#4CAF50',
  'No adverse context signals present at this time.',
  'Do not claim confirmed-normal operations from a zero score alone.'
),

( 'generic_0_5', 1, 'Minimal Context',
  'At least one low-confidence context signal is present. '
  'Informational only. No operational claim supported.',
  '#8BC34A',
  'Low-confidence context signal present. Monitor for updates.',
  'Do not describe level 1 as an impact or advisory.'
),

( 'generic_0_5', 2, 'Monitor',
  'At least one medium-confidence context signal is present. '
  'Operator awareness warranted. No operational claim without FAA source support.',
  '#FFC107',
  'Context signals warrant monitoring. No FAA operational claim.',
  'Do not describe level 2 as a delay or impact without FAA source confirmation.'
),

( 'generic_0_5', 3, 'Elevated',
  'Multiple context signals present or at least one medium-confidence operational signal. '
  'Elevated awareness. Operator review recommended before any public claim.',
  '#FF9800',
  'Elevated context signals. Recommend operator review before public claim.',
  'Do not describe level 3 as confirmed delay or restriction without FAA source.'
),

( 'generic_0_5', 4, 'High',
  'Strong operational context signals present. FAA source data may support delay context. '
  'Operator review required before any public claim.',
  '#F44336',
  'High-context signals present. Operator review required.',
  'Do not publish level 4 output without operator review and FAA source confirmation.'
),

( 'generic_0_5', 5, 'Severe / Critical',
  'Severe operational signals present. FAA source data must explicitly support any claim. '
  'Operator review mandatory. Public release requires explicit approval.',
  '#B71C1C',
  'Severe context signals. Mandatory operator review and explicit FAA source required.',
  'Do not publish level 5 output without explicit operator approval and confirmed FAA source data.'
)

on conflict (scale_key, level) do nothing;


-- ─── Seed: impact_score_guardrails ───────────────────────────────────────────
-- Eight guardrails as doctrine-in-schema.
-- rule_text is authoritative.

insert into public.impact_score_guardrails (
  guardrail_key, guardrail_type, applies_to,
  rule_text, allowed_language, prohibited_language, enforcement_level
) values

( 'no_invented_source_data',
  'source_boundary',
  array['all'],
  'Do not invent source data. Every score input must be traceable to a real source row. '
  'Empty state is better than invented scoring data.',
  'Source not available — score not generated.',
  'Never populate a scoring input with invented or default data to produce a non-zero score.',
  'hard_block'
),

( 'no_nws_alert_causes_faa_delay',
  'prohibited_claim',
  array['public_weather_alert_truth', 'shared_framework', 'aviaimpact', 'roadcast'],
  'An NWS public weather alert must never be claimed to cause an FAA delay program. '
  'NWS alerts are Public Weather Alert Truth — not FAA operational delay truth.',
  'NWS alert context is present near this airport. Source: Public Weather Alert — NWS CAP.',
  'NWS alert caused FAA delay. Public alert caused airport delay.',
  'hard_block'
),

( 'no_routecast_geometry_causes_delay',
  'prohibited_claim',
  array['routecast_geometry_scaffold', 'routecast_context_match', 'shared_framework'],
  'RouteCast corridor geometry must never be claimed to cause delay. '
  'RouteCast geometry is a planning/display scaffold — not FAA operational delay truth.',
  'RouteCast corridor is a display scaffold — no delay claim from geometry.',
  'RouteCast geometry caused delay. Route geometry caused delay.',
  'hard_block'
),

( 'no_context_match_equals_impact_score',
  'prohibited_claim',
  array['routecast_context_match', 'atcscc_context_match', 'shared_framework'],
  'A C3 context match must never be claimed as an impact score. '
  'C3 context matches are context scaffolds — not delay claims and not impact scores.',
  'Context match present — operator review required before any public claim.',
  'Context match proves impact. Context match equals delay score.',
  'hard_block'
),

( 'no_forecast_proxy_as_observation',
  'prohibited_claim',
  array['forecast_proxy', 'shared_framework', 'aviaimpact', 'roadcast'],
  'NWS forecast proxy must never be described as observed weather or confirmed conditions. '
  'Forecast proxy is a planning signal — not observation truth.',
  'Forecast weather proxy: NWS forecast suggests conditions may affect operations.',
  'Forecast proxy is observed truth. Forecast equals current conditions.',
  'hard_block'
),

( 'no_aviaimpact_output_in_d1',
  'product_boundary',
  array['shared_framework', 'd1'],
  'D1 must not produce AviaImpact scores. '
  'AviaImpact is a future product phase (D2) that requires separate design approval.',
  'AviaImpact is a future product — not produced in D1.',
  'AviaImpact score generated. AviaImpact scoring active in D1.',
  'hard_block'
),

( 'no_roadcast_output_in_d1',
  'product_boundary',
  array['shared_framework', 'd1'],
  'D1 must not produce RoadCast scores. '
  'RoadCast is a future product phase (D3–D5) that requires separate design approval.',
  'RoadCast is a future product — not produced in D1.',
  'RoadCast score generated. RoadCast scoring active in D1.',
  'hard_block'
),

( 'operator_review_required_for_public_release',
  'operator_control',
  array['all'],
  'Operator review is required before any draft score output becomes a public claim. '
  'public_release_allowed must never be set automatically. '
  'operator_review_status must be ''accepted'' before public_release_allowed = true.',
  'Draft output. Operator review required before public release.',
  'Automatic public release. Score published without operator review.',
  'hard_block'
)

on conflict (guardrail_key) do nothing;


-- ─── Seed: impact_score_models ────────────────────────────────────────────────
-- Three draft / placeholder model definitions.
-- None of these are live scoring products in D1.
-- model_status = 'draft' or 'placeholder' only.
-- No score outputs generated from these definitions in D1.

insert into public.impact_score_models (
  model_key, model_name, model_family, model_version, model_status,
  intended_product, description,
  source_truth_lanes, allowed_inputs, prohibited_inputs,
  output_contract, guardrail_notes
) values

( 'shared_impact_scoring_framework_v0_1',
  'Shared Impact Scoring Framework',
  'shared_framework',
  '0.1',
  'draft',
  null,
  'D1 shared scoring framework: source lane registry, guardrails, scale definitions, '
  'and scoring primitives. Not a live product. Does not generate AviaImpact or RoadCast scores.',
  array[
    'faa_operational_truth', 'aviation_weather_truth',
    'public_weather_alert_truth', 'forecast_proxy',
    'routecast_geometry_scaffold', 'routecast_context_match',
    'atcscc_context_match', 'manual_operator_review'
  ],
  array['all_registered_source_lanes'],
  array['invented_data', 'aviaimpact_product_score', 'roadcast_product_score'],
  '{"score_range": [0, 5], "public_release_allowed": false, "operator_review_required": true}'::jsonb,
  'D1 framework only. No live outputs. No AviaImpact. No RoadCast. '
  'Operator review required before any output becomes a public claim.'
),

( 'aviaimpact_future_v0_1_placeholder',
  'AviaImpact (Future — D2 Placeholder)',
  'aviaimpact',
  '0.1-placeholder',
  'placeholder',
  'AviaImpact',
  'Placeholder for the future AviaImpact airport impact scoring product (Phase D2). '
  'NOT a live scoring product. NOT active in D1. '
  'Requires separate D2 design approval and operator validation before activation.',
  array[
    'faa_operational_truth', 'aviation_weather_truth',
    'public_weather_alert_truth', 'forecast_proxy', 'manual_operator_review'
  ],
  array[]::text[],
  array['invented_data', 'context_match_as_score', 'geometry_as_score'],
  '{"status": "placeholder", "active": false, "public_release_allowed": false}'::jsonb,
  'D2 placeholder only. Not active in D1. No AviaImpact scores may be generated until D2 is approved.'
),

( 'roadcast_future_v0_1_placeholder',
  'RoadCast (Future — D3–D5 Placeholder)',
  'roadcast',
  '0.1-placeholder',
  'placeholder',
  'RoadCast',
  'Placeholder for the future RoadCast travel-impact scoring product (Phases D3–D5). '
  'NOT a live scoring product. NOT active in D1. '
  'Requires separate D3–D5 design approval and operator validation before activation.',
  array[
    'forecast_proxy', 'public_weather_alert_truth', 'manual_operator_review'
  ],
  array[]::text[],
  array['invented_data', 'faa_delay_without_source', 'geometry_as_delay'],
  '{"status": "placeholder", "active": false, "public_release_allowed": false}'::jsonb,
  'D3–D5 placeholder only. Not active in D1. No RoadCast scores may be generated until D3 is approved.'
)

on conflict (model_key) do nothing;


-- ─── View: v_impact_score_model_registry ─────────────────────────────────────
-- Model registry for UI and audit.

create or replace view public.v_impact_score_model_registry as
select
  model_key,
  model_name,
  model_family,
  model_version,
  model_status,
  intended_product,
  source_truth_lanes,
  allowed_inputs,
  prohibited_inputs,
  guardrail_notes,
  updated_at
from public.impact_score_models
order by model_family, model_version;


-- ─── View: v_impact_score_source_lane_registry ───────────────────────────────
-- All source lane definitions and claim boundaries.

create or replace view public.v_impact_score_source_lane_registry as
select
  source_lane_key,
  source_lane_label,
  truth_role,
  allowed_use,
  prohibited_use,
  example_sources,
  claim_boundary,
  created_at
from public.impact_score_source_lanes
order by truth_role, source_lane_key;


-- ─── View: v_impact_score_guardrails ─────────────────────────────────────────
-- Guardrail registry for UI, audit, and docs reference.

create or replace view public.v_impact_score_guardrails as
select
  guardrail_key,
  guardrail_type,
  applies_to,
  rule_text,
  allowed_language,
  prohibited_language,
  enforcement_level,
  created_at
from public.impact_score_guardrails
order by enforcement_level desc, guardrail_type, guardrail_key;


-- ─── View: v_impact_score_draft_review_queue ─────────────────────────────────
-- Draft outputs pending operator review.
-- All output rows require operator review before public release.
-- public_release_allowed is never set automatically.

create or replace view public.v_impact_score_draft_review_queue as
select
  o.model_key,
  o.entity_type,
  o.entity_key,
  o.score_level,
  o.score_label,
  o.score_confidence,
  o.operator_review_status,
  o.public_release_allowed,
  o.created_at,
  'Draft impact score outputs require operator review and are not public claims.'::text
    as disclaimer
from public.impact_score_draft_outputs o
where o.operator_review_status = 'draft'
order by o.created_at desc;


-- ─── Grants ───────────────────────────────────────────────────────────────────

grant select on public.impact_score_models                to anon, authenticated;
grant select on public.impact_score_source_lanes          to anon, authenticated;
grant select on public.impact_score_scale_definitions     to anon, authenticated;
grant select on public.impact_score_guardrails            to anon, authenticated;
grant select on public.impact_score_input_requirements    to anon, authenticated;
grant select on public.impact_score_draft_outputs         to anon, authenticated;
grant select on public.v_impact_score_model_registry      to anon, authenticated;
grant select on public.v_impact_score_source_lane_registry to anon, authenticated;
grant select on public.v_impact_score_guardrails          to anon, authenticated;
grant select on public.v_impact_score_draft_review_queue  to anon, authenticated;

grant select, insert, update, delete
  on public.impact_score_models,
     public.impact_score_source_lanes,
     public.impact_score_scale_definitions,
     public.impact_score_guardrails,
     public.impact_score_input_requirements,
     public.impact_score_draft_outputs
  to service_role;
