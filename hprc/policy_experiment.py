"""기능 ON/OFF 비교에서 사전 지정한 설정만 다른지 검증한다. 모델을 부르지 않는다."""
import copy
from .token_policy import fingerprint

ALLOWED = {'verification.semantic', 'critic_policy.combine_light', 'critic_policy.compact_inputs'}


def compare_policy(left, right, changed_paths):
    paths = set(changed_paths)
    if not paths or not paths <= ALLOWED:
        raise ValueError('등록된 비교 설정만 지정해야 합니다')
    if left.get('case_id') != right.get('case_id') or left.get('input_hash') != right.get('input_hash'):
        raise ValueError('고정 입력이 다릅니다')
    a,b = left.get('runtime_metadata',{}),right.get('runtime_metadata',{})
    for runtime in (a,b):
        if runtime.get('runtime_consistent') is not True:
            raise ValueError('호출별 구성 일치 기록이 필요합니다')
    for key in ('code_revision','prompt_hashes','benchmark_version','frozen_at','frozen_input_hash','as_of','role_assignments'):
        if not a.get(key) or a.get(key) != b.get(key):
            raise ValueError(f'통제 조건 불일치: {key}')
    configs=[copy.deepcopy(r.get('config_snapshot')) for r in (a,b)]
    if not all(isinstance(c,dict) for c in configs): raise ValueError('설정 스냅샷이 필요합니다')
    for runtime,config in zip((a,b),configs):
        if runtime.get('config_hash') != fingerprint(config): raise ValueError('설정 해시 불일치')
    changes={}
    for path in sorted(paths):
        parent,key=path.split('.')
        if any(parent not in cfg or key not in cfg[parent] for cfg in configs): raise ValueError('비교 설정이 누락됐습니다')
        values=[cfg[parent].pop(key) for cfg in configs]
        if values[0] == values[1]: raise ValueError('선언한 설정이 바뀌지 않았습니다')
        changes[path]={'baseline':values[0],'candidate':values[1]}
    if configs[0] != configs[1]: raise ValueError('허용하지 않은 출력·예산·기타 설정도 바뀌었습니다')
    qualities = (left.get('quality_qualified'), right.get('quality_qualified'))
    preserved = False if any(q is False for q in qualities) else True if all(q is True for q in qualities) else None
    return {'case_id':left['case_id'],'mode':'explicit_policy_toggle','changes':changes,
            'total_token_delta':right['reported_total_tokens']-left['reported_total_tokens'] if left.get('unknowncalls') == 0 and right.get('unknowncalls') == 0 else None,
            'quality_preserved': preserved,
            'scope':'selected_rubric_not_full_factual_accuracy'}
