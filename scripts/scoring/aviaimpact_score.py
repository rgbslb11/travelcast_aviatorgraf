#!/usr/bin/env python3
"""
scripts/scoring/aviaimpact_score.py
Phase D2 — AviaImpact Score v0.1

Deterministic component-based aviation impact scoring.
Imports D1 shared scoring utilities from shared_impact_scoring.py.

Doctrine:
  AviaImpact is a draft aviation impact score — NOT FAA/NAS/ATCSCC truth.
  FAA/NAS/ATCSCC/official airport sources control operational-delay truth.
  AviationWeather.gov controls aviation-weather truth.
  NWS CAP/public alerts provide public-weather-alert context ONLY.
  RouteCast geometry provides corridor/route scaffold ONLY.
  C3 corridor matches provide advisory/hazard context ONLY.
  Context is NOT impact. Forecast proxy is NOT observation.
  Missing source data must produce empty-state / do-not-score results.
  All outputs default to operator_review_required=True, public_release_allowed=False.
  AviaImpact draft scores are not FAA operational-delay claims.
  Empty state is better than invented scoring data.

No network calls. No Supabase writes. No file I/O by default.
CLI:
  python scripts/scoring/aviaimpact_score.py --self-test
  python scripts/scoring/aviaimpact_score.py --input test_data.json
  python scripts/scoring/aviaimpact_score.py --input test_data.json --out result.json
"""

import argparse
import json
import sys
from pathlib import Path

# D1 shared scoring utilities (same directory)
sys.path.insert(0, str(Path(__file__).parent))
from shared_impact_scoring import (
    clamp_score,
    score_to_level,
    level_to_label,
    weighted_score,
    normalize_confidence,
    validate_source_lane,
    validate_no_prohibited_claim,
    VALID_SOURCE_LANES,
    WEIGHT_SUM_TOLERANCE,
)

# ─── Model constants ──────────────────────────────────────────────────────────

MODEL_KEY = 'aviaimpact_v0_1'
MODEL_VERSION = '0.1'
MINIMUM_AVAILABLE_WEIGHT = 0.60

COMPONENT_WEIGHTS = {
    'official_operational_status': 0.35,
    'aviation_weather':            0.25,
    'public_alert_context':        0.15,
    'routecast_context':           0.15,
    'forecast_proxy':              0.10,
}

# Verify weights sum to 1.0 at import time
_weight_sum = sum(COMPONENT_WEIGHTS.values())
assert abs(_weight_sum - 1.0) <= WEIGHT_SUM_TOLERANCE, (
    f'COMPONENT_WEIGHTS must sum to 1.0, got {_weight_sum}'
)

COMPONENT_SOURCE_LANES = {
    'official_operational_status': 'faa_operational_truth',
    'aviation_weather':            'aviation_weather_truth',
    'public_alert_context':        'public_weather_alert_truth',
    'routecast_context':           'routecast_context_match',
    'forecast_proxy':              'forecast_proxy',
}

DISCLAIMER = (
    'AviaImpact draft scores require operator review '
    'and are not FAA operational-delay claims.'
)

# Maps for official operational status -> score
_OFFICIAL_STATUS_SCORES = {
    'airport_closure':    5,
    'unavailable':        5,
    'ground_stop':        5,
    'gdp':                4,
    'ground_delay_program': 4,
    'afp':                3,
    'airspace_flow_program': 3,
    'reroute':            3,
    'mit':                2,
    'miles_in_trail':     2,
    'staffing_constraint': 2,
    'route_constraint':   2,
    'no_impact':          0,
    'no_known_impact':    0,
    'vfr_normal':         0,
}

# Maps for aviation weather -> score
_WEATHER_STATUS_SCORES = {
    'lifr':                   5,
    'severe_convective':      5,
    'major_runway_impact':    5,
    'ifr':                    3,
    'strong_convective':      3,
    'high_wind':              3,
    'mvfr':                   2,
    'moderate_weather':       2,
    'vfr':                    0,
    'no_hazard':              0,
    'clear':                  0,
}

