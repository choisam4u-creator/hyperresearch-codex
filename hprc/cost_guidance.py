"""추가 호출 없이 저장된 사용량과 예산을 읽기 쉽게 설명한다."""
from .token_policy import usage_summary


def cost_guidance(cfg, rows, reservations=None, stop_reason=None):
    usage = usage_summary(rows)
    budget = cfg.get('budget', {})
    reserved_input = sum((reservations or {}).values())
    reserved_output = len(reservations or {}) * max(0, int(budget.get('output_reservation', 4096)))
    limits = {'input': budget.get('max_input_tokens'), 'total': budget.get('max_total_tokens'), 'calls': budget.get('max_model_calls')}
    used = {'input':usage['input_tokens'], 'total':usage['total_tokens'], 'calls':usage['calls']}
    remaining = {key: (max(0, limit-used[key]) if limit is not None and (key=='calls' or usage['complete']) else None) for key,limit in limits.items()}
    steps={}
    for row in rows:
        steps.setdefault(row.get('step','unknown'),[]).append(row)
    return {'usage': usage, 'thresholds':limits, 'remaining':remaining, 'reserved_input':reserved_input,
            'reserved_output':reserved_output, 'stop_reason':stop_reason,
            'by_step':{name:usage_summary(items) for name,items in steps.items()},
            'additional_work':{'gap_fetch':bool(cfg.get('gap_fetch',{}).get('enabled')), 'changed_citation_recheck':bool(cfg.get('verification',{}).get('recheck_changed')),
                               'estimate':'unknown_until_inputs_are_selected'},
            'scope':'run_local_not_account_allowance', 'hard_spending_cap':False}


def render_cost_guidance(data, lang='ko'):
    ko=lang=='ko';r=data['remaining'];u=data['usage']
    unknown='미확정' if ko else 'unknown'
    value=lambda v: unknown if v is None else f'{v:,}'
    lines=[('## 토큰과 남은 예산' if ko else '## Tokens and remaining budget'),'',
           f"Input + output: {u['total_tokens']:,}" + (' (측정분)' if not u['complete'] and ko else ' (known only)' if not u['complete'] else ''),
           f"Remaining input: {value(r['input'])} · total: {value(r['total'])} · calls: {value(r['calls'])}",
           f"In-flight reservation: input {data['reserved_input']:,} / output {data['reserved_output']:,}"]
    if data.get('stop_reason'): lines+=['', ('중단 이유: ' if ko else 'Stopped: ')+data['stop_reason']]
    lines += ['', '| 단계 | 호출 | 측정 입력+출력 | 미측정 호출 |' if ko else '| Step | Calls | Known input+output | Unknown calls |', '|---|---:|---:|---:|']
    for name, row in sorted(data['by_step'].items(), key=lambda item: -item[1]['total_tokens']):
        lines.append(f"| {name} | {row['calls']} | {row['total_tokens']:,} | {row['unknown_calls']} |")
    lines+=['', ('추가 조사는 입력이 정해져야 추정할 수 있습니다. 예약은 예상치이며 강제 결제 상한이 아닙니다.' if ko else 'Additional work is estimated after its inputs are selected. Reservations are estimates, not a hard spending cap.')]
    return '\n'.join(lines)+'\n'
