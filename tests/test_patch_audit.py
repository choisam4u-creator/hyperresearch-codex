"""저장된 실패/수정 응답을 모델 호출 없이 비교한다."""
import json
from pathlib import Path
import tempfile
import unittest

from hprc.gates import GateError, apply_hunks, defer_excerpt_absence_findings
from hprc.patch_audit import numeric_removals, qualifier_removals
from hprc.pipeline import Run


class PatchNumericAuditTests(unittest.TestCase):
    def test_deferred_details_survive_general_issue_display_limit(self):
        from hprc.brief import render_brief
        issues = [{'kind': 'high_finding_unresolved', 'message': f'High {n}'} for n in range(12)]
        issues += [{'kind': 'deferred_finding_review', 'message': f'Deferred {n}',
                    'finding_id': f'F{n}', 'quote': f'Unique quote {n}',
                    'source_ids': ['S1'], 'reason': 'excerpt_insufficient'} for n in range(12)]
        usage = dict(input_tokens=0, cached_input_tokens=0, output_tokens=0,
                     calls=0, failed_calls=0, retry_calls=0, unknown_calls=0)
        rendered = render_brief('## 답\n본문', {'status': 'review_required', 'issues': issues}, usage)
        self.assertEqual(12, rendered.count('deferred_finding_review'))
        for n in range(12):
            self.assertIn(f'Unique quote {n}', rendered)

    def test_critic_schema_requires_explicit_evidence_status(self):
        from hprc.schemas import FINDING
        from hprc.critique_policy import CRITIC_COMBINED
        self.assertEqual(set(FINDING['properties']), set(FINDING['required']))
        self.assertIs(CRITIC_COMBINED['properties']['findings']['items'], FINDING)

    def test_ko_and_en_qualifier_loss_has_readable_provenance(self):
        cases = [
            ('ko', '단, 전문 데스크는 제외하고 문제가 없는 경우에만 허용한다.', '모두 허용한다.',
             {'condition', 'exclusion', 'negation'}),
            ('en', 'Only if approved, without minors and excluding trials.', 'Approved for trials.',
             {'condition', 'exclusion', 'negation'}),
        ]
        for lang, old, new, categories in cases:
            rows = qualifier_removals([{'find': old, 'replace': new, 'finding_ids': ['F7']}], lang)
            self.assertEqual(['F7'], rows[0]['finding_ids'])
            self.assertEqual((old, new), (rows[0]['before'], rows[0]['after']))
            self.assertEqual(categories, set(rows[0]['removed_qualifiers']))

    def test_rephrased_or_added_qualifiers_do_not_warn(self):
        self.assertEqual([], qualifier_removals([{'find': 'Only if ready.', 'replace': 'Only if fully ready.'}], 'en'))
        self.assertEqual([], qualifier_removals([{'find': '허용한다.', 'replace': '문제가 없는 경우에만 허용한다.'}], 'ko'))

    def test_excerpt_absence_is_deferred_but_contradiction_and_corrections_remain_actionable(self):
        base = {'critic': 'depth', 'quote': 'Claim.', 'suggested_fix': 'Qualified claim.', 'severity': 'high', 'source_ids': ['S1']}
        absence = {**base, 'id': 'F1', 'problem': 'The supplied evidence does not mention this claim.',
                   'evidence_status': 'excerpt_insufficient'}
        mixed = {**base, 'id': 'F2', 'problem': 'The excerpt does not mention scope. The date is 2025, not 2024.',
                 'evidence_status': 'actionable'}
        source_absence = {**base, 'id': 'F3', 'problem': 'The source says nothing; the excerpt does not mention it.',
                          'evidence_status': 'excerpt_insufficient'}
        legacy = {**base, 'id': 'F4', 'problem': 'The supplied evidence does not mention this claim.'}
        actionable, deferred = defer_excerpt_absence_findings([absence, mixed, source_absence, legacy])
        self.assertEqual(['F2', 'F4'], [row['id'] for row in actionable])
        self.assertEqual(['F1', 'F3'], [row['id'] for row in deferred])
        self.assertEqual('excerpt_absence_is_not_source_absence', deferred[0]['deferral_reason'])

    def test_pipeline_keeps_deferred_finding_out_of_patcher_but_preserves_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Run.__new__(Run)
            run.dir, run.lang, run.known, run.relevant = Path(tmp), 'en', {'S1'}, {'S1'}
            run.G = {'hunk_max_chars': 1200, 'patch_max_ratio': .5}
            run.begin = lambda _: True
            run.end = lambda *args: None
            run.digest = lambda: ''
            run.excerpts = lambda *args: {}
            findings = [
                {'id': 'F1', 'problem': 'excerpt absence', 'suggested_fix': '', 'source_ids': [],
                 'patch_action': 'deferred', 'deferral_reason': 'excerpt_absence_is_not_source_absence'},
                {'id': 'F2', 'problem': 'wrong date', 'suggested_fix': 'New.', 'source_ids': ['S1']},
            ]
            (run.dir / 'draft.md').write_text('Old.', encoding='utf-8')
            (run.dir / 'findings.json').write_text(json.dumps({'findings': findings}), encoding='utf-8')
            received = {}
            def call(name, prompt, schema, inputs, role):
                received.update(json.loads(inputs['findings.json']))
                return {'hunks': [], 'skipped': []}
            run.call = call
            run.step_patch()
            self.assertEqual(['F2'], [row['id'] for row in received['findings']])
            stored = json.loads((run.dir / 'findings.json').read_text(encoding='utf-8'))
            self.assertEqual('deferred', stored['findings'][0]['patch_action'])
    def test_saved_failure_flags_denominator_but_fixed_response_does_not(self):
        root = Path(__file__).resolve().parents[1]
        bundle = json.loads((root / 'docs/results/patch-qualifier-replay-20260915/bundle.json').read_text(encoding='utf-8'))
        contract = bundle['patch_contract']
        draft = contract['application']['draft']
        controls = contract['application']['controls']
        results = []
        for response in (contract['original_replay']['raw_response'], bundle['patch']['raw_response']):
            applied = []
            apply_hunks(draft, response['hunks'], controls['patch_max_ratio'], controls['hunk_max_chars'],
                        preserve_judgment_lang='ko', applied_hunks=applied)
            results.append(numeric_removals(applied))
        self.assertTrue(any('F2' in row['finding_ids'] and '1080' in row['removed_numbers'] for row in results[0]))
        self.assertEqual([], results[1])

    def test_format_and_citation_changes_are_not_number_loss(self):
        self.assertEqual([], numeric_removals([{'find': '1,080.0 [S2]', 'replace': '1080 [S1]'}]))
        self.assertEqual([], numeric_removals([{'find': '3%', 'replace': '3% and 4%'}]))

    def test_correction_and_sign_or_percent_changes_remain_review_signals(self):
        for old, new in [('950', '960'), ('3%', '3'), ('-4', '4'), ('−4', '4'),
                         ('123456789012345678901234567890', '123456789012345678901234567891')]:
            self.assertTrue(numeric_removals([{'find': old, 'replace': new}]))
        self.assertEqual([], numeric_removals([{'find': '−4', 'replace': '-4'}]))

    def test_rejected_or_noop_hunks_do_not_create_signals(self):
        applied = []
        apply_hunks('Keep 37. (judgment) 1080', [
            {'find': '(judgment) 1080', 'replace': 'gone'},
            {'find': 'missing 5', 'replace': 'missing'},
            {'find': 'Keep 37.', 'replace': 'Keep 37.'}], 1, 1200,
            preserve_judgment_lang='en', applied_hunks=applied)
        self.assertEqual([], numeric_removals(applied))
        failed = []
        with self.assertRaises(GateError):
            apply_hunks('37', [{'find': '37', 'replace': 'none'}], 0, 1200, applied_hunks=failed)
        self.assertEqual([], failed)

    def test_pipeline_records_only_applied_hunks_even_when_pairs_repeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Run.__new__(Run)
            run.dir, run.lang, run.known, run.G = Path(tmp), 'en', {'S1'}, {'hunk_max_chars': 1200}
            draft = 'Remove 1080 here. [S1] ' + 'Background. ' * 30
            hunk = {'find': 'Remove 1080 here.', 'replace': 'Revised here.', 'finding_ids': ['F1']}
            run.call = lambda *args: {'hunks': [hunk, hunk], 'skipped': []}
            (run.dir / 'draft.md').write_text(draft, encoding='utf-8')
            run._apply_hunk_step('patcher', 'patcher', 'draft.md', 'report.md', 'patcher', .5, {})
            audit = json.loads((run.dir / 'patcher_numeric_audit.json').read_text(encoding='utf-8'))
            resolution = json.loads((run.dir / 'patcher_resolution.json').read_text(encoding='utf-8'))
            self.assertEqual(['1080'], audit['changes'][0]['removed_numbers'])
            self.assertEqual(1, len(audit['changes']))
            self.assertEqual(['F1'], resolution['applied_finding_ids'])
            self.assertEqual(1, len(resolution['rejected']))


if __name__ == '__main__':
    unittest.main()
