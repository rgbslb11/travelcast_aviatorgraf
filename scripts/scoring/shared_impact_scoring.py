#!/usr/bin/env python3
"""
scripts/scoring/shared_impact_scoring.py
Phase D1 — Shared Impact Scoring Framework utilities.

Pure deterministic scoring primitives and guardrail helpers.
No network calls. No Supabase writes. No file I/O by default.
No live score generation from project data.
Does not produce AviaImpact scores.
Does not produce RoadCast scores.
Does not publish graphics or broadcast outputs.
Operator review is required before any result becomes a public claim.
Empty state is better than invented scoring data.

CLI:
  python scripts/scoring/shared_impact_scoring.py --self-test
"""

import argparse
import sys

# ─── Constants ────────────────────────────────────────────────────────────────

SCORE_MIN = 0
SCORE_MAX = 5

VALID_SOURCE_LANES = {
    'faa_operational_truth',
    'aviation_weather_truth',
    'public_weather_alert_truth',
    'forecast_proxy',
    'routecast_geometry_scaffold',
    'routecast_context_match',
    'atcscc_context_match',
    'manual_operator_review',
}

GENERIC_0_5_LABELS = {
    0: 'No Known Impact',
    1: 'Minimal Context',
    2: 'Monitor',
    3: 'Elevated',
    4: 'High',
    5: 'Severe / Critical',
}

VALID_CONFIDENCE_LEVELS = {'high', 'medium', 'low', 'insufficient_data'}

_CONFIDENCE_NORMALIZE = {
    'high': 'high',
    'strong': 'high',
    'confirmed': 'high',
    'medium': 'medium',
    'moderate': 'medium',
    'medium_airport_or_fix_overlap': 'medium',
    'low': 'low',
    'weak': 'low',
    'low_text_context': 'low',
    'none': 'insufficient_data',
    'unknown': 'insufficient_data',
    'unmatched': 'insufficient_data',
    'insufficient': 'insufficient_data',
    'insufficient_data': 'insufficient_data',
}

PROHIBITED_CLAIM_PATTERNS = [
    'nws alert caused faa delay',
    'public alert caused airport delay',
    'routecast geometry caused delay',
    'context match proves impact',
    'forecast proxy is observed truth',
    'aviaimpact score generated',
    'roadcast score generated',
    'ground stop inferred',
    'restriction inferred',
    'closure inferred',
    'delay confirmed',
    'delay caused by nws',
    'delay caused by alert',
    'delay caused by forecast',
    'geometry proves delay',
    'match equals impact',
]

WEIGHT_SUM_TOLERANCE = 1e-6


# ─── Core scoring primitives ───────────────────────────────────────────────────

def clamp_score(value, min_value=SCORE_MIN, max_value=SCORE_MAX):
    """Return value clamped to [min_value, max_value]."""
    return max(float(min_value), min(float(max_value), float(value)))


def score_to_level(score):
    """Convert a float score (0.0–5.0) to an integer level (0–5)."""
    return int(round(clamp_score(score)))


def level_to_label(level, scale_key='generic_0_5'):
    """Return the display label for a score level on a given scale."""
    if scale_key == 'generic_0_5':
        return GENERIC_0_5_LABELS.get(int(clamp_score(level)), 'Unknown')
    raise ValueError(f'Unknown scale_key: {scale_key!r}')


def weighted_score(components, weights):
    """
    Compute a weighted average score from component scores and weights.

    components: dict of {key: float_score}
    weights:    dict of {key: float_weight}

    Weights must sum to 1.0 within WEIGHT_SUM_TOLERANCE.
    Keys must match. Returns float in [SCORE_MIN, SCORE_MAX].
    """
    if not components:
        raise ValueError('weighted_score: components must not be empty')
    if not weights:
        raise ValueError('weighted_score: weights must not be empty')
    if set(components.keys()) != set(weights.keys()):
        raise ValueError(
            f'weighted_score: component keys {set(components.keys())} '
            f'do not match weight keys {set(weights.keys())}'
        )
    weight_sum = sum(weights.values())
    if abs(weight_sum - 1.0) > WEIGHT_SUM_TOLERANCE:
        raise ValueError(
            f'weighted_score: weights must sum to 1.0, got {weight_sum}'
        )
    total = sum(clamp_score(components[k]) * weights[k] for k in components)
    return clamp_score(total)


