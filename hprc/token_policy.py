"""사용량 계획과 호출 전 추정. 구독 잔량이나 실제 청구액을 추정하지 않는다."""
import hashlib
import json
import math


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def usage_summary(rows):
    result = dict(input_tokens=0, cached_input_tokens=0, output_tokens=0, unknown_calls=0,
                  calls=len(rows), failed_calls=0, retry_calls=0)
    for row in rows:
        known = row.get('usage_known', bool(row.get('usage')))
        result['failed_calls'] += row.get('status', 'ok') != 'ok'
        result['retry_calls'] += row.get('attempt', 1) > 1
        if not known:
            result['unknown_calls'] += 1
            continue
        u = row.get('usage') or {}
        for key in ('input_tokens', 'cached_input_tokens', 'output_tokens'):
            result[key] += u.get(key, 0)
    # 캐시는 입력에 이미 포함되므로 합계에 다시 더하지 않는다.
    result['total_tokens'] = result['input_tokens'] + result['output_tokens']
    result['complete'] = result['unknown_calls'] == 0
    return result


def estimate_next_input(prompt, inputs, history, role):
    size = len(prompt.encode('utf-8')) + sum(len(v.encode('utf-8')) for v in inputs.values())
    low, high = max(1, math.ceil(size / 4)), max(2048, size + 2048)
    ratios = [u['usage']['input_tokens'] / u['input_bytes'] for u in history
              if u.get('role') == role and u.get('usage_known') and u.get('input_bytes', 0) > 0
              and u.get('usage', {}).get('input_tokens', 0) > 0]
    if ratios:
        high = max(high, math.ceil(size * max(ratios) * 1.25))
    return {'input_low': low, 'input_reservation': high, 'input_bytes': size,
            'basis': 'utf8_heuristic_and_observed_role_max' if ratios else 'utf8_heuristic',
            'hard_cap': False}


def plan_run(cfg, tier, no_search=False, replay=False):
    t = cfg[tier]
    scout = int(not no_search and not replay and 'codex_scout' in cfg['search']['providers'])
    # 초안 및 비평은 최대 개수. patch/citecheck는 근거가 없어 생략될 수 있다.
    ordinary = 1 + (1 if tier == 'light' else 1 + t['loci_max'] + t['drafts'] + 1)
    ordinary += len(t['critics']) + 1 + 1
    ordinary += int(tier == 'full' and t.get('polish', False))
    gaps = int(tier == 'full' and cfg['gap_fetch']['enabled'] and not no_search and not replay)
    optional = int(cfg.get('verification', {}).get('recheck_changed', False) and tier == 'full')
    planned = ordinary + scout + gaps + optional
    attempts = planned * (1 + cfg['budget'].get('max_retries', 1))
    maximum = cfg['budget'].get('max_model_calls')
    if maximum is not None:
        attempts = min(attempts, maximum)
    # 과거 실측에 기반한 넓은 계획 범위일 뿐 새로운 모델의 비용 보장이 아니다.
    low, high = ((380_000, 700_000) if tier == 'light' else (1_200_000, 3_500_000))
    return {'tier': tier, 'preset': cfg['preset'], 'planned_calls_max': planned,
            'attempts_max': attempts, 'input_estimate_range': [low, high],
            'estimate_basis': 'historical_reference_not_model_calibrated',
            'input_stop_threshold': cfg['budget']['max_input_tokens'] or cfg['budget']['default_by_tier'][tier],
            'reservation_enabled': cfg['budget'].get('reserve_input', False),
            'stop_on_unknown': cfg['budget'].get('stop_on_unknown', False),
            'models': cfg['models'], 'gap_fetch_enabled': bool(gaps), 'hard_spending_cap': False,
            'note': 'Failed attempts and retries count. In-flight usage may exceed estimates. Subscription allowance is unknown.'}