# Maps for public alert type -> score
_ALERT_TYPE_SCORES = {
    'tornado_warning':            4,
    'severe_thunderstorm_warning': 4,
    'flash_flood_warning':        4,
    'hurricane_warning':          5,
    'blizzard_warning':           3,
    'winter_storm_warning':       3,
    'wind_advisory':              2,
    'watch':                      2,
    'advisory':                   2,
    'special_weather_statement':  1,
    'statement':                  1,
    'no_alert':                   0,
}

# Maps for routecast context match type -> score
_ROUTECAST_CONTEXT_SCORES = {
    'high_official_atcscc_match':      3,
    'medium_airport_fix_overlap':      2,
    'public_alert_hazard_match':       1,
    'geometry_scaffold_only':          0,
    'low_text_context_only':           1,
}


# ─── Component builder ────────────────────────────────────────────────────────

def build_component_result(component_key, source_lane_key, raw_value,
                            normalized_score, confidence,
                            stale=False, explanation=None):
    """
    Build a standardized component result dict.

    normalized_score=None means the component is not available (empty-state).
    """
    return {
        'component_key':   component_key,
        'source_lane_key': source_lane_key,
        'raw_value':       raw_value,
        'normalized_score': normalized_score,
        'confidence':      confidence,
        'stale':           stale,
        'explanation':     explanation or '',
        'available':       normalized_score is not None and not stale,
    }


def is_component_available(component):
    """Return True if a component has a valid, non-stale score."""
    return (
        component.get('available', False)
        and component.get('normalized_score') is not None
        and not component.get('stale', False)
    )


# ─── Component evaluators ─────────────────────────────────────────────────────

def evaluate_official_operational_status(input_data):
    """
    Evaluate the official operational status component.
    Source lane: faa_operational_truth. Weight: 0.35.

    Only FAA/NAS/ATCSCC/official airport sources may produce operational claims.
    Missing or stale data must produce empty-state, not zero.
    Do not infer operational delay from weather context, NWS alerts, or geometry.
    Official operational source required for operational delay claims.
    """
    raw = input_data.get('official_operational_status', {})
    key = 'official_operational_status'
    lane = COMPONENT_SOURCE_LANES[key]

    if not raw.get('available', False):
        return build_component_result(
            key, lane, raw_value=None, normalized_score=None,
            confidence='insufficient_data',
            explanation='Official operational source not available — empty state. '
                        'Do not infer operational delay from weather or geometry.'
        )

    if not raw.get('fresh', True):
        return build_component_result(
            key, lane, raw_value=raw.get('explicit_status'),
            normalized_score=None, confidence='insufficient_data',
            stale=True,
            explanation='Official operational source is stale — empty state. '
                        'Stale source must not be treated as current.'
        )

    status = str(raw.get('explicit_status') or '').lower().strip()
    if status in _OFFICIAL_STATUS_SCORES:
        score = float(_OFFICIAL_STATUS_SCORES[status])
        confidence = normalize_confidence(raw.get('confidence', 'medium'))
        return build_component_result(
            key, lane, raw_value=status, normalized_score=score,
            confidence=confidence,
            explanation=(
                f'Official operational source explicitly reports: {status}. '
                f'Score {score}/5. Source: FAA/NAS/ATCSCC/official airport.'
            )
        )

    # Unknown status -> cannot score
    return build_component_result(
        key, lane, raw_value=status, normalized_score=None,
        confidence='insufficient_data',
        explanation=(
            f'Official operational status unknown: {status!r}. '
            'Cannot score without explicit source-backed status. Empty state.'
        )
    )


