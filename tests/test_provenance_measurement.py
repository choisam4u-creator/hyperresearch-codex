"""The known-case supplement must not rewrite or recount the original study."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'docs/results/provenance-repair-20260915'
BASE = ROOT / 'docs/results/inline-measurement-20260915/bundle.json'
spec = importlib.util.spec_from_file_location('provenance_measurement_verify', DATA / 'verify.py')
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class PublishedProvenanceMeasurementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = json.loads((DATA / 'bundle.json').read_text(encoding='utf-8'))
        cls.baseline = json.loads(BASE.read_text(encoding='utf-8'))

    def test_standalone_verification_under_optimized_python(self):
        result = subprocess.run([sys.executable, '-O', str(DATA / 'verify.py')],
                                capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn('reused C reports excluded', result.stdout)

    def test_reused_report_cannot_be_counted_as_new_research(self):
        data = copy.deepcopy(self.bundle)
        next(r for r in data['records'] if r['arm'] == 'before')['included_in_current_cost'] = True
        with self.assertRaisesRegex(ValueError, 'Baseline cannot count as new research'):
            verify.recompute(data, self.baseline)

    def test_original_quality_results_cannot_be_rewritten(self):
        data = copy.deepcopy(self.bundle)
        data['original_c_summary']['arms']['after']['quality']['pass'] += 1
        with self.assertRaisesRegex(ValueError, 'Original C result changed'):
            verify.recompute(data, self.baseline)