def normalize_confidence(confidence):
    """
    Normalize a confidence string to a canonical value.

    Returns one of: 'high', 'medium', 'low', 'insufficient_data'.
    Unknown values map to 'insufficient_data'.
    """
    if confidence is None:
        return 'insufficient_data'
    normalized = _CONFIDENCE_NORMALIZE.get(str(confidence).lower().strip())
    return normalized if normalized else 'insufficient_data'


def explain_score_components(components, weights):
    """
    Return a structured explanation of how components contributed to a score.

    Returns a dict with keys: components, total_weighted_score,
    total_level, total_label, note.
    """
    total = weighted_score(components, weights)
    level = score_to_level(total)
    label = level_to_label(level)
    component_list = [
        {
            'key': k,
            'score': clamp_score(components[k]),
            'weight': weights[k],
            'contribution': clamp_score(components[k]) * weights[k],
        }
        for k in components
    ]
    return {
        'components': component_list,
        'total_weighted_score': total,
        'total_level': level,
        'total_label': label,
        'note': (
            'Explanation is informational only. '
            'Operator review required before any public claim.'
        ),
    }


# ─── Empty state and guardrail helpers ────────────────────────────────────────

def empty_state_result(reason):
    """
    Return a standardized empty-state result dict.

    Use when required inputs are missing, stale, or insufficient.
    Empty state is better than invented scoring data.
    """
    return {
        'score_level': None,
        'score_label': None,
        'score_confidence': 'insufficient_data',
        'empty_state': True,
        'empty_state_reason': reason,
        'operator_review_required': True,
        'public_release_allowed': False,
        'disclaimer': (
            'No score generated — insufficient source data. '
            'Empty state is better than invented scoring data.'
        ),
    }


def require_operator_review(result):
    """
    Enforce that a result dict has operator_review_required = True.

    Returns the modified result. Raises ValueError if already False.
    """
    if result.get('operator_review_required') is False:
        raise ValueError(
            'require_operator_review: operator_review_required=False — '
            'operator review may not be bypassed'
        )
    result['operator_review_required'] = True
    return result


def assert_no_public_release(result):
    """
    Enforce that a result dict has public_release_allowed = False.

    Returns the modified result. Raises ValueError if already True.
    """
    if result.get('public_release_allowed') is True:
        raise ValueError(
            'assert_no_public_release: public_release_allowed=True — '
            'public release requires explicit operator approval'
        )
    result['public_release_allowed'] = False
    return result


# ─── Validation helpers ────────────────────────────────────────────────────────

def validate_source_lane(source_lane_key):
    """
    Validate that source_lane_key is in the registered lane set.

    Raises ValueError for unknown lanes. Returns the key unchanged if valid.
    """
    if source_lane_key not in VALID_SOURCE_LANES:
        raise ValueError(
            f'validate_source_lane: unknown source lane {source_lane_key!r}. '
            f'Valid lanes: {sorted(VALID_SOURCE_LANES)}'
        )
    return source_lane_key


def validate_no_prohibited_claim(text):
    """
    Check that text does not contain prohibited claim patterns.

    Raises ValueError naming the first prohibited pattern found.
    Returns the text unchanged if clean.
    """
    if not isinstance(text, str):
        raise TypeError(
            f'validate_no_prohibited_claim: expected str, got {type(text).__name__}'
        )
    lower = text.lower()
    for pattern in PROHIBITED_CLAIM_PATTERNS:
        if pattern in lower:
            raise ValueError(
                f'validate_no_prohibited_claim: prohibited claim pattern found: '
                f'{pattern!r} in text: {text[:120]!r}'
            )
    return text