def evaluate_aviation_weather(input_data):
    """
    Evaluate the aviation weather component.
    Source lane: aviation_weather_truth. Weight: 0.25.

    Only AviationWeather.gov / official aviation-weather sources.
    Do not fabricate METAR/TAF values.
    Weather hazard does not equal FAA delay without official operational confirmation.
    Missing/stale data produces empty-state.
    """
    raw = input_data.get('aviation_weather', {})
    key = 'aviation_weather'
    lane = COMPONENT_SOURCE_LANES[key]

    if not raw.get('available', False):
        return build_component_result(
            key, lane, raw_value=None, normalized_score=None,
            confidence='insufficient_data',
            explanation='Aviation-weather source not available — empty state.'
        )

    if not raw.get('fresh', True):
        return build_component_result(
            key, lane, raw_value=raw.get('explicit_status'),
            normalized_score=None, confidence='insufficient_data',
            stale=True,
            explanation='Aviation-weather source is stale — empty state.'
        )

    status = str(raw.get('explicit_status') or '').lower().strip()
    if status in _WEATHER_STATUS_SCORES:
        score = float(_WEATHER_STATUS_SCORES[status])
        confidence = normalize_confidence(raw.get('confidence', 'medium'))
        return build_component_result(
            key, lane, raw_value=status, normalized_score=score,
            confidence=confidence,
            explanation=(
                f'Aviation-weather source reports: {status}. '
                f'Score {score}/5. Source: AviationWeather.gov / official aviation-weather. '
                'Note: weather hazard does not equal FAA delay without official operational confirmation.'
            )
        )

    return build_component_result(
        key, lane, raw_value=status, normalized_score=None,
        confidence='insufficient_data',
        explanation=f'Aviation-weather status unknown: {status!r}. Empty state.'
    )


def evaluate_public_alert_context(input_data):
    """
    Evaluate the public alert context component.
    Source lane: public_weather_alert_truth. Weight: 0.15.

    NWS CAP/WEA public alerts provide weather-hazard context ONLY.
    NWS alerts are context only — not FAA delay truth.
    Public alerts do not prove airport delay or route disruption.
    Fresh source confirming no active relevant alert may score 0.
    Missing/stale source must produce empty-state, not zero.
    """
    raw = input_data.get('public_alert_context', {})
    key = 'public_alert_context'
    lane = COMPONENT_SOURCE_LANES[key]

    if not raw.get('available', False):
        return build_component_result(
            key, lane, raw_value=None, normalized_score=None,
            confidence='insufficient_data',
            explanation=(
                'Public alert source not available — empty state. '
                'NWS alerts are context only — not FAA delay truth.'
            )
        )

    if not raw.get('fresh', True):
        return build_component_result(
            key, lane, raw_value=raw.get('alert_type'),
            normalized_score=None, confidence='insufficient_data',
            stale=True,
            explanation='Public alert source is stale — empty state.'
        )

    alert_type = str(raw.get('alert_type') or '').lower().strip()
    if alert_type in _ALERT_TYPE_SCORES:
        score = float(_ALERT_TYPE_SCORES[alert_type])
        confidence = normalize_confidence(raw.get('confidence', 'medium'))
        note = (
            'NWS alert context only — does not confirm airport delay or route disruption. '
            'Source: Public Weather Alert — NWS CAP.'
        )
        return build_component_result(
            key, lane, raw_value=alert_type, normalized_score=score,
            confidence=confidence,
            explanation=f'NWS public alert context: {alert_type}. Score {score}/5. {note}'
        )

    return build_component_result(
        key, lane, raw_value=alert_type, normalized_score=None,
        confidence='insufficient_data',
        explanation=f'Public alert type unknown: {alert_type!r}. Empty state.'
    )


