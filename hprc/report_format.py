"""질문 유형별 형식 지시. 분량이나 모델 호출 수를 늘리지 않는다."""
FORMATS = {'brief', 'facts', 'comparison', 'analysis'}
_GUIDES = {
    'ko': {
        'facts': '답변 절은 확인할 사실별로 짧게 정리하라. 각 사실에 직접 출처와 적용 날짜·조건을 붙이고, 확인 불가는 별도로 표시하라.',
        'comparison': '답변 절은 같은 기준의 비교표를 우선하라. 항목·조건·출처를 각 행에 붙이고, 미확인 값을 추정으로 채우지 마라. 결론의 선택 기준과 예외를 명시하라.',
        'analysis': '답변 절을 핵심 주장, 뒷받침 근거, 반대 근거, 한계 순으로 구성하라. 인과와 상관을 구분하고 반대 근거를 찾지 못한 경우 없다고 단정하지 마라.',
    },
    'en': {
        'facts': 'Organize the Answer by short factual claims. Attach direct citations and applicable dates/conditions to each; separate unknowns.',
        'comparison': 'Prefer a like-for-like comparison table inside Answer. Include conditions and citations per row; leave unknown cells explicit. State decision criteria and exceptions.',
        'analysis': 'Organize Answer as key claims, supporting evidence, counterevidence, and limitations. Separate correlation from causation; failure to find counterevidence does not establish its absence.',
    },
}


def format_instruction(kind='brief', lang='ko'):
    if kind not in FORMATS:
        raise ValueError('모르는 보고서 형식')
    if kind == 'brief':
        return ''
    guide = _GUIDES.get(lang, _GUIDES['ko'])[kind]
    guard = ('기존 필수 절 제목·원 질문·판단 표시를 유지하고 지정 분량을 늘리지 마라.' if lang == 'ko'
             else 'Keep mandatory section headings, the original question, and judgment markers. Do not increase the specified length.')
    return '\n\n' + guide + '\n' + guard
