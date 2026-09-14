"""호출 없는 근거 비교표와 원문 위치에 결속된 명시적 계산 검증."""
from decimal import Decimal, InvalidOperation
import hashlib
import re


def evidence_matrix(ledger):
    rows = []
    for claim in ledger.get('claims', []):
        rows.append({'claim_id': claim.get('claim_id'), 'statement': claim.get('statement'),
                     'classification': claim.get('classification'),
                     'verification': claim.get('verification', {}),
                     'evidence': claim.get('evidence_links', []),
                     'semantic_atoms': claim.get('semantic_atoms', []),
                     'conditions': 'unknown_unless_explicit_in_semantic_atoms'})
    return {'rows': rows, 'scope': 'recorded_evidence_not_new_adjudication'}


def render_matrix(matrix):
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')
    lines = ['# 근거 비교표 / Evidence matrix', '',
             '미검증 관계를 지지·반박으로 추정하지 않습니다. / Unchecked is not support.', '',
             '| 주장 / Claim | 출처 / Sources | 판정 / Recorded status | 조건 / Conditions |', '|---|---|---|---|']
    for row in matrix['rows']:
        refs = ', '.join(f"{e.get('source_alias')}: {e.get('relation', 'unchecked')}" for e in row['evidence'])
        conditions = [a.get('conditions') for a in row['semantic_atoms'] if a.get('conditions')]
        lines.append('| ' + ' | '.join(map(cell, [row['statement'], refs or 'none', row['verification'].get('status', 'unchecked'), conditions or 'unknown'])) + ' |')
    return '\n'.join(lines) + '\n'


def check_calculation(spec, sources):
    """명시된 operand 원문 위치·단위·연산을 검증한다. operand 선택의 의미는 판정하지 않는다."""
    op = spec.get('operation')
    if op not in {'sum', 'mean', 'difference', 'percent_change'}:
        raise ValueError('unsupported operation')
    operands = spec.get('operands', [])
    if not operands or (op in {'difference', 'percent_change'} and len(operands) != 2):
        raise ValueError('invalid operand count')
    values, units, bindings = [], [], []
    for operand in operands:
        text = sources.get(operand.get('source_id'))
        start, end = operand.get('start'), operand.get('end')
        if not isinstance(text, str) or type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
            raise ValueError('invalid source span')
        raw = text[start:end]
        if raw != operand.get('quote'):
            raise ValueError('source quote mismatch')
        # Exact whole numeric token + explicit unit. No substring matches such as 2 in 12.
        match = re.fullmatch(r'([-+]?\d+(?:,\d{3})*(?:\.\d+)?)\s*(\S*)', raw)
        if not match or match.group(2) != operand.get('unit', ''):
            raise ValueError('quote must contain one value and its declared unit')
        if (start and (text[start-1].isalnum() or text[start-1] in '.,+_-−–—')) or (end < len(text) and (text[end].isalnum() or text[end] in '%_')) or re.match(r'[.,]\d', text[end:]):
            raise ValueError('partial numeric or unit token')
        if not match.group(2) and re.match(r'\s+[A-Za-z%가-힣]+', text[end:]):
            raise ValueError('unit omitted from source quote')
        try:
            value = Decimal(match.group(1).replace(',', ''))
        except InvalidOperation as error:
            raise ValueError('invalid value') from error
        values.append(value); units.append(match.group(2))
        bindings.append({'source_id': operand['source_id'], 'source_sha256': hashlib.sha256(text.encode()).hexdigest(), 'start': start, 'end': end, 'quote': raw})
    if len(set(units)) != 1:
        raise ValueError('mixed units require explicit conversion before calculation')
    if op == 'sum': result = sum(values)
    elif op == 'mean': result = sum(values) / len(values)
    elif op == 'difference': result = values[1] - values[0]
    else:
        if values[0] == 0: raise ValueError('zero denominator')
        result = (values[1] - values[0]) / values[0] * 100
    expected = spec.get('expected')
    if expected is not None:
        try: expected = Decimal(str(expected))
        except InvalidOperation as error: raise ValueError('invalid expected value') from error
        if not expected.is_finite(): raise ValueError('non-finite expected value')
    return {'operation': op, 'result': str(result), 'unit': '%' if op == 'percent_change' else units[0],
            'matches_expected': result == expected if expected is not None else None,
            'bindings': bindings, 'scope': 'arithmetic_and_source_spans_only_not_semantic_validation'}


def input_diagnostics(manifest):
    from .token_policy import usage_summary
    by_step = {}
    for row in manifest.get('usage', []):
        by_step.setdefault(row.get('step', 'unknown'), []).append(row)
    return {'scope': 'prepared_bytes_and_observed_tokens_are_different_measures',
            'profiles': manifest.get('input_profiles', []),
            'actual_by_step': {step: usage_summary(rows) for step, rows in by_step.items()},
            'reuse_events': manifest.get('reuse_events', []),
            'estimated_saved_tokens': None}