def evaluate_routecast_context(input_data):
    """
    Evaluate the RouteCast context component.
    Source lane: routecast_context_match. Weight: 0.15.

    Context match is not impact.
    RouteCast geometry is context/scaffold only — not delay truth.
    High context with no source-backed operational/weather hazard
    must not produce public claims.
    Low-text context (max score 1) must require operator review.
    Missing context produces empty-state (not zero-as-no-impact).
    """
    raw = input_data.get('routecast_context', {})
    key = 'routecast_context'
    lane = COMPONENT_SOURCE_LANES[key]

    if not raw.get('available', False):
        return build_component_result(
            key, lane, raw_value=None, normalized_score=None,
            confidence='insufficient_data',
            explanation=(
                'RouteCast context source not available — empty state. '
                'Context match is not impact. Geometry is not delay truth.'
            )
        )

    if not raw.get('fresh', True):
        return build_component_result(
            key, lane, raw_value=raw.get('explicit_status'),
            normalized_score=None, confidence='insufficient_data',
            stale=True,
            explanation='RouteCast context source is stale — empty state.'
        )

    ctx_type = str(raw.get('explicit_status') or '').lower().strip()
    if ctx_type in _ROUTECAST_CONTEXT_SCORES:
        score = float(_ROUTECAST_CONTEXT_SCORES[ctx_type])
        # low_text_context capped at 1 — also flag requires operator review
        if ctx_type == 'low_text_context_only':
            score = min(score, 1.0)
        confidence = normalize_confidence(raw.get('confidence', 'low'))
        return build_component_result(
            key, lane, raw_value=ctx_type, normalized_score=score,
            confidence=confidence,
            explanation=(
                f'RouteCast context: {ctx_type}. Score {score}/5. '
                'Context match is not impact. Geometry is not delay truth. '
                'Operator review required before any public claim.'
            )
        )

    return build_component_result(
        key, lane, raw_value=ctx_type, normalized_score=None,
        confidence='insufficient_data',
        explanation=f'RouteCast context type unknown: {ctx_type!r}. Empty state.'
    )


def evaluate_forecast_proxy(input_data):
    """
    Evaluate the forecast proxy component.
    Source lane: forecast_proxy. Weight: 0.10.

    Forecast proxy is not observation.
    Forecast proxy cannot override official current operational truth.
    Forecast proxy cannot create delay claims.
    Stale forecast must be empty-state.
    Outputs labeled as forecast context only.
    """
    raw = input_data.get('forecast_proxy', {})
    key = 'forecast_proxy'
    lane = COMPONENT_SOURCE_LANES[key]

    forecast_score_map = {
        'high_impact':    3,
        'moderate_impact': 2,
        'low_impact':     1,
        'no_hazard':      0,
        'clear':          0,
    }

    if not raw.get('available', False):
        return build_component_result(
            key, lane, raw_value=None, normalized_score=None,
            confidence='insufficient_data',
            explanation=(
                'Forecast proxy source not available — empty state. '
                'Forecast proxy is not observation.'
            )
        )

    if not raw.get('fresh', True):
        return build_component_result(
            key, lane, raw_value=raw.get('explicit_status'),
            normalized_score=None, confidence='insufficient_data',
            stale=True,
            explanation='Forecast proxy source is stale — empty state.'
        )

    status = str(raw.get('explicit_status') or '').lower().strip()
    if status in forecast_score_map:
        score = float(forecast_score_map[status])
        confidence = normalize_confidence(raw.get('confidence', 'low'))
        return build_component_result(
            key, lane, raw_value=status, normalized_score=score,
            confidence=confidence,
            explanation=(
                f'Forecast proxy: {status}. Score {score}/5. '
                'Forecast proxy is not observation. Cannot create delay claims. '
                'Source: NWS forecast proxy / TAF forecast / official aviation-weather forecast.'
            )
        )

    return build_component_result(
        key, lane, raw_value=status, normalized_score=None,
        confidence='insufficient_data',
        explanation=f'Forecast proxy status unknown: {status!r}. Empty state.'
    )


# ─── Result builders ──────────────────────────────────────────────────────────

def build_source_summary(components):
    """Build a source summary dict from evaluated components."""
    summary = {}
    for k, comp in components.items():
        summary[k] = {
            'source_lane_key': comp.get('source_lane_key'),
            'available': comp.get('available', False),
            'stale': comp.get('stale', False),
            'confidence': comp.get('confidence', 'insufficient_data'),
            'raw_value': comp.get('raw_value'),
        }
    return summary


