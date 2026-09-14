"""Standalone E supplement verifier. Baseline C evidence is read, never re-counted."""
import hashlib,importlib.util,json,sys
from pathlib import Path
SPEC=importlib.util.spec_from_file_location('provenance_core',Path(__file__).with_name('core.py'))
if not SPEC.loader or not Path(SPEC.origin).exists():
 SPEC=importlib.util.spec_from_file_location('provenance_core',Path(__file__).with_name('public_verify_template.py'))
core=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(core)
require=core.require
CASES={'holdout-ko-leak-alert','holdout-ko-forest-survival','holdout-en-permit-ledger'}


def quality(rows):
 result={'reports':len(rows),'pass':0,'fail':0,'eval_unavailable':0,'required_total':0,'met':0,'missing':0,'incorrect':0,'unresolved':0,'critical_issues':0,'minor_issues':0,'full_reviewed':0,'unresolved_reports':0}
 for row in rows:
  result[row['overall']]+=1;result['full_reviewed']+=row['full_report_reviewed']
  result['unresolved_reports']+=bool(row['unresolved']) or not row['full_report_reviewed'] or any(x['status']=='unresolved' for x in row['requirements'])
  for x in row['requirements']:result['required_total']+=1;result[x['status']]+=1
  for x in row['issues']:result[x['severity']+'_issues']+=1
 require(result['required_total']==16,'E requires 16 judgments per arm')
 return result


def reference_signature(row):
 return (row['overall'],row['full_report_reviewed'],sorted((j['id'],j['status']) for j in row['requirements']),sorted((j['id'],j['severity'],tuple(j['report_refs']),json.dumps(j['source_refs'],sort_keys=True)) for j in row['issues']),sorted(row['unresolved']))


