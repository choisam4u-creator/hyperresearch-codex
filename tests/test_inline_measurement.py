"""Published observations must remain reproducible and evidence-bound offline."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'docs/results/inline-measurement-20260915'
spec = importlib.util.spec_from_file_location('inline_measurement_verify', DATA / 'verify.py')
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class PublishedInlineMeasurementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = json.loads((DATA / 'bundle.json').read_text(encoding='utf-8'))

    def test_standalone_verification_under_optimized_python(self):
        result = subprocess.run([sys.executable, '-O', str(DATA / 'verify.py')],
                                capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('separate final quality', result.stdout)

    def test_wrong_source_identity_cannot_support_final_quality(self):
        data = copy.deepcopy(self.bundle)
        item = next(j for r in data['finals']['C12_inline']['response']['reports']
                    for j in r['requirements'] if j['source_evidence'])
        item['source_evidence'][0]['source_id'] = 'S_FOREIGN'
        with self.assertRaisesRegex(ValueError, 'Source ID/context/PROCESSING'):
            verify.recompute(data)

    def test_unknown_usage_cannot_keep_established_totals(self):
        data = copy.deepcopy(self.bundle)
        data['evaluations'][0]['usage']['known'] = False
        with self.assertRaisesRegex(ValueError, 'Unknown usage'):
            verify.recompute(data)

    def test_omitted_research_call_cannot_keep_original_total(self):
        data = copy.deepcopy(self.bundle)
        data['research'][0]['calls'].pop()
        with self.assertRaisesRegex(ValueError, 'Run usage differs from calls'):
            verify.recompute(data)

    def test_final_cannot_select_initial_review_instead_of_adjudication(self):
        data = copy.deepcopy(self.bundle)
        opaque = next(r['identity']['opaque_id'] for r in data['research']
                      if r['case_id'] == 'holdout-ko-leak-alert' and r['arm'] == 'after')
        initial = next(r for e in data['evaluations']
                       if e['review_kind'] == 'independent' and e['reviewer'] == 'terra'
                       for r in e.get('accepted_response', {}).get('reports', [])
                       if r['opaque_id'] == opaque)
        final = data['finals']['C12_inline']['response']['reports']
        index = next(i for i, r in enumerate(final) if r['opaque_id'] == opaque)
        self.assertNotEqual(final[index], initial)
        final[index] = initial
        with self.assertRaisesRegex(ValueError, 'Final must use the context adjudication'):
            verify.recompute(data)

    def test_disagreements_cannot_be_dropped(self):
        data = copy.deepcopy(self.bundle)
        data['finals']['C12_inline']['disagreements'] = []
        with self.assertRaisesRegex(ValueError, 'Disagreement membership'):
            verify.recompute(data)