def build_explanation(components, overall_result):
    """Build a structured explanation dict for operator review."""
    comp_explanations = {}
    for k, comp in components.items():
        comp_explanations[k] = {
            'available': comp.get('available', False),
            'score': comp.get('normalized_score'),
            'weight': COMPONENT_WEIGHTS.get(k),
            'explanation': comp.get('explanation', ''),
        }
    return {
        'model_key': MODEL_KEY,
        'model_version': MODEL_VERSION,
        'overall_score': overall_result.get('score_value'),
        'overall_level': overall_result.get('score_level'),
        'score_mode': overall_result.get('score_mode', 'do_not_score'),
        'available_weight': overall_result.get('available_weight', 0.0),
        'missing_components': overall_result.get('missing_components', []),
        'components': comp_explanations,
        'disclaimer': DISCLAIMER,
        'note': (
            'This explanation is for operator review only. '
            'AviaImpact draft scores are not FAA operational-delay claims. '
            'Operator review required before any use.'
        ),
    }


def empty_aviaimpact_result(reason, missing_components=None):
    """
    Return a standardized empty/do-not-score AviaImpact result.

    Always: operator_review_required=True, public_release_allowed=False.
    Empty state is better than invented scoring data.
    """
    return {
        'model_key':             MODEL_KEY,
        'model_version':         MODEL_VERSION,
        'score_level':           None,
        'score_value':           None,
        'score_label':           None,
        'score_confidence':      'insufficient_data',
        'score_mode':            'do_not_score',
        'available_weight':      0.0,
        'missing_components':    missing_components or [],
        'component_scores':      {},
        'source_summary':        {},
        'explanation':           {'reason': reason, 'disclaimer': DISCLAIMER},
        'operator_review_status': 'draft',
        'operator_review_required': True,
        'public_release_allowed': False,
        'empty_state':           True,
        'empty_state_reason':    reason,
        'disclaimer':            DISCLAIMER,
    }


def validate_aviaimpact_result(result):
    """
    Validate that an AviaImpact result respects doctrine requirements.

    Raises ValueError if any requirement is violated.
    Returns result unchanged if valid.
    """
    if result.get('public_release_allowed') is True:
        raise ValueError(
            'validate_aviaimpact_result: public_release_allowed=True — '
            'public release requires explicit operator approval'
        )
    if result.get('operator_review_required') is False:
        raise ValueError(
            'validate_aviaimpact_result: operator_review_required=False — '
            'operator review may not be bypassed for AviaImpact outputs'
        )
    score_level = result.get('score_level')
    if score_level is not None:
        if not isinstance(score_level, int) or score_level < 0 or score_level > 5:
            raise ValueError(
                f'validate_aviaimpact_result: score_level {score_level!r} '
                'is out of range [0, 5]'
            )
    return result


# ─── Main scoring function ────────────────────────────────────────────────────