# ─── Self-test ────────────────────────────────────────────────────────────────

def _run_self_test():
    """
    Run unit-like checks on all scoring primitives.
    Prints PASS/FAIL for each check. Returns True if all pass.
    No file I/O. No Supabase writes. No network calls.
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

    print('D1 shared_impact_scoring self-test')
    print('---')

    # ── clamp_score ──
    def t_clamp_basic():
        assert clamp_score(3.0) == 3.0
        assert clamp_score(-1) == 0.0
        assert clamp_score(6) == 5.0
        assert clamp_score(0) == 0.0
        assert clamp_score(5) == 5.0
    chk('clamp_score basic', t_clamp_basic)

    def t_clamp_custom():
        assert clamp_score(0.5, min_value=1.0, max_value=4.0) == 1.0
        assert clamp_score(5.0, min_value=1.0, max_value=4.0) == 4.0
    chk('clamp_score custom bounds', t_clamp_custom)

    # ── score_to_level ──
    def t_score_to_level():
        assert score_to_level(0.0) == 0
        assert score_to_level(1.4) == 1
        assert score_to_level(1.5) == 2
        assert score_to_level(4.9) == 5
        assert score_to_level(5.0) == 5
        assert score_to_level(-1) == 0
        assert score_to_level(99) == 5
    chk('score_to_level', t_score_to_level)

    # ── level_to_label ──
    def t_level_labels():
        assert level_to_label(0) == 'No Known Impact'
        assert level_to_label(1) == 'Minimal Context'
        assert level_to_label(2) == 'Monitor'
        assert level_to_label(3) == 'Elevated'
        assert level_to_label(4) == 'High'
        assert level_to_label(5) == 'Severe / Critical'
    chk('level_to_label generic_0_5', t_level_labels)
    chk('level_to_label unknown scale raises',
        lambda: expect_raises(lambda: level_to_label(1, scale_key='bad'), ValueError))

    # ── weighted_score ──
    def t_weighted_balanced():
        result = weighted_score({'a': 3.0, 'b': 1.0}, {'a': 0.5, 'b': 0.5})
        assert abs(result - 2.0) < 1e-9, f'Expected 2.0, got {result}'
    chk('weighted_score balanced', t_weighted_balanced)

    def t_weighted_full():
        assert weighted_score({'x': 4.0}, {'x': 1.0}) == 4.0
    chk('weighted_score full weight', t_weighted_full)

    chk('weighted_score bad sum raises',
        lambda: expect_raises(lambda: weighted_score({'a': 2.0}, {'a': 0.7}), ValueError))
    chk('weighted_score key mismatch raises',
        lambda: expect_raises(lambda: weighted_score({'a': 2.0}, {'b': 1.0}), ValueError))
    chk('weighted_score empty raises',
        lambda: expect_raises(lambda: weighted_score({}, {}), ValueError))

    def t_weighted_clamps():
        assert weighted_score({'a': 10.0}, {'a': 1.0}) == 5.0
    chk('weighted_score clamps output', t_weighted_clamps)

    # ── normalize_confidence ──
    def t_normalize():
        assert normalize_confidence('high') == 'high'
        assert normalize_confidence('strong') == 'high'
        assert normalize_confidence('medium') == 'medium'
        assert normalize_confidence('moderate') == 'medium'
        assert normalize_confidence('low') == 'low'
        assert normalize_confidence('unmatched') == 'insufficient_data'
        assert normalize_confidence(None) == 'insufficient_data'
        assert normalize_confidence('garbage') == 'insufficient_data'
        assert normalize_confidence('medium_airport_or_fix_overlap') == 'medium'
        assert normalize_confidence('low_text_context') == 'low'
    chk('normalize_confidence', t_normalize)

    # ── empty_state_result ──
    def t_empty_state():
        r = empty_state_result('test reason')
        assert r['score_level'] is None
        assert r['empty_state'] is True
        assert r['operator_review_required'] is True
        assert r['public_release_allowed'] is False
        assert 'disclaimer' in r
        assert r['empty_state_reason'] == 'test reason'
    chk('empty_state_result structure', t_empty_state)

    # ── require_operator_review ──
    def t_require_review():
        assert require_operator_review({})['operator_review_required'] is True
    chk('require_operator_review sets flag', t_require_review)
    chk('require_operator_review raises on False',
        lambda: expect_raises(
            lambda: require_operator_review({'operator_review_required': False}), ValueError
        ))

    # ── assert_no_public_release ──
    def t_no_public():
        assert assert_no_public_release({})['public_release_allowed'] is False
    chk('assert_no_public_release sets False', t_no_public)
    chk('assert_no_public_release raises on True',
        lambda: expect_raises(
            lambda: assert_no_public_release({'public_release_allowed': True}), ValueError
        ))

    # ── validate_source_lane ──
    def t_valid_lanes():
        for lane in sorted(VALID_SOURCE_LANES):
            assert validate_source_lane(lane) == lane
    chk('validate_source_lane all known lanes', t_valid_lanes)
    chk('validate_source_lane unknown raises',
        lambda: expect_raises(lambda: validate_source_lane('invented_lane'), ValueError))

    # ── validate_no_prohibited_claim ──
    def t_clean_text():
        r = validate_no_prohibited_claim('NWS alert context is present near this airport.')
        assert r == 'NWS alert context is present near this airport.'
    chk('validate_no_prohibited_claim clean text', t_clean_text)

    chk('validate_no_prohibited_claim nws delay',
        lambda: expect_raises(
            lambda: validate_no_prohibited_claim('NWS alert caused FAA delay at JFK.'), ValueError
        ))
    chk('validate_no_prohibited_claim aviaimpact',
        lambda: expect_raises(
            lambda: validate_no_prohibited_claim('AviaImpact score generated for ORD.'), ValueError
        ))
    chk('validate_no_prohibited_claim ground stop',
        lambda: expect_raises(
            lambda: validate_no_prohibited_claim('Ground stop inferred from NWS alert.'), ValueError
        ))
    chk('validate_no_prohibited_claim geometry delay',
        lambda: expect_raises(
            lambda: validate_no_prohibited_claim('RouteCast geometry caused delay.'), ValueError
        ))
    chk('validate_no_prohibited_claim type error',
        lambda: expect_raises(lambda: validate_no_prohibited_claim(123), TypeError))

    # ── explain_score_components ──
    def t_explain():
        e = explain_score_components({'wx': 3.0, 'ops': 1.0}, {'wx': 0.6, 'ops': 0.4})
        assert 'components' in e
        assert 'total_weighted_score' in e
        assert 'total_level' in e
        assert 'total_label' in e
        assert isinstance(e['components'], list)
        assert len(e['components']) == 2
        for c in e['components']:
            assert 'key' in c and 'score' in c and 'weight' in c and 'contribution' in c
        expected_total = 3.0 * 0.6 + 1.0 * 0.4
        assert abs(e['total_weighted_score'] - expected_total) < 1e-9
    chk('explain_score_components structure', t_explain)

    print('---')
    if failures:
        print(f'FAILED: {len(failures)} check(s): {failures}')
        return False
    total_checks = 24
    print(f'All {total_checks} checks passed.')
    return True


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Phase D1 Shared Impact Scoring Framework — utility module'
    )
    parser.add_argument(
        '--self-test', action='store_true',
        help='Run unit-like checks on all scoring primitives and exit'
    )
    args = parser.parse_args()

    if args.self_test:
        ok = _run_self_test()
        sys.exit(0 if ok else 1)

    parser.print_help()
    sys.exit(0)


if __name__ == '__main__':
    main()
