"""Standalone verifier for one F patcher replay. No model calls or private files."""
import copy, importlib.util, json, re, sys
from pathlib import Path

SPEC=importlib.util.spec_from_file_location('patch_core',Path(__file__).with_name('core.py'))
if not SPEC.loader or not Path(SPEC.origin).exists():
 SPEC=importlib.util.spec_from_file_location('patch_core',Path(__file__).with_name('public_verify_template.py'))
core=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(core)
require=core.require
CASE='holdout-ko-forest-survival'
GATES=importlib.util.spec_from_file_location('patch_gates',Path(__file__).with_name('gates.py'))
gates=None
if GATES.loader and Path(GATES.origin).exists():
 gates=importlib.util.module_from_spec(GATES);GATES.loader.exec_module(gates)


def sig(row):
 return (row['overall'],row['full_report_reviewed'],sorted((x['id'],x['status']) for x in row['requirements']),sorted((x['id'],x['severity'],tuple(x['report_refs']),json.dumps(x['source_refs'],sort_keys=True)) for x in row['issues']),sorted(row['unresolved']))


def quality(rows):
 out={'reports':len(rows),'pass':0,'fail':0,'eval_unavailable':0,'required_total':0,'met':0,'missing':0,'incorrect':0,'unresolved':0,'critical_issues':0,'minor_issues':0,'full_reviewed':0,'unresolved_reports':0}
 for row in rows:
  out[row['overall']]+=1;out['full_reviewed']+=row['full_report_reviewed'];out['unresolved_reports']+=bool(row['unresolved']) or not row['full_report_reviewed'] or any(x['status']=='unresolved' for x in row['requirements'])
  for x in row['requirements']:out['required_total']+=1;out[x['status']]+=1
  for x in row['issues']:out[x['severity']+'_issues']+=1
 require(out['required_total']==5,'The paired forest rubric requires five judgments per report')
 return out


def _usage(value):
 return core.checked_usage(value)


def replay_application(raw, application, known):
 require(gates is not None,'Missing frozen gates.py')
 draft=application['draft'];controls=application['controls']
 new,rejected=gates.apply_hunks(draft,raw['hunks'],controls['patch_max_ratio'],controls['hunk_max_chars'],preserve_judgment_lang=controls['lang'])
 unknown=[c for c in re.findall(r"\[(S\d+)\]",new) if c not in known]
 if unknown:raise gates.GateError('Unknown citations: '+','.join(unknown))
 require(gates.judgment_sentences(new,controls['lang'])>=gates.judgment_sentences(draft,controls['lang']),'Patcher removed a judgment marker')
 new,_=gates.clean_internal_cites(new,controls['lang'])
 rejected_pairs={(h['find'],h['replace']) for h in rejected}
 resolution={'applied_finding_ids':sorted({fid for h in raw['hunks'] if h['find']!=h['replace'] and (h['find'],h['replace']) not in rejected_pairs for fid in h['finding_ids']}),'rejected':rejected,'skipped':raw.get('skipped',[])}
 return {'report':new,'resolution':resolution}


def _bind_packet(packet, public_packet, reports):
 require(len(packet.get('contexts',{}))==1 and len(packet.get('reports',[]))==2,'Evaluator packet must contain exactly one paired context')
 require(packet['contexts']==public_packet['contexts'],'Evaluator source/rubric context differs')
 byid={r['opaque_id']:r for r in packet['reports']}
 require(set(byid)==set(reports) and all(byid[k]==reports[k] for k in byid),'Evaluator received different report bodies')


