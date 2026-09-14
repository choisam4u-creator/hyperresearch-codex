import json,os,sys,tempfile
from pathlib import Path
repo=next(p for p in Path(__file__).resolve().parents if (p/'hpr.py').exists())
sys.path.insert(0,str(repo))
from hprc import pipeline
from unittest.mock import patch
fixture=repo/'tests/fixtures/benchmark_inputs.json'
case=next(c for c in json.loads(fixture.read_text())['cases'] if c['id']=='fact-ko-01')
rows=[]
with tempfile.TemporaryDirectory(prefix='hpr-full-route-probe-') as tmp, patch.dict(os.environ,{'HPR_BACKEND':'mock'}):
 for strategy in ('standard','adaptive'):
  root=Path(tmp)/strategy
  report=pipeline.run(root,case['prompt'],'full',run_id='trial',quiet=True,preset='lean',lang='ko',replay_file=str(fixture),case_id=case['id'],report_format='facts',efficiency={'strategy':strategy})
  manifest=json.loads((report.parent/'manifest.json').read_text());steps=[r['step'] for r in manifest['usage']]
  rows.append({'strategy':strategy,'backend':'mock','attempt_count':len(steps),'steps':steps,'critic_steps':[s for s in steps if s.startswith('critic_')],'citecheck_present':'citecheck' in steps,'workflow':manifest.get('workflow'),'config_hash':manifest['runtime']['config_hash'],'code_hash':manifest['runtime']['code_hash']})
result={'scope':'mock_route_observation_not_actual_tokens_or_quality','case_id':case['id'],'tier':'full','preset':'lean','report_format':'facts','observations':rows}
Path(__file__).with_name('full-route-observations.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print([(r['strategy'],r['attempt_count'],r['steps']) for r in rows])
