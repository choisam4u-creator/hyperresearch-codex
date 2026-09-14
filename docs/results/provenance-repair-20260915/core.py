"""Standalone integrity and arithmetic verifier; no model or external dependency."""
import copy
import hashlib
import json
from pathlib import Path
import re
import sys

PHASES={'B4_oldfix':(4,16),'C12_inline':(12,31)}

def require(condition,message):
    if not condition:raise ValueError(message)

def digest(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def textsha(value):return hashlib.sha256(value.encode('utf-8')).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
def filesha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def blind_body(text):
    body=re.sub(r'\A(?:<!--[^\n]*-->\n){1,2}\n?','',text)
    footer=re.search(r'\n## (?:Source details \(auto-generated\)|출처 상세\(자동 생성\))\n\n\|',body)
    if not footer:return body
    review=re.search(r'\n## (?:Verification status|검증 상태|Citation sample check|인용 표본 검사)\n\n',body[:footer.start()])
    return body[:(review.start()+1 if review else footer.start()+1)]

def required_ids(rubric):
    ids=[x['id'] for cat in ('required_facts','required_qualifiers','correct_abstentions') for x in rubric[cat]]
    require(all(isinstance(x,str) and x for x in ids) and len(ids)==len(set(ids)),'Duplicate/invalid required IDs')
    return set(ids)

def checked_usage(usage):
    require(type(usage.get('known')) is bool,'Usage known must be boolean')
    keys=('input_tokens','cached_input_tokens','output_tokens','total_tokens')
    if not usage['known']:
        require(all(usage.get(k) is None for k in keys),'Unknown usage cannot have established totals');return None
    require(all(type(usage.get(k)) is int and usage[k]>=0 for k in keys),'Invalid token counters')
    require(usage['cached_input_tokens']<=usage['input_tokens'],'Cached tokens exceed input')
    require(usage['total_tokens']==usage['input_tokens']+usage['output_tokens'],'Incorrect total tokens')
    return usage

def summarize(calls,runs=0):
    out=dict(runs=runs,calls=len(calls),known_calls=0,unknown_calls=0,input_tokens=0,cached_input_tokens=0,output_tokens=0,total_tokens=0)
    for call in calls:
        u=checked_usage(call)
        if u is None:out['unknown_calls']+=1;continue
        out['known_calls']+=1
        for key in ('input_tokens','cached_input_tokens','output_tokens','total_tokens'):out[key]+=u[key]
    out['uncached_input_tokens']=out['input_tokens']-out['cached_input_tokens'];out['complete']=out['unknown_calls']==0
    return out

def delivery_observations(calls):
    eligible=[c for c in calls if c.get('step')=='writer' or c.get('step','').startswith(('draft_','critic_'))]
    def commands(rows):
        for row in rows:
            items=row.get('items')
            if not isinstance(items,dict) or type(items.get('command_execution')) is not int or items['command_execution']<0:return None
        return sum(r['items']['command_execution'] for r in rows)
    cost=summarize(eligible)
    return {'calls':len(calls),'eligible_calls':len(eligible),'command_executions':commands(calls),'eligible_command_executions':commands(eligible),'eligible_input_tokens':cost['input_tokens'] if cost['complete'] else None,'eligible_output_tokens':cost['output_tokens'] if cost['complete'] else None,'scope':'Observed completed command items and metered usage; prepared bytes are not tokens'}

def validate_assessment(response,packet):
    require(isinstance(response,dict) and isinstance(response.get('reports'),list),'Invalid accepted response')
    reports={r['opaque_id']:r for r in packet['reports']}
    require(len(reports)==len(packet['reports']),'Duplicate packet reports')
    rows=response['reports'];require(len(rows)==len(reports) and {r['opaque_id'] for r in rows}==set(reports),'Assessment report coverage mismatch')
    for row in rows:
        report=reports[row['opaque_id']];context=packet['contexts'][report['context_id']]
        require(type(row['full_report_reviewed']) is bool,'Invalid full report flag')
        req=row['requirements'];require(len(req)==len(required_ids(context['rubric'])) and {r['id'] for r in req}==required_ids(context['rubric']),'Per-report required coverage mismatch')
        require(len({r['id'] for r in row['issues']})==len(row['issues']),'Duplicate issue IDs')
        for item in req+row['issues']:
            issue=item in row['issues'];status=item.get('status')
            require(issue or status in ('met','missing','incorrect','unresolved'),'Invalid requirement status')
            require(not issue or item['severity'] in ('critical','minor'),'Invalid issue severity')
            quote=item['report_quote'];require(isinstance(quote,str) and (not quote or quote in report['report']),'Report quote mismatch')
            require(not (issue or status in ('met','incorrect')) or bool(quote),'Required report quote missing')
            evidence=item['source_evidence'];require(isinstance(evidence,list) and (status=='unresolved' or bool(evidence)),'Required source evidence missing')
            for e in evidence:
                source=report.get('processing_evidence','') if e['source_id']=='PROCESSING' else context['sources'].get(e['source_id'],'')
                require(isinstance(e['quote'],str) and bool(e['quote']) and e['quote'] in source,'Source ID/context/PROCESSING quote mismatch')
        require(isinstance(row['unresolved'],list) and all(isinstance(x,str) for x in row['unresolved']),'Invalid unresolved list')
        failed=bool(row['issues']) or any(x['status'] in ('missing','incorrect') for x in req)
        unknown=not row['full_report_reviewed'] or bool(row['unresolved']) or any(x['status']=='unresolved' for x in req)
        require(row['overall']==('fail' if failed else 'eval_unavailable' if unknown else 'pass'),'Overall contradicts judgments')
    return rows

def reference_lines(text,prefix):
    lines=[];offset=0
    for raw in text.splitlines(keepends=True):
        body=raw.rstrip('\r\n')
        if body:lines.append({'id':f'{prefix}:L{len(lines)+1:04d}','start':offset,'end':offset+len(body),'text':body})
        offset+=len(raw)
    return lines

def materialize(raw,packet,normalize=False):
    # Same original line IDs, Unicode offsets and interval semantics as the
    # frozen private adapter. No semantic judgment is made here.
    reports={r['opaque_id']:r for r in packet['reports']};decoded=[]
    require(len(raw['reports'])==len(reports) and {r['opaque_id'] for r in raw['reports']}==set(reports),'Raw report coverage mismatch')
    for row in raw['reports']:
        report=reports[row['opaque_id']];context=packet['contexts'][report['context_id']]
        lines=reference_lines(report['report'],'report:'+row['opaque_id']);lookup={r['id']:i for i,r in enumerate(lines)}
        result={k:row[k] for k in ('opaque_id','full_report_reviewed','unresolved','overall')}
        for category in ('requirements','issues'):
            result[category]=[]
            for item in row[category]:
                ids=item['report_refs'];require(isinstance(ids,list) and all(x in lookup for x in ids),'Raw report reference ownership mismatch')
                ix=[lookup[x] for x in ids]
                if ix and normalize:ix=list(range(min(ix),max(ix)+1))
                if ix:require(ix==list(range(ix[0],ix[-1]+1)),'Raw report interval is not ordered/contiguous')
                quote=report['report'][lines[ix[0]]['start']:lines[ix[-1]]['end']] if ix else ''
                evidence=[];seen=set()
                for e in item['source_refs']:
                    key=(e['source_id'],e['line_id'])
                    if normalize and key in seen:continue
                    require(key not in seen,'Duplicate source reference');seen.add(key)
                    if e['source_id']=='PROCESSING':text=report.get('processing_evidence','');prefix='report:'+row['opaque_id']+':processing'
                    else:
                        require(e['source_id'] in context['sources'],'Wrong raw source ID')
                        text=context['sources'][e['source_id']];prefix='context:'+report['context_id']+':source:'+e['source_id']
                    source={r['id']:r['text'] for r in reference_lines(text,prefix)}
                    require(e['line_id'] in source,'Raw source/context reference ownership mismatch')
                    evidence.append({'source_id':e['source_id'],'quote':source[e['line_id']]})
                result[category].append({**{k:item[k] for k in (('id','severity','reason') if category=='issues' else ('id','status','reason'))},'report_quote':quote,'source_evidence':evidence})
        decoded.append(result)
    response={'reports':decoded};validate_assessment(response,packet);return response

def canonical_references(raw,packet):
    result=copy.deepcopy(raw);reports={r['opaque_id']:r for r in packet['reports']}
    for row in result['reports']:
        require(row['opaque_id'] in reports,'Normalization report ownership mismatch')
        lines=reference_lines(reports[row['opaque_id']]['report'],'report:'+row['opaque_id']);ids=[x['id'] for x in lines]
        for item in row['requirements']+row['issues']:
            refs=item['report_refs'];require(isinstance(refs,list) and all(x in ids for x in refs),'Normalization ID ownership mismatch')
            if refs:
                positions=[ids.index(x) for x in refs];item['report_refs']=ids[min(positions):max(positions)+1]
            refs=item['source_refs'];item['source_refs']=[x for i,x in enumerate(refs) if x not in refs[:i]]
    return result

def reference_signature(row):
    return (row['overall'], row['full_report_reviewed'],
            sorted((j['id'], j['status']) for j in row['requirements']),
            sorted((j['id'], j['severity'], tuple(j['report_refs']), json.dumps(j['source_refs'], sort_keys=True)) for j in row['issues']),
            sorted(row['unresolved']))

def recompute(bundle):
    require(bundle['schema_version']=='measurement-concrete-v2','Unsupported bundle')
    research=bundle['research'];evaluations=bundle['evaluations'];cases=bundle['cases'];finals=bundle['finals']
    require(len({r['id'] for r in research})==len(research),'Duplicate research IDs')
    require(len({r['id'] for r in evaluations})==len(evaluations),'Duplicate evaluator IDs')
    require({r['study'] for r in evaluations}=={'A','B','D','D2'},'All evaluator ledgers required')
    require(set(finals)==set(PHASES),'Both phase finals required')
    ledger=bundle['ledger_index'];require(set(ledger)=={'A','B','C','D','D2'},'Five original ledgers required')
    for study in ledger:
        expected_eval=[r['id'] for r in evaluations if r['study']==study]
        expected_research=[r['id'] for r in research if {'B4_oldfix':'B','C12_inline':'C'}.get(r['phase'])==study]
        require(sorted(ledger[study]['evaluation'])==sorted(expected_eval) and len(set(ledger[study]['evaluation']))==len(expected_eval),'Original evaluator ledger membership mismatch')
        require(sorted(ledger[study]['research'])==sorted(expected_research) and len(set(ledger[study]['research']))==len(expected_research),'Original research ledger membership mismatch')
    require(len(ledger['A']['evaluation'])==1 and len(ledger['B']['evaluation'])==4 and len(ledger['D']['evaluation'])==1 and not ledger['C']['evaluation'],'Prior failed/successful evaluator attempts missing')
    require(set(cases)=={r['case_id'] for r in research} and len(cases)==8,'Exactly eight frozen cases required')
    identities={};phase_summaries={};allcalls=[]
    for row in research:
        require(row['phase'] in PHASES and row['arm'] in ('before','after') and row['status']=='ok','Invalid research phase/arm/status')
        require(row['case_id'] in cases and cases[row['case_id']]['phase']==row['phase'],'Case phase mismatch')
        if row['phase']=='C12_inline':
            cfg=row['efficiency'];require(cfg['packet_inputs'] is False and cfg['inline_inputs'] is (row['arm']=='after') and cfg['evidence_selection'] is False and cfg['reuse_analysis'] is False and cfg['strategy']=='standard','Inline experiment controls differ')
        calls=row['calls'];require(bool(calls),'Missing per-call research usage')
        require(all(isinstance(c.get('step'),str) and type(c.get('attempt')) is int and c['attempt']>=1 for c in calls),'Missing per-call step/attempt identity')
        require(len({(c['step'],c['attempt']) for c in calls})==len(calls),'Duplicate research step/attempt')
        for call in calls:
            if 'runtime' in call:require(all(call['runtime'].get(k)==row['runtime'].get(k) for k in ('code_hash','prompt_hash')),'Per-call runtime differs from manifest')
        summary=summarize(calls);allcalls+=calls
        run_usage=checked_usage(row['usage'])
        if summary['complete']:
            require(run_usage is not None and all(run_usage[k]==summary[k] for k in ('input_tokens','cached_input_tokens','output_tokens','total_tokens')),'Run usage differs from calls')
        else:require(run_usage is None,'Run marked known despite unknown calls')
        require(textsha(row['report'])==row['report_sha256'],'Original report hash mismatch')
        identity=row['identity'];opaque=identity['opaque_id'];require(opaque not in identities,'Duplicate opaque research IDs')
        require(identity['original_report_sha256']==row['report_sha256'] and identity['blind_report_sha256']==textsha(blind_body(row['report'])),'Original/blind report binding mismatch')
        identities[opaque]=row
    def bind_packet(packet,final_phase=None,calibration=False):
        require(isinstance(packet.get('contexts'),dict) and isinstance(packet.get('reports'),list),'Invalid original packet')
        for report in packet['reports']:
            context=packet['contexts'].get(report['context_id']);require(isinstance(context,dict),'Unknown context')
            if report['opaque_id'] not in identities:
                require(calibration,'Noncalibration report lacks original research binding');continue
            row=identities[report['opaque_id']];case=cases[row['case_id']]
            require(final_phase is None or row['phase']==final_phase,'Cross-phase final report')
            require(report['report']==blind_body(row['report']),'Packet report body differs from original')
            require(context=={k:case[k] for k in ('question','lang','sources','rubric')},'Packet context differs from frozen case')
            require(report.get('processing_evidence')==row['processing_evidence'] and report.get('verified_processing_context')==row['verified_processing_context'],'Processing context differs from bound research')
    accepted={}
    for row in evaluations:
        checked_usage(row['usage']);require(row['status'] in ('ok','failed'),'Incomplete evaluator attempt')
        packet=row.get('packet')
        if row.get('raw_response') is not None:require(digest(row['raw_response'])==row['raw_response_sha256'],'Raw response hash mismatch')
        if row.get('accepted_response') is not None:
            normalized=row.get('reference_normalization')=='exact_interval_and_dedup'
            require((row['status']=='ok' or normalized) and row['review_kind']!='diagnostic' and packet is not None,'Unvalidated response cannot be accepted')
            execution=row['execution'];require(execution['backend']=='codex' and execution['attempt']==1 and execution['web_search'] is False and execution['model']=={'terra':'gpt-5.6-terra','astra':'gpt-6-astra'}[row['reviewer']] and execution['effort']=='low','Accepted evaluator execution mismatch')
            if normalized:
                note=row['normalization'];require(note['semantic_judgments_unchanged'] is True and note['raw_response_sha256']==row['raw_file_sha256'],'Normalization binding mismatch')
                require(row['normalized_response']==canonical_references(row['raw_response'],packet),'Normalization changed more than exact refs')
            bind_packet(packet,calibration=row['purpose']=='calibration')
            raw=row.get('raw_response');require(raw is not None,'Accepted result missing raw response')
            is_reference=any('report_refs' in j for r in raw['reports'] for j in r['requirements']+r['issues'])
            expected=materialize(raw,packet,normalize=row.get('reference_normalization')=='exact_interval_and_dedup') if is_reference else raw
            require(row['accepted_response']==expected,'Accepted response differs from raw deterministic decoding')
            rows=validate_assessment(row['accepted_response'],packet)
            if row['study']=='D2' and row['purpose']!='calibration':
                references={r['opaque_id']:r for r in row.get('normalized_response',raw)['reports']}
                for assessment in rows:
                    accepted.setdefault(assessment['opaque_id'],[]).append({'reviewer':row['reviewer'],'kind':row['review_kind'],'assessment':assessment,'signature':reference_signature(references[assessment['opaque_id']])})
    for phase,(expected_runs,expected_required) in PHASES.items():
        rows=[r for r in research if r['phase']==phase];require(len(rows)==expected_runs,'Phase research count mismatch')
        phase_cases={r['case_id'] for r in rows};require(len(phase_cases)==expected_runs//2,'Phase case count mismatch')
        pairs=[];arms={}
        for case_id in sorted(phase_cases):
            pair=[r for r in rows if r['case_id']==case_id];require(len(pair)==2 and {r['arm'] for r in pair}=={'before','after'},'Pair coverage mismatch')
            pair={r['arm']:r for r in pair}
            if phase=='C12_inline':require(all(pair['before']['runtime'].get(k) is not None and pair['before']['runtime'].get(k)==pair['after']['runtime'].get(k) for k in ('code_hash','prompt_hash')),'Paired inline code/prompt differs')
            a=pair['before']['usage']['total_tokens'];b=pair['after']['usage']['total_tokens']
            pairs.append({'case_id':case_id,'before':a,'after':b,'delta':b-a if a is not None and b is not None else None})
        final=finals[phase];bind_packet(final['packet'],phase)
        assessed=validate_assessment(final['response'],final['packet'])
        require({r['opaque_id'] for r in assessed}=={r['identity']['opaque_id'] for r in rows},'Final report coverage mismatch')
        independent={};different=set()
        for a in assessed:
            support=accepted.get(a['opaque_id'],[])
            roles={role:[x for x in support if x['kind']=='independent' and x['reviewer']==role] for role in ('terra','astra')}
            require(all(len(values)==1 for values in roles.values()),'Two accepted independent reviews required')
            independent[a['opaque_id']]={role:values[0] for role,values in roles.items()}
            if roles['terra'][0]['signature']!=roles['astra'][0]['signature']:different.add(a['opaque_id'])
        require(len(final['disagreements'])==len(set(final['disagreements'])) and set(final['disagreements'])==different,'Disagreement membership differs from independent reviews')
        context_by_id={r['opaque_id']:r['context_id'] for r in final['packet']['reports']}
        adjudicated_contexts={context_by_id[i] for i in different}
        for a in assessed:
            if context_by_id[a['opaque_id']] in adjudicated_contexts:
                candidates=[x['assessment'] for x in accepted[a['opaque_id']] if x['kind']=='adjudication' and x['reviewer']=='astra']
                require(len(candidates)==1 and a==candidates[0],'Final must use the context adjudication')
            else:require(a==independent[a['opaque_id']]['terra']['assessment'],'Final must use the agreed independent assessment')
        for arm in ('before','after'):
            arm_rows=[r for r in rows if r['arm']==arm];arm_ids={r['identity']['opaque_id'] for r in arm_rows};ar=[a for a in assessed if a['opaque_id'] in arm_ids]
            quality={'reports':len(ar),'pass':0,'fail':0,'eval_unavailable':0,'required_total':0,'met':0,'missing':0,'incorrect':0,'unresolved':0,'critical_issues':0,'minor_issues':0,'full_reviewed':0,'unresolved_reports':0}
            for a in ar:
                quality[a['overall']]+=1;quality['full_reviewed']+=a['full_report_reviewed']
                quality['unresolved_reports']+=bool(a['unresolved']) or any(j['status']=='unresolved' for j in a['requirements']) or not a['full_report_reviewed']
                for issue in a['issues']:quality[issue['severity']+'_issues']+=1
                for j in a['requirements']:quality['required_total']+=1;quality[j['status']]+=1
            require(quality['required_total']==expected_required,'Frozen per-arm requirement total mismatch')
            tokens=summarize([c for r in arm_rows for c in r['calls']],len(arm_rows))
            arms[arm]={'tokens':tokens,'quality':quality,'delivery':delivery_observations([c for r in arm_rows for c in r['calls']]),'tokens_per_pass':tokens['total_tokens']/quality['pass'] if tokens['complete'] and quality['pass'] else None}
        before=arms['before']['tokens'];after=arms['after']['tokens'];complete=before['complete'] and after['complete']
        phase_summaries[phase]={'arms':arms,'pairs':pairs,'after_to_before_ratio':after['total_tokens']/before['total_tokens'] if complete and before['total_tokens'] else None,'delta_total_tokens':after['total_tokens']-before['total_tokens'] if complete else None,'after_lower_pairs':sum(p['delta'] is not None and p['delta']<0 for p in pairs)}
    research_total=summarize(allcalls,len(research));evaluator_total=summarize([r['usage'] for r in evaluations])
    return {'research':research_total,'evaluator':evaluator_total,'evaluators_by_study':{name:summarize([r['usage'] for r in evaluations if r['study']==name]) for name in ('A','B','D','D2')},'current_total_tokens':research_total['total_tokens']+evaluator_total['total_tokens'],'complete_cost':research_total['complete'] and evaluator_total['complete'],'phases':phase_summaries,'historical_old20':{'runs':20,'calls':118,'total_tokens':4840608,'included_in_current_total':False},'maintenance':{'metered':False,'included_in_current_total':False}}

def verify(root):
    manifest=read(root/'manifest.json');require(filesha(root/'manifest.json')==(root/'manifest.sha256').read_text().strip(),'Manifest checksum mismatch')
    actual={p.relative_to(root).as_posix():filesha(p) for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in ('manifest.json','manifest.sha256')}
    require(actual==manifest['files'],'Bundle file hashes mismatch')
    bundle=read(root/'bundle.json');require(bundle['summary']==recompute(bundle),'Recomputed summary differs')
    print('verified 4 B runs, 12 C runs, all recorded evaluator attempts, and separate final quality')

if __name__=='__main__':verify(Path(sys.argv[1]) if len(sys.argv)==2 else Path(__file__).resolve().parent)