def recompute(bundle,baseline):
 require(bundle['schema_version']=='known-patch-replay-v1','Wrong patch replay schema')
 require(bundle['scope']['full_pipeline_rerun'] is False and bundle['scope']['research_rerun'] is False,'F must remain patch-only')
 require(bundle['scope']['not_rerun']==['research','writer','critics','citecheck','quality.json'],'Unexpected rerun scope')
 require(bundle['baseline_bundle_sha256']==core.filesha(Path(bundle['_baseline_path'])),'Baseline public digest differs')
 require(set(bundle['cases'])=={CASE},'Only the selected forest case is allowed')
 case=bundle['cases'][CASE];rubric=case['rubric'];require(len(core.required_ids(rubric))==5,'The complete five-item rubric is required')
 base_records=[r for r in baseline['records'] if r['case_id']==CASE and r['arm']=='after']
 require(len(base_records)==1,'Expected E after record for forest case');base=base_records[0]
 require(case==baseline['cases'][CASE],'Full source lines or rubric differs from public E')
 contract=bundle['patch_contract'];profile=contract['input_profile'];require(len(profile)==4 and sum(x['bytes'] for x in profile.values())==14581,'Expected four immutable patch inputs totaling 14,581 bytes')
 old,new=contract['original_request'],contract['candidate_request']
 require(all(old[k]==new[k] for k in ('name','schema','inputs','role','web_search')) and old['prompt']!=new['prompt'],'Only the patcher prompt may differ')
 actual={k:{'bytes':len(v.encode('utf-8')),'sha256':core.textsha(v)} for k,v in old['inputs'].items()}
 require(contract['application']['draft']==old['inputs']['draft.md'] and contract['application']['controls']['lang']==case['lang'],'Application draft/language differs from immutable request')
 require(actual==profile and contract['delivery']=='input_files' and old['name']=='patcher' and old['role']=='patcher' and old['web_search'] is False,'Patch input profile or delivery differs')
 require(contract['patcher_role']==bundle['patch']['execution']['role'],'Patcher role differs')
 require(contract['patcher_schema']==old['schema']==new['schema'],'Patcher schema differs')
 require(contract['method_sha256'] and contract['step_sha256'] and contract['runtime_sha256'] and contract['gates_sha256'],'Missing production handler/runtime identities')
 require(gates is not None and core.filesha(Path(gates.__file__))==contract['gates_sha256'],'Frozen gate source differs')
 patch=bundle['patch'];require(patch['status']=='ok' and patch['execution']['backend']=='codex' and patch['execution']['attempt']==1 and patch['execution']['web_search'] is False,'Patcher execution controls differ')
 _usage(patch['usage']);require(core.digest(patch['raw_response'])==patch['raw_response_sha256'],'Patcher raw response digest differs')
 require(patch['execution']['model']==contract['patcher_role']['model'] and patch['execution']['effort']==contract['patcher_role']['effort'],'Patcher model/effort differs')
 result=patch['result'];require(core.textsha(result['report'])==patch['report_sha256'],'Patch result report digest differs')
 require(result['request']==new and result['method_sha256']==contract['method_sha256'] and result['step_sha256']==contract['step_sha256'],'Patch application request/handler differs')
 require(result['lint']==patch['lint'] and result['resolution']==patch['resolution'],'Patch cleanup/gate result differs')
 require(patch['lint']==gates.report_lint(result['report'],case['question'],set(case['sources']),case['lang']),'Patch lint differs from the actual patched report')
 actual=replay_application(patch['raw_response'],contract['application'],set(case['sources']))
 require(actual['report']==result['report'] and actual['resolution']==result['resolution'],'Raw hunks do not reproduce the gated patch report')
 records=bundle['records'];require(len(records)==2 and {r['arm'] for r in records}=={'before','after'},'Exactly one before/after pair required')
 byarm={r['arm']:r for r in records};before,after=byarm['before'],byarm['after']
 original=contract['original_replay'];require(original['result']['request']==old and core.textsha(original['result']['report'])==original['report_sha256'],'Original replay request/report hash differs')
 old_actual=replay_application(original['raw_response'],contract['application'],set(case['sources']))
 require(old_actual['report']==before['report'] and old_actual['report']==original['result']['report'] and old_actual['resolution']==original['resolution']==original['result']['resolution'],'Original raw response does not reproduce public E report')
 require(before['reused'] is True and before['included_in_current_cost'] is False and before['id']==base['id'],'E report must be reused and excluded from F cost')
 require(before['report']==base['report'] and before['usage']==base['usage'],'Reused E report or historical usage differs')
 require(before['verified_processing_context']==base['verified_processing_context'] and before['processing_evidence']==base['processing_evidence'],'E processing metadata differs')
 require(after['reused'] is False and after['included_in_current_cost'] is True and after['report']==result['report'] and after['usage']==patch['usage'],'New patch report or usage mismatch')
 require(after['verified_processing_context']==before['verified_processing_context'] and after['processing_evidence']==before['processing_evidence'],'Patch pair processing metadata must remain identical')
 for row in records:
  ident=row['identity'];require(ident['case_id']==CASE and ident['arm']==row['arm'] and core.textsha(row['report'])==ident['original_report_sha256'] and core.textsha(core.blind_body(row['report']))==ident['blind_report_sha256'],'Record identity/hash mismatch')
 reports={r['identity']['opaque_id']:{'opaque_id':r['identity']['opaque_id'],'context_id':next(iter(bundle['packet']['contexts'])),'report':core.blind_body(r['report']),'processing_evidence':r['processing_evidence'],'verified_processing_context':r['verified_processing_context']} for r in records}
 packet=bundle['packet'];require({r['opaque_id']:r for r in packet['reports']}==reports,'Public packet does not bind exactly to records')
 require(len(packet['contexts'])==1 and next(iter(packet['contexts'].values()))=={k:case[k] for k in ('question','lang','sources','rubric')},'Public packet must retain full source lines and rubric')
 evaluations=bundle['evaluations'];require(len({r['id'] for r in evaluations})==len(evaluations),'Duplicate evaluator ID')
 require(bundle['research']==[] and bundle['ledger_index']['research']==[] and bundle['ledger_index']['patch']==[patch['id']] and bundle['ledger_index']['evaluation']==[r['id'] for r in evaluations],'Patch-only ledger membership differs')
 accepted=[];independent={}
 for row in evaluations:
  require(row['status'] in ('ok','failed'),'Incomplete evaluator attempt cannot be exported');_usage(row['usage'])
  if 'raw_response' in row:require(core.digest(row['raw_response'])==row['raw_response_sha256'],'Evaluator raw response digest differs')
  if row['status']=='failed':
   require('raw_response' in row,'Failed evaluator raw response is required')
   require('accepted_response' not in row and 'accepted_reference' not in row,'Failed evaluator cannot be accepted');continue
  require(row['reviewer'] in ('terra','astra') and row['execution']=={'backend':'codex','model':{'terra':'gpt-5.6-terra','astra':'gpt-6-astra'}[row['reviewer']],'effort':'low','attempt':1,'web_search':False},'Evaluator execution differs')
  _bind_packet(row['packet'],packet,reports)
  require(row['accepted_reference']==core.canonical_references(row['raw_response'],row['packet']),'Reference normalization changed more than references')
  note=row['normalization'];require(note['semantic_judgments_unchanged'] is True and note['raw_response_sha256']==row['raw_file_sha256'],'Normalization provenance differs')
  require(row['accepted_response']==core.materialize(row['raw_response'],row['packet'],normalize=True),'Accepted response does not decode raw references')
  core.validate_assessment(row['accepted_response'],row['packet']);accepted.append(row)
  if row['review_kind']=='independent':independent[row['reviewer']]=row
 require(set(independent)=={'terra','astra'} and len([x for x in accepted if x['review_kind']=='independent'])==2,'Two accepted independent reviews are required')
 left={x['opaque_id']:x for x in independent['terra']['accepted_reference']['reports']};right={x['opaque_id']:x for x in independent['astra']['accepted_reference']['reports']}
 disagreements=sorted(k for k in left if sig(left[k])!=sig(right[k]));require(sorted(set(bundle['final']['disagreements']))==disagreements and len(bundle['final']['disagreements'])==len(set(bundle['final']['disagreements'])),'Actual independent-review disagreement list differs')
 final=core.validate_assessment(bundle['final']['response'],packet);fby={x['opaque_id']:x for x in final}
 if disagreements:
  ads=[x for x in accepted if x['review_kind']=='adjudication'];require(len(ads)==1 and ads[0]['reviewer']=='astra','Actual disagreement requires one Astra adjudication')
  require(ads[0]['previous_reviews']==[independent['terra']['accepted_reference'],independent['astra']['accepted_reference']],'Adjudication must receive both actual independent reviews')
  require(all(fby[x['opaque_id']]==x for x in ads[0]['accepted_response']['reports']),'Final must equal actual adjudication')
 else:
  require(not any(x['review_kind']=='adjudication' for x in accepted),'No adjudication allowed without actual disagreement')
  require(all(fby[x['opaque_id']]==x for x in independent['terra']['accepted_response']['reports']),"Agreement final must equal the driver Terra result")
 p=core.summarize([patch['usage']]);e=core.summarize([x['usage'] for x in evaluations]);oldcost=core.summarize([before['usage']],1)
 return {'scope':'One metered patcher replay and its evaluators; no research or full pipeline rerun','new_patch':p,'evaluations':e,'current_total_tokens':p['total_tokens']+e['total_tokens'],'complete_cost':p['complete'] and e['complete'],'reused_baseline':{'reports':1,'previously_measured_total_tokens':oldcost['total_tokens'],'included_in_current_cost':False},'quality':{arm:quality([x for x in final if x['opaque_id']==byarm[arm]['identity']['opaque_id']]) for arm in ('before','after')},'original_e_results_unchanged':True,'not_rerun':bundle['scope']['not_rerun']}


