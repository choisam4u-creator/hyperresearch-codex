"""새 모델 호출 없이 검토 진입점을 만든다. 원 보고서의 결론을 새로 추론하지 않는다."""
import html
import re


def _review_quote(value, limit=300):
    value = str(value or '')
    if len(value) > limit:
        value = value[:limit] + '…'
    return '<br>'.join(html.escape(line) for line in value.splitlines())


def render_brief(report, quality, usage, lang='ko', report_format='brief'):
    ko = lang == 'ko'
    title = '# 검토 안내' if ko else '# Review guide'
    chunks = re.split(r'(?m)^##\s+', report)
    chosen = next((c for c in chunks[1:] if re.match(r'(답변|결론|핵심|Answer|Conclusion|Summary)', c, re.I)), None)
    if chosen is None:
        chosen = next((c for c in chunks[1:] if c.strip()), report)
    excerpt = chosen[:900].strip()
    if len(chosen) > 900:
        excerpt += '\n[… 발췌 / excerpt …]'
    rows = [title, '', f"**{quality['status']}** · {report_format}", '',
            '## 보고서 발췌' if ko else '## Report excerpt', '', excerpt, '',
            '## 확인할 항목' if ko else '## Review items', '']
    # 보류·수정 손실의 직접 검토 정보는 일반 경고의 표시 상한에 가리지 않는다.
    issues = quality.get('issues', [])
    detailed_kinds = {'deferred_finding_review', 'qualifier_removal_in_edit'}
    displayed = [issue for index, issue in enumerate(issues)
                 if index < 12 or issue.get('kind') in detailed_kinds]
    for issue in displayed:
        rows.append(f"- {issue['kind']}: {issue['message']}")
        if issue.get('kind') == 'qualifier_removal_in_edit':
            for change in issue.get('changes', [])[:3]:
                ids = ', '.join(change.get('finding_ids', [])) or ('없음' if ko else 'none')
                rows.append(f"  - finding: {ids}")
                rows.append(f"    - before: {_review_quote(change.get('before'))}")
                rows.append(f"    - after: {_review_quote(change.get('after'))}")
            rows.append(f"  - {'전체 기록' if ko else 'Full record'}: {issue.get('audit_file', '')}")
        if issue.get('kind') == 'deferred_finding_review':
            ids = ', '.join(issue.get('source_ids', [])) or ('없음' if ko else 'none')
            rows.append(f"  - finding: {issue.get('finding_id', '')} · sources: {ids}")
            rows.append(f"    - quote: {_review_quote(issue.get('quote'))}")
            rows.append(f"    - reason: {html.escape(str(issue.get('reason', '')))}")
    if not quality.get('issues'):
        rows += ['- 자동 검사에서 추가 신호 없음. 미검증 범위는 상세 기록 참조.' if ko else '- No additional automatic flags; see detailed verification scope.']
    if not usage.get('complete', usage.get('unknown_calls', 0) == 0):
        rows += ['', '**측정된 토큰만 표시: 전체 사용량 미확정**' if ko else '**Known tokens only: total usage is incomplete**']
    scope = quality.get('scope', {}).get('claim_inventory', {})
    if scope:
        rows += ['', f"Candidates: {scope.get('candidates', 0)} · Unchecked: {scope.get('unchecked', 0)} · Missing links: {scope.get('without_complete_links', 0)}"]
    rows += ['', f"Input: {usage['input_tokens']:,} · Cached: {usage['cached_input_tokens']:,} · Output: {usage['output_tokens']:,}",
             f"Calls: {usage['calls']} · Failed: {usage['failed_calls']} · Retries: {usage['retry_calls']} · Unknown: {usage['unknown_calls']}", '',
             '[Report](final_report.md) · [Evidence](evidence_ledger.json) · [Quality](quality.json) · [Usage](usage_summary.json)', '']
    return '\n'.join(rows)
