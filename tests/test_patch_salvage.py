"""Reject marker-removing hunks without discarding independent valid fixes."""
import json
from pathlib import Path
import tempfile
import unittest
from hprc.pipeline import Run


class PatchSalvageTests(unittest.TestCase):
    def apply(self, hunks, ratio=0.5):
        draft = '# Question: test\n\nOld detail [S1].\n\n(judgment) Keep the staffed alternative.\n' + 'Background evidence. ' * 30
        with tempfile.TemporaryDirectory() as tmp:
            run = Run.__new__(Run)
            run.dir = Path(tmp)
            run.lang = 'en'
            run.known = {'S1'}
            run.G = {'hunk_max_chars': 1200}
            run.call = lambda *args: {'hunks': hunks, 'skipped': []}
            (run.dir / 'draft.md').write_text(draft)
            run._apply_hunk_step('patcher', 'patcher', 'draft.md', 'report.md', 'patcher', ratio, {})
            return draft, (run.dir / 'report.md').read_text(), json.loads((run.dir / 'patcher_resolution.json').read_text())

    def test_valid_fix_survives_marker_removal_in_other_hunk(self):
        _, result, resolution = self.apply([
            {'find': 'Old detail [S1].', 'replace': 'Corrected detail [S1].', 'finding_ids': ['F1']},
            {'find': '(judgment) Keep', 'replace': '(no source) Keep', 'finding_ids': ['F2']},
        ])
        self.assertIn('Corrected detail [S1].', result)
        self.assertIn('(judgment) Keep', result)
        self.assertEqual(['F1'], resolution['applied_finding_ids'])
        self.assertEqual('judgment_marker_removed', resolution['rejected'][0]['reason'])

    def test_unknown_citation_still_rejects_whole_patch(self):
        before, result, resolution = self.apply([
            {'find': 'Old detail [S1].', 'replace': 'Corrected detail [S9].', 'finding_ids': ['F1']},
        ])
        self.assertEqual(before, result)
        self.assertEqual([], resolution['applied_finding_ids'])
        self.assertIn('gate_error', resolution)

    def test_total_change_limit_still_rejects_whole_patch(self):
        before, result, resolution = self.apply([
            {'find': 'Old detail [S1].', 'replace': 'Corrected detail [S1].', 'finding_ids': ['F1']},
        ], ratio=0)
        self.assertEqual(before, result)
        self.assertIn('gate_error', resolution)