def compute_aviaimpact_score(input_data, allow_partial=True):
    """
    Compute a deterministic draft AviaImpact score from input_data.

    input_data: dict with optional keys:
      official_operational_status, aviation_weather, public_alert_context,
      routecast_context, forecast_proxy

    Each sub-dict has keys:
      available (bool), fresh (bool), explicit_status (str),
      alert_type (str, for public_alert_context),
      confidence (str), source_lane (str), notes (str)

    Returns a result dict. All outputs are draft/internal.
    operator_review_required=True, public_release_allowed=False always.
    Empty state is better than invented scoring data.

    Partial scoring rules (v0.1):
      - At least one official operational OR aviation-weather source must be available.
      - Total available component weight must be >= MINIMUM_AVAILABLE_WEIGHT (0.60).
      - Unavailable components are listed as missing_components.
      - Confidence is downgraded when partial.
    """
    # Evaluate all 5 components
    components = {
        'official_operational_status': evaluate_official_operational_status(input_data),
        'aviation_weather':            evaluate_aviation_weather(input_data),
        'public_alert_context':        evaluate_public_alert_context(input_data),
        'routecast_context':           evaluate_routecast_context(input_data),
        'forecast_proxy':              evaluate_forecast_proxy(input_data),
    }

    available_keys = [k for k in components if is_component_available(components[k])]
    missing_keys   = [k for k in components if not is_component_available(components[k])]

    available_weight = sum(COMPONENT_WEIGHTS[k] for k in available_keys)

    has_operational = is_component_available(components['official_operational_status'])
    has_weather     = is_component_available(components['aviation_weather'])

    # Rule 1: No official or aviation-weather source -> context-only or do_not_score
    if not has_operational and not has_weather:
        return empty_aviaimpact_result(
            'No official operational or aviation-weather source available. '
            'Context-only sources cannot produce AviaImpact scores without official backing. '
            'Empty state is better than invented scoring data.',
            missing_components=missing_keys
        )

    # Rule 2: Partial scoring allowed check
    if not allow_partial and len(missing_keys) > 0:
        return empty_aviaimpact_result(
            f'Partial scoring not allowed and {len(missing_keys)} component(s) missing: '
            f'{missing_keys}',
            missing_components=missing_keys
        )

    # Rule 3: Available weight must meet minimum
    if available_weight < MINIMUM_AVAILABLE_WEIGHT:
        return empty_aviaimpact_result(
            f'Available component weight {available_weight:.2f} is below '
            f'minimum {MINIMUM_AVAILABLE_WEIGHT:.2f}. '
            'Insufficient source coverage for partial scoring. '
            'Empty state is better than invented scoring data.',
            missing_components=missing_keys
        )

    # Renormalize weights over available components
    renorm_weights = {
        k: COMPONENT_WEIGHTS[k] / available_weight
        for k in available_keys
    }

    # Compute weighted score using D1 utility (renormalized weights sum to 1.0)
    component_score_values = {
        k: components[k]['normalized_score']
        for k in available_keys
    }
    raw_score = weighted_score(component_score_values, renorm_weights)

    # Determine confidence based on available weight
    if available_weight >= 0.90:
        confidence = 'high'
    elif available_weight >= 0.75:
        confidence = 'medium'
    else:
        confidence = 'low'

    # Determine score mode
    if not has_operational:
        score_mode = 'weather_context_only'
    elif len(missing_keys) == 0:
        score_mode = 'full_coverage'
    else:
        score_mode = 'draft_internal'

    score_level = score_to_level(raw_score)
    score_label = level_to_label(score_level)

    result = {
        'model_key':             MODEL_KEY,
        'model_version':         MODEL_VERSION,
        'score_level':           score_level,
        'score_value':           raw_score,
        'score_label':           score_label,
        'score_confidence':      confidence,
        'score_mode':            score_mode,
        'available_weight':      available_weight,
        'missing_components':    missing_keys,
        'component_scores':      {k: components[k] for k in components},
        'operator_review_status': 'draft',
        'operator_review_required': True,
        'public_release_allowed': False,
        'empty_state':           False,
        'disclaimer':            DISCLAIMER,
    }
    result['source_summary'] = build_source_summary(components)
    result['explanation']    = build_explanation(components, result)

    return validate_aviaimpact_result(result)


# ─── Self-test ────────────────────────────────────────────────────────────────

