"""새 모델 호출 없이 검토 진입점을 만든다. 원 보고서의 결론을 새로 추론하지 않는다."""
import re


def render_brief(report, quality, usage, lang='ko'):
    ko = lang == 'ko'
    title = '# 검토 안내' if ko else '# Review guide'
    chunks = re.split(r'(?m)^##\s+', report)
    chosen = next((c for c in chunks[1:] if re.match(r'(답변|결론|핵심|Answer|Conclusion|Summary)', c, re.I)), None)
    if chosen is None:
        chosen = next((c for c in chunks[1:] if c.strip()), report)
    excerpt = chosen[:900].strip()
    if len(chosen) > 900:
        excerpt += '\n[… 발췌 / excerpt …]'
    rows = [title, '', f"**{quality['status']}**", '',
            '## 보고서 발췌' if ko else '## Report excerpt', '', excerpt, '',
            '## 확인할 항목' if ko else '## Review items', '']
    rows += [f"- {i['kind']}: {i['message']}" for i in quality.get('issues', [])[:12]]
    if not quality.get('issues'):
        rows += ['- 자동 검사에서 추가 신호 없음. 미검증 범위는 상세 기록 참조.' if ko else '- No additional automatic flags; see detailed verification scope.']
    rows += ['', f"Input: {usage['input_tokens']:,} · Cached: {usage['cached_input_tokens']:,} · Output: {usage['output_tokens']:,}",
             f"Calls: {usage['calls']} · Failed: {usage['failed_calls']} · Retries: {usage['retry_calls']} · Unknown: {usage['unknown_calls']}", '',
             '[Report](final_report.md) · [Evidence](evidence_ledger.json) · [Quality](quality.json) · [Usage](usage_summary.json)', '']
    return '\n'.join(rows)
