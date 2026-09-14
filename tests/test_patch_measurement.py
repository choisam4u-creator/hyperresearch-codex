import hashlib,json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PUBLIC=ROOT/'docs/results/patch-qualifier-replay-20260915'
BASE=ROOT/'docs/results/provenance-repair-20260915/bundle.json'

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def update_manifest(root):
 manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'));manifest['files']['bundle.json']=digest(root/'bundle.json')
 (root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8');(root/'manifest.sha256').write_text(digest(root/'manifest.json')+'\n',encoding='utf-8')

class PatchReplayPublicBundleTests(unittest.TestCase):
 def test_standalone_verifier_accepts_public_bundle(self):
  result=subprocess.run([sys.executable,str(PUBLIC/'verify.py'),str(PUBLIC),str(BASE)],text=True,capture_output=True)
  self.assertEqual(0,result.returncode,result.stderr);self.assertIn('patch-only replay',result.stdout)
 def test_verifier_recomputes_summary_and_excludes_reused_e_cost(self):
  with tempfile.TemporaryDirectory() as td:
   copied=Path(td)/'bundle';shutil.copytree(PUBLIC,copied)
   bundle=json.loads((copied/'bundle.json').read_text(encoding='utf-8'))
   self.assertEqual([],bundle['research']);self.assertEqual(['patcher-replay'],bundle['ledger_index']['patch']);self.assertFalse(bundle['summary']['reused_baseline']['included_in_current_cost'])
   bundle['summary']['current_total_tokens']+=1
   (copied/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
   update_manifest(copied)
   result=subprocess.run([sys.executable,str(copied/'verify.py'),str(copied),str(BASE)],text=True,capture_output=True)
   self.assertNotEqual(0,result.returncode);self.assertIn('summary differs',result.stderr)
 def test_verifier_rejects_raw_hunk_that_no_longer_matches_stored_report(self):
  with tempfile.TemporaryDirectory() as td:
   copied=Path(td)/'bundle';shutil.copytree(PUBLIC,copied);bundle=json.loads((copied/'bundle.json').read_text(encoding='utf-8'))
   bundle['patch']['raw_response']['hunks'][0]['replace']+=' '
   bundle['patch']['raw_response_sha256']=hashlib.sha256(json.dumps(bundle['patch']['raw_response'],ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
   (copied/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');update_manifest(copied)
   result=subprocess.run([sys.executable,str(copied/'verify.py'),str(copied),str(BASE)],text=True,capture_output=True)
   self.assertNotEqual(0,result.returncode);self.assertIn('Raw hunks do not reproduce',result.stderr)
 def test_verifier_rejects_omitted_evaluator_ledger_row(self):
  with tempfile.TemporaryDirectory() as td:
   copied=Path(td)/'bundle';shutil.copytree(PUBLIC,copied);bundle=json.loads((copied/'bundle.json').read_text(encoding='utf-8'))
   bundle['ledger_index']['evaluation']=bundle['ledger_index']['evaluation'][:1]
   (copied/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');update_manifest(copied)
   result=subprocess.run([sys.executable,str(copied/'verify.py'),str(copied),str(BASE)],text=True,capture_output=True)
   self.assertNotEqual(0,result.returncode);self.assertIn('ledger membership',result.stderr)
 def test_public_bundle_has_no_private_absolute_path(self):
  value=(PUBLIC/'bundle.json').read_text(encoding='utf-8')
  self.assertNotIn('/Users/',value);self.assertNotIn('/private/',value)

if __name__=='__main__':unittest.main()
