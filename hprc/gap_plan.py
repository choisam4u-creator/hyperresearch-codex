"""추가 모델 호출 없이 근거 부족 항목을 정렬한다. 완전한 질문 분해가 아니다."""
from .text_select import terms


def plan_gaps(question, claims, limit=2):
    gaps = list(dict.fromkeys(claims.get('gaps', [])))
    query = terms(question)
    contradictions = claims.get('contradictions', [])
    items = []
    for index, gap in enumerate(gaps):
        overlap = len(terms(gap) & query)
        conflict = any(terms(gap) & terms(c.get('note', '')) for c in contradictions)
        items.append({'gap': gap, 'priority': overlap + 3 * bool(conflict), 'order': index,
                      'reason': 'contradiction_overlap' if conflict else 'question_overlap' if overlap else 'analyst_gap',
                      'perspective': 'support_and_counterevidence'})
    items.sort(key=lambda row: (-row['priority'], row['order']))
    return {'selected': items[:max(0, min(2, limit))], 'deferred': items[max(0, min(2, limit)):],
            'method': 'deterministic_overlap_not_semantic_decomposition'}