def recompute(bundle,baseline):
 require(bundle['schema_version']=='known-provenance-repair-v1','Wrong supplement schema')
 require(set(bundle['cases'])==CASES and len(bundle['research'])==3,'Exactly three selected known cases required')
 require(bundle['original_c_summary']==baseline['summary']['phases']['C12_inline'],'Original C result changed')
 require(bundle['calibration_reuse']=={'new_calls':0,'source':'D2 calibrated reference v2','roles':['terra','astra']},'Calibration reuse declaration changed')
 roles={'terra':{'model':'gpt-5.6-terra','effort':'low'},'astra':{'model':'gpt-6-astra','effort':'low'}}
 require(bundle['evaluator_contract']['roles']==roles,'Evaluator role contract changed')
 base_rows={r['id']:r for r in baseline['research']};records=bundle['records'];require(len(records)==6 and len({r['identity']['opaque_id'] for r in records})==6,'Six distinct reports required')
 current={r['id']:r for r in bundle['research']};require(len(current)==3,'Duplicate research IDs')
 originals={};research_calls=[]
 for case_id in CASES:
  require(bundle['cases'][case_id]==baseline['cases'][case_id],'E source/rubric differs from original C')
  rows=[r for r in records if r['case_id']==case_id];require(len(rows)==2 and {r['arm'] for r in rows}=={'before','after'},'E pair coverage differs')
 for row in records:
  identity=row['identity'];opaque=identity['opaque_id'];originals[opaque]=row
  require(identity['case_id']==row['case_id'] and identity['run_id']==row['id'] and identity['arm']==row['arm'],'Identity role mismatch')
  require(core.textsha(row['report'])==identity['original_report_sha256'] and core.textsha(core.blind_body(row['report']))==identity['blind_report_sha256'],'Original/blind report mismatch')
  if row['arm']=='before':
   original=base_rows[row['id']]
   require(original['phase']=='C12_inline' and original['arm']=='after' and original['case_id']==row['case_id'],'Wrong reused baseline')
   require(row['report']==original['report'] and row['usage']==original['usage'],'Reused report/cost differs from C')
   require(row['processing_evidence']==original['processing_evidence'] and row['verified_processing_context']==original['verified_processing_context'],'Reused processing evidence differs')
   require(row['reused'] is True and row['included_in_current_cost'] is False,'Baseline cannot count as new research')
  else:
   run=current[row['id']];require(run['case_id']==row['case_id'] and run['status']=='ok' and run['report_sha256']==identity['original_report_sha256'],'New report does not bind to completed run')
   require(row['reused'] is False and row['included_in_current_cost'] is True,'Incorrect new research flag')
   require(row['usage']==run['usage'],'New usage mismatch')
   calls=run['calls'];require(0<len(calls)<=8 and len({(c['step'],c['attempt']) for c in calls})==len(calls),'Invalid/duplicate research calls')
   cfg=run['config'];require(cfg==bundle['configurations'][run['id']],'Frozen configuration differs');require(cfg['efficiency']['inline_inputs'] is True and cfg['efficiency']['packet_inputs'] is False,'E must retain inline delivery')
   expected=bundle['runtime'][bundle['cases'][row['case_id']]['lang']]
   require(all(run['runtime'][k]==expected[k] for k in ('code_hash','prompt_hash')),'Candidate runtime differs')
   roles={'analyst':'analyst','writer':'writer','critic_dialectic':'critic','critic_instruction':'critic','patcher':'patcher','citecheck':'citecheck'}
   for call in calls:
    role=roles.get(call['step']);require(role is not None and call['role']==role and call['backend']=='codex' and call['attempt']==1 and call['status']=='ok' and call['web_search'] is False,'Research execution control mismatch')
    require(call['model']==cfg['models'][role]['model'] and call['effort']==cfg['models'][role]['effort'],'Research model differs')
    require(all(call['runtime'][k]==expected[k] for k in ('code_hash','prompt_hash')),'Per-call runtime differs')
   cost=core.summarize(calls);u=core.checked_usage(run['usage'])
   require((not cost['complete'] and u is None) or (cost['complete'] and u is not None and all(u[k]==cost[k] for k in ('input_tokens','cached_input_tokens','output_tokens','total_tokens'))),'Research aggregate differs from calls')
   research_calls+=calls
 packet=bundle['packet'];reports={r['opaque_id']:r for r in packet['reports']}
 require(set(reports)==set(originals) and len(packet['reports'])==6,'Packet report coverage mismatch')
 for opaque,report in reports.items():
  row=originals[opaque];case=bundle['cases'][row['case_id']]
  require(packet['contexts'][report['context_id']]=={k:case[k] for k in ('question','lang','sources','rubric')},'Context binding mismatch')
  require(report['report']==core.blind_body(row['report']) and report.get('processing_evidence')==row['processing_evidence'] and report.get('verified_processing_context')==row['verified_processing_context'],'Report/PROCESSING binding mismatch')
 require(len(packet['contexts'])==3,'Unexpected E contexts')
 def bind(sub):
  require(len(sub['contexts'])==1 and len(sub['reports'])==2 and len({r['opaque_id'] for r in sub['reports']})==2,'Each evaluator must receive exactly one pair')
  require(all(k in packet['contexts'] and v==packet['contexts'][k] for k,v in sub['contexts'].items()),'Evaluator context changed')
  require(all(r==reports.get(r['opaque_id']) and r['context_id'] in sub['contexts'] for r in sub['reports']),'Evaluator report scope changed')
 evaluations=bundle['evaluations'];require(len({r['id'] for r in evaluations})==len(evaluations),'Duplicate evaluator IDs')
 require(sorted(bundle['ledger_index']['research'])==sorted(current) and sorted(bundle['ledger_index']['evaluation'])==sorted(r['id'] for r in evaluations),'Original ledger membership differs')
 accepted={};context_reviews={}
 for row in evaluations:
  require(row['status'] in ('ok','failed'),'In-flight evaluator cannot be exported');core.checked_usage(row['usage'])
  if 'packet' in row:bind(row['packet'])
  if 'raw_response' in row:require(core.digest(row['raw_response'])==row['raw_response_sha256'],'Raw response digest mismatch')
  if 'accepted_response' not in row:require(row['status']=='failed','Successful response missing');continue
  require(row['status']=='ok','Failed response cannot silently become final')
  meta=row['execution'];role=row['reviewer'];require(role in ('terra','astra'),'Unexpected reviewer')
  require(meta['backend']=='codex' and meta['model']=={'terra':'gpt-5.6-terra','astra':'gpt-6-astra'}[role] and meta['effort']=='low' and meta['attempt']==1 and meta['web_search'] is False,'Reviewer execution differs')
  require(row['review_kind']==('adjudication' if 'adjudication' in row['id'] else 'independent'),'Reviewer kind differs from attempt')
  require(row['accepted_reference']==core.canonical_references(row['raw_response'],row['packet']),'Reference normalization changed semantic fields')
  note=row['normalization'];require(note['semantic_judgments_unchanged'] is True and note['raw_response_sha256']==row['raw_file_sha256'],'Normalization provenance differs')
  require(core.materialize(row['raw_response'],row['packet'],normalize=True)==row['accepted_response'],'Decoded/raw response mismatch')
  context_id=next(iter(row['packet']['contexts']));context_reviews.setdefault(context_id,[]).append(row)
  for result in core.validate_assessment(row['accepted_response'],row['packet']):accepted.setdefault(result['opaque_id'],[]).append((role,row['review_kind'],result))
 final=core.validate_assessment(bundle['final'],packet)
 final_byid={r['opaque_id']:r for r in final}
 for context_id in packet['contexts']:
  candidates=context_reviews.get(context_id,[])
  independent={role:[r for r in candidates if r['review_kind']=='independent' and r['reviewer']==role] for role in ('terra','astra')}
  require(all(len(rows)==1 for rows in independent.values()),'Exactly one accepted independent review per role and context required')
  terra=independent['terra'][0];astra=independent['astra'][0]
  left={r['opaque_id']:r for r in terra['accepted_reference']['reports']};right={r['opaque_id']:r for r in astra['accepted_reference']['reports']}
  different=any(reference_signature(left[key])!=reference_signature(right[key]) for key in left)
  if different:
   adjudications=[r for r in candidates if r['review_kind']=='adjudication' and r['reviewer']=='astra']
   require(len(adjudications)==1,'Disagreement requires one accepted adjudication')
   chosen=adjudications[0];require(chosen.get('previous_reviews')==[terra['accepted_reference'],astra['accepted_reference']],'Adjudication prior reviews differ')
   require(all(final_byid[r['opaque_id']]==r for r in chosen['accepted_response']['reports']),'Final must equal adjudication for both reports in a disputed pair')
  else:
   for opaque in left:require(any(final_byid[opaque]==r for call in (terra,astra) for r in call['accepted_response']['reports']),'Final must equal an independent result for an undisputed pair')
 costs=core.summarize(research_calls,3);evalcost=core.summarize([r['usage'] for r in evaluations])
 reused=core.summarize([r['usage'] for r in records if r['arm']=='before'],3)
 return {'scope':'Three selected known-case repairs; not heldout or new inline savings evidence','new_research':costs,'evaluations':evalcost,'current_total_tokens':costs['total_tokens']+evalcost['total_tokens'],'complete_cost':costs['complete'] and evalcost['complete'],'reused_baseline':{'reports':3,'previously_measured_total_tokens':reused['total_tokens'],'included_in_current_cost':False},'quality':{arm:quality([r for r in final if originals[r['opaque_id']]['arm']==arm]) for arm in ('before','after')},'calibration':{'reused_from':'D2','new_calls':0},'original_c_results_unchanged':True}


def verify(root,baseline_path=None):
 manifest=core.read(root/'manifest.json');require(core.filesha(root/'manifest.json')==(root/'manifest.sha256').read_text().strip(),'Manifest digest differs')
 actual={f.relative_to(root).as_posix():core.filesha(f) for f in root.rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.name not in ('manifest.json','manifest.sha256')};require(actual==manifest['files'],'Supplement file hashes differ')
 bundle=core.read(root/'bundle.json');baseline_path=baseline_path or root.parent/'inline-measurement-20260915/bundle.json'
 require(core.filesha(baseline_path)==bundle['baseline_bundle_sha256'],'Original C public bundle digest differs')
 require(bundle['summary']==recompute(bundle,core.read(baseline_path)),'Supplement recomputation differs')
 print('verified separate E known-case repair; reused C reports excluded from current cost')

if __name__=='__main__':verify(Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent,Path(sys.argv[2]) if len(sys.argv)>2 else None)