def verify(root,baseline_path=None):
 root=Path(root);manifest=core.read(root/'manifest.json');require(core.filesha(root/'manifest.json')==(root/'manifest.sha256').read_text().strip(),'Manifest digest differs')
 actual={f.relative_to(root).as_posix():core.filesha(f) for f in root.rglob('*') if f.is_file() and f.name not in ('manifest.json','manifest.sha256') and '__pycache__' not in f.parts};require(actual==manifest['files'],'Public file hashes differ')
 bundle=core.read(root/'bundle.json');reproduction=core.read(root/'reproduction.json');require(reproduction==bundle['reproduction'] and reproduction['baseline']=='../provenance-repair-20260915/reproduction.json' and reproduction['patch']=='patcher-only.patch','Reproduction linkage differs')
 require(core.filesha(root/'patcher-only.patch')==reproduction['patch_sha256'],'Patcher-only patch digest differs')
 prompts=reproduction['patcher_prompts']['ko'];require(prompts['before_delivered_sha256']==core.textsha(bundle['patch_contract']['original_request']['prompt']) and prompts['after_delivered_sha256']==core.textsha(bundle['patch_contract']['candidate_request']['prompt']),'Reproduction delivered prompt hashes differ')
 baseline_path=Path(baseline_path or root.parent/'provenance-repair-20260915/bundle.json');bundle['_baseline_path']=str(baseline_path)
 require(bundle['summary']==recompute(bundle,core.read(baseline_path)),'Patch replay summary differs from recomputation')
 print('verified F patch-only replay; E reuse excluded from current F cost')

if __name__=='__main__':verify(Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).resolve().parent,Path(sys.argv[2]) if len(sys.argv)>2 else None)
