"""저장된 실패/수정 응답을 모델 호출 없이 비교한다."""
import json
from pathlib import Path
import tempfile
import unittest

from hprc.gates import GateError, apply_hunks
from hprc.patch_audit import numeric_removals
from hprc.pipeline import Run


class PatchNumericAuditTests(unittest.TestCase):
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
