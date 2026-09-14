"""형식이 명시된 경우만 적용하는 선택 실행 경로. 검증 단계를 생략하지 않는다."""
import copy


def workflow_config(cfg, tier):
    out = copy.deepcopy(cfg)
    strategy = out.get('efficiency', {}).get('strategy', 'standard')
    if strategy not in {'standard', 'adaptive'}:
        raise ValueError('unknown workflow strategy')
    single = strategy == 'adaptive' and tier == 'full' and cfg.get('report_format') == 'facts'
    if single:
        out['full']['drafts'] = 1
        out['full']['polish'] = False
    return out, {'strategy': strategy, 'single_draft': single,
                 'reason': 'explicit_facts_format' if single else 'preserve_existing_route',
                 'verification_preserved': True, 'performance_measured': False}
