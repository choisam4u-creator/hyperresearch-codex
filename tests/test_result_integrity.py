"""공개 실측 자료와 판정 사이의 연결이 깨지면 성공으로 표시하지 않는다."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'docs/results/verify_efficiency_results.py'
DATA = ROOT / 'docs/results/packet-inputs-20260914'
spec = importlib.util.spec_from_file_location('result_integrity', SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class ResultIntegrityTests(unittest.TestCase):
    def test_published_data_has_consistent_usage_and_review_bindings(self):
        with contextlib.redirect_stdout(io.StringIO()):
            checker.verify(DATA)

    def test_replacing_report_and_its_hash_cannot_reuse_old_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/'data'
            shutil.copytree(DATA, folder)
            rows = json.loads((folder/'records.json').read_text())
            row = rows['records'][0]
            report = folder/(row['run_id']+'.md')
            report.write_text('검토받지 않은 다른 본문\n')
            row['report_sha256'] = hashlib.sha256(report.read_bytes()).hexdigest()
            (folder/'records.json').write_text(json.dumps(rows))
            with self.assertRaises(AssertionError):
                checker.verify(folder)

    def test_optimized_python_refuses_to_claim_validation(self):
        result = subprocess.run([sys.executable, '-O', str(SCRIPT), str(DATA)],
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('bindings PASS', result.stdout)
        self.assertIn('RuntimeError', result.stderr)

    def test_wrong_total_is_not_a_passing_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)/'data'
            shutil.copytree(DATA, folder)
            rows = json.loads((folder/'records.json').read_text())
            rows['known_tokens'] += 999
            (folder/'records.json').write_text(json.dumps(rows))
            with self.assertRaises(AssertionError):
                checker.verify(folder)


class EvidenceCheckoutTests(unittest.TestCase):
    def test_autocrlf_checkout_preserves_original_evidence_bytes(self):
        if shutil.which('git') is None:
            self.skipTest('Git checkout 검증에는 git이 필요함')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = b'{"evidence": "frozen"}\n'
            subprocess.run(['git','init',str(root)], capture_output=True, check=True)
            shutil.copyfile(ROOT/'.gitattributes', root/'.gitattributes')
            evidence = root/'docs/results/example.json'
            evidence.parent.mkdir(parents=True)
            evidence.write_bytes(payload)
            subprocess.run(['git','-C',str(root),'-c','core.autocrlf=true','add','--','.gitattributes','docs/results/example.json'], capture_output=True, check=True)
            evidence.unlink()
            subprocess.run(['git','-C',str(root),'-c','core.autocrlf=true','checkout-index','--all','--force'], capture_output=True, check=True)
            self.assertEqual(evidence.read_bytes(), payload)