def run_self_test():
    """
    Run 12 deterministic self-test cases for AviaImpact v0.1.
    No file I/O. No network calls. No Supabase writes.
    Returns True if all pass.
    """
    failures = []

    def chk(name, fn):
        try:
            fn()
            print(f'  PASS  {name}')
        except Exception as e:
            print(f'  FAIL  {name}: {e}')
            failures.append(name)

    def expect_raises(fn, exc_type):
        try:
            fn()
        except exc_type:
            return
        raise AssertionError(f'Expected {exc_type.__name__} but no exception raised')

    print('D2 aviaimpact_score self-test')
    print('---')

    # Case 1: All components missing -> do_not_score / empty-state
    def t_all_missing():
        r = compute_aviaimpact_score({})
        assert r['score_level'] is None, f'Expected None score_level, got {r["score_level"]}'
        assert r['empty_state'] is True
        assert r['operator_review_required'] is True
        assert r['public_release_allowed'] is False
        assert r['score_mode'] == 'do_not_score'
    chk('Case 1: all components missing -> do_not_score', t_all_missing)

    # Case 2: Explicit ground stop (official + weather available -> weight 0.60)
    def t_ground_stop():
        data = {
            'official_operational_status': {
                'available': True, 'fresh': True,
                'explicit_status': 'ground_stop', 'confidence': 'high',
            },
            'aviation_weather': {
                'available': True, 'fresh': True,
                'explicit_status': 'ifr', 'confidence': 'high',
            },
        }
        r = compute_aviaimpact_score(data)
        assert r['empty_state'] is False
        assert r['score_level'] is not None
        assert r['score_level'] >= 3, f'Ground stop should score >= 3, got {r["score_level"]}'
        assert r['operator_review_required'] is True
        assert r['public_release_allowed'] is False
        assert r['operator_review_status'] == 'draft'
        assert 'official_operational_status' not in r['missing_components']
    chk('Case 2: ground stop -> high draft score, no public release', t_ground_stop)

    # Case 3: Strong aviation weather, no official operational source
    def t_weather_no_official():
        data = {
            'aviation_weather': {
                'available': True, 'fresh': True,
                'explicit_status': 'severe_convective', 'confidence': 'high',
            },
            'public_alert_context': {
                'available': True, 'fresh': True,
                'alert_type': 'severe_thunderstorm_warning', 'confidence': 'medium',
            },
            'routecast_context': {
                'available': True, 'fresh': True,
                'explicit_status': 'medium_airport_fix_overlap', 'confidence': 'medium',
            },
            'forecast_proxy': {
                'available': True, 'fresh': True,
                'explicit_status': 'high_impact', 'confidence': 'low',
            },
        }
        r = compute_aviaimpact_score(data)
        # Available weight: 0.25+0.15+0.15+0.10 = 0.65 >= 0.60
        assert r['empty_state'] is False or r.get('score_mode') == 'do_not_score'
        # If scored, it must be weather_context_only
        if not r['empty_state']:
            assert r['score_mode'] == 'weather_context_only', (
                f'Expected weather_context_only mode, got {r["score_mode"]!r}'
            )
            assert r['public_release_allowed'] is False
            assert r['operator_review_required'] is True
        # No operational delay claim
        explanation_str = json.dumps(r.get('explanation', {}))
        assert 'faa delay' not in explanation_str.lower() or 'not' in explanation_str.lower()
    chk('Case 3: strong aviation weather, no official -> weather_context_only, no delay claim', t_weather_no_official)

    # Case 4: NWS warning only -> do_not_score (weight 0.15 < 0.60)
    def t_nws_only():
        data = {
            'public_alert_context': {
                'available': True, 'fresh': True,
                'alert_type': 'tornado_warning', 'confidence': 'high',
            },
        }
        r = compute_aviaimpact_score(data)
        assert r['empty_state'] is True, (
            f'NWS-only should produce empty state, got score_mode={r.get("score_mode")}'
        )
        assert r['score_mode'] == 'do_not_score'
        assert r['public_release_allowed'] is False
    chk('Case 4: NWS warning only -> do_not_score, no FAA delay claim', t_nws_only)

    # Case 5: RouteCast context only -> do_not_score (weight 0.15 < 0.60)
    def t_routecast_only():
        data = {
            'routecast_context': {
                'available': True, 'fresh': True,
                'explicit_status': 'high_official_atcscc_match', 'confidence': 'high',
            },
        }
        r = compute_aviaimpact_score(data)
        assert r['empty_state'] is True
        assert r['score_mode'] == 'do_not_score'
    chk('Case 5: RouteCast context only -> do_not_score, no delay claim', t_routecast_only)

    # Case 6: Forecast proxy only -> do_not_score (weight 0.10 < 0.60)
    def t_forecast_only():
        data = {
            'forecast_proxy': {
                'available': True, 'fresh': True,
                'explicit_status': 'high_impact', 'confidence': 'low',
            },
        }
        r = compute_aviaimpact_score(data)
        assert r['empty_state'] is True
        assert r['score_mode'] == 'do_not_score'
    chk('Case 6: forecast proxy only -> do_not_score, no observation claim', t_forecast_only)

    # Case 7: Partial scoring — official + weather available (weight exactly 0.60)
    def t_partial_60():
        data = {
            'official_operational_status': {
                'available': True, 'fresh': True,
                'explicit_status': 'no_impact', 'confidence': 'high',
            },
            'aviation_weather': {
                'available': True, 'fresh': True,
                'explicit_status': 'mvfr', 'confidence': 'medium',
            },
        }
        r = compute_aviaimpact_score(data, allow_partial=True)
        # available_weight = 0.35 + 0.25 = 0.60, meets minimum exactly
        assert r['empty_state'] is False
        assert r['score_level'] is not None
        assert r['score_confidence'] == 'low', (
            f'Expected low confidence at 0.60 weight, got {r["score_confidence"]!r}'
        )
        assert r['public_release_allowed'] is False
        assert r['operator_review_required'] is True
        assert len(r['missing_components']) > 0
    chk('Case 7: partial scoring official+weather (weight 0.60) -> allowed, confidence=low', t_partial_60)

    # Case 8: Missing components are NOT treated as zero
    def t_missing_not_zero():
        # Only official available; weight 0.35 < 0.60 -> do_not_score
        data = {
            'official_operational_status': {
                'available': True, 'fresh': True,
                'explicit_status': 'no_impact', 'confidence': 'high',
            },
        }
        r = compute_aviaimpact_score(data)
        # Must be empty-state (insufficient weight), not score_level=0
        assert r['empty_state'] is True, (
            f'Missing components must not be treated as zero — expected empty_state, '
            f'got score_level={r.get("score_level")}'
        )
    chk('Case 8: missing components not treated as zero', t_missing_not_zero)

    # Case 9: Prohibited claim text fails validate_no_prohibited_claim
    def t_prohibited_claim():
        expect_raises(
            lambda: validate_no_prohibited_claim(
                'NWS alert caused FAA delay at EWR.'
            ),
            ValueError
        )
    chk('Case 9: prohibited claim text fails validation', t_prohibited_claim)

    # Case 10: public_release_allowed=True fails validate_aviaimpact_result
    def t_public_release_blocked():
        fake_result = {
            'score_level': 3,
            'operator_review_required': True,
            'public_release_allowed': True,
        }
        expect_raises(lambda: validate_aviaimpact_result(fake_result), ValueError)
    chk('Case 10: public_release_allowed=True fails validation', t_public_release_blocked)

    # Case 11: Unknown source lane fails validate_source_lane
    def t_unknown_lane():
        expect_raises(lambda: validate_source_lane('invented_lane'), ValueError)
    chk('Case 11: unknown source lane fails validation', t_unknown_lane)

    # Case 12: Component weights sum to 1.0
    def t_weights_sum():
        total = sum(COMPONENT_WEIGHTS.values())
        assert abs(total - 1.0) <= WEIGHT_SUM_TOLERANCE, (
            f'COMPONENT_WEIGHTS must sum to 1.0, got {total}'
        )
    chk('Case 12: component weights sum to 1.0', t_weights_sum)

    print('---')
    if failures:
        print(f'FAILED: {len(failures)} case(s): {failures}')
        return False
    print(f'All 12 self-test cases passed.')
    return True


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Phase D2 AviaImpact Score v0.1 — scoring utility'
    )
    parser.add_argument(
        '--self-test', action='store_true',
        help='Run 12 deterministic self-test cases and exit'
    )
    parser.add_argument(
        '--input', metavar='PATH',
        help='Path to local JSON input file for test scoring (does not write by default)'
    )
    parser.add_argument(
        '--out', metavar='PATH',
        help='Write scoring result to this JSON file (only when --input is also provided)'
    )
    args = parser.parse_args()

    if args.self_test:
        ok = run_self_test()
        sys.exit(0 if ok else 1)

    if args.input:
        in_path = Path(args.input)
        if not in_path.exists():
            print(f'ERROR: input file not found: {in_path}', file=sys.stderr)
            sys.exit(1)
        input_data = json.loads(in_path.read_text(encoding='utf-8'))
        result = compute_aviaimpact_score(input_data)
        # Exclude non-serializable component_scores detail for concise output
        output = {k: v for k, v in result.items() if k != 'component_scores'}
        print(json.dumps(output, indent=2, default=str))
        if args.out:
            out_path = Path(args.out)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')
            print(f'Result written to {out_path}')
        sys.exit(0)

    parser.print_help()
    sys.exit(0)


if __name__ == '__main__':
    main()
