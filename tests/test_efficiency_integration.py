import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from hprc import pipeline

FIXTURE = Path(__file__).parent / 'fixtures/benchmark_inputs.json'

class EfficiencyIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.env=patch.dict(os.environ,{'HPR_BACKEND':'mock'});self.env.start();self.addCleanup(self.env.stop)
    def run_case(self, rid, **kwargs):
        fixture=kwargs.pop('fixture',FIXTURE)
        case=next(c for c in json.loads(Path(fixture).read_text())['cases'] if c['id']=='fact-ko-01')
        return pipeline.run(self.root,case['prompt'],'light',run_id=rid,quiet=True,lang=case['lang'],
                            replay_file=str(fixture),case_id='fact-ko-01',**kwargs).parent
    def data(self, rid):
        return json.loads((self.root/'research/runs'/rid/'manifest.json').read_text())
    def test_exact_analysis_reuse_skips_call_and_resume_adds_nothing(self):
        opts={'reuse_analysis':True}
        self.run_case('first',efficiency=opts);second=self.run_case('second',efficiency=opts)
        before=self.data('second')
        self.assertFalse(any(x['step']=='analyst' for x in before['usage']))
        self.assertTrue(before['reuse_events'][0]['model_call_skipped'])
        self.run_case('second',efficiency=opts)
        self.assertEqual(before['usage'],self.data('second')['usage'])
        self.assertTrue((second/'evidence_matrix.md').is_file())
    def test_packet_reaches_backend_and_profiles_are_not_tokens(self):
        actual=pipeline.run_step;seen=[]
        def recording(name,prompt,schema,inputs,*args,**kwargs):
            seen.append((name,inputs,prompt));return actual(name,prompt,schema,inputs,*args,**kwargs)
        with patch.object(pipeline,'run_step',side_effect=recording):
            self.run_case('packet',efficiency={'packet_inputs':True,'evidence_selection':True})
        writer=next(x for x in seen if x[0]=='writer')
        self.assertEqual(['_input_packet.md'],list(writer[1]))
        self.assertIn('INPUT CONTRACT',writer[2])
        self.assertIn('claims.json',writer[1]['_input_packet.md'])
        profiles=self.data('packet')['input_profiles']
        self.assertTrue(all(x['before']['scope']=='prepared_not_actual_tokens' for x in profiles))
        self.assertTrue(self.data('packet')['evidence_selections'])
    def test_changed_source_invalidates_cache(self):
        self.run_case('first',efficiency={'reuse_analysis':True})
        fixture=json.loads(FIXTURE.read_text())
        case=next(c for c in fixture['cases'] if c['id']=='fact-ko-01')
        case['sources']['S1']+=' Changed fact.'
        path=self.root/'changed.json';path.write_text(json.dumps(fixture))
        self.run_case('changed',fixture=path,efficiency={'reuse_analysis':True})
        self.assertTrue(any(x['step']=='analyst' for x in self.data('changed')['usage']))
    def test_update_unchanged_reuses_and_changed_runs_delta_analysis(self):
        self.run_case('before')
        self.run_case('same',update_from='before')
        self.assertFalse(any(x['step'].startswith('analyst') for x in self.data('same')['usage']))
        fixture=json.loads(FIXTURE.read_text());case=next(c for c in fixture['cases'] if c['id']=='fact-ko-01')
        case['sources']['S1']+=' Changed fact.'
        path=self.root/'changed.json';path.write_text(json.dumps(fixture))
        current=self.run_case('delta',fixture=path,update_from='before')
        self.assertTrue(any(x['step']=='analyst_update' for x in self.data('delta')['usage']))
        plan=json.loads((current/'update_plan.json').read_text())
        self.assertEqual('incremental',plan['mode'])
        self.assertTrue(plan['retained_claims'])
        self.assertTrue((current/'changes.json').is_file())

    def test_adaptive_full_facts_preserves_critics_and_citation_check(self):
        case=next(c for c in json.loads(FIXTURE.read_text())['cases'] if c['id']=='fact-ko-01')
        out=pipeline.run(self.root,case['prompt'],'full',run_id='adaptive',quiet=True,
                         lang=case['lang'],replay_file=str(FIXTURE),case_id=case['id'],
                         report_format='facts',efficiency={'strategy':'adaptive'})
        steps=[x['step'] for x in self.data('adaptive')['usage']]
        self.assertIn('writer',steps);self.assertNotIn('synth',steps);self.assertNotIn('polish',steps)
        self.assertTrue(any(x.startswith('critic_') for x in steps));self.assertIn('citecheck',steps)
        plan=json.loads((out.parent/'execution_plan.json').read_text())
        self.assertTrue(plan['workflow']['single_draft'])
        self.assertLessEqual(len(steps),plan['planned_calls_max'])

    def test_cli_diagnostics_and_changes_are_read_only(self):
        import io
        from contextlib import redirect_stdout
        from hprc import cli
        self.run_case('before');self.run_case('after',update_from='before')
        for args in (['hpr','profile','after'],['hpr','changes','before','after'],['hpr','evidence','after']):
            with patch.object(cli,'ROOT',self.root), patch('sys.argv',args), redirect_stdout(io.StringIO()) as out:
                self.assertEqual(0,cli.main())
                self.assertTrue(out.getvalue())

    def test_calculate_cli_reads_verified_note_and_rejects_tampering(self):
        import io
        from contextlib import redirect_stdout
        from hprc import cli, vault
        fixture=json.loads(FIXTURE.read_text());case=next(c for c in fixture['cases'] if c['id']=='fact-ko-01')
        case['sources']['S1']+=' Recorded power: 10 kW.'
        path=self.root/'calc-fixture.json';path.write_text(json.dumps(fixture))
        directory=self.run_case('calc',fixture=path)
        rows=json.loads((directory/'sources.json').read_text())['sources']
        row=next(r for r in rows if '10 kW' in vault.note_body(Path(r['path'])))
        body=vault.note_body(Path(row['path']));start=body.index('10 kW')
        spec={'operation':'sum','operands':[{'source_id':row['id'],'start':start,'end':start+5,'quote':'10 kW','unit':'kW'}],'expected':'10'}
        specfile=self.root/'calc.json';specfile.write_text(json.dumps(spec))
        with patch.object(cli,'ROOT',self.root),patch('sys.argv',['hpr','calculate','calc',str(specfile)]),redirect_stdout(io.StringIO()) as out:
            self.assertEqual(0,cli.main())
        self.assertTrue(json.loads(out.getvalue())['matches_expected'])
        note=Path(row['path']);note.write_text(note.read_text().replace('10 kW','90 kW'))
        spec['operands'][0]['quote']='90 kW';specfile.write_text(json.dumps(spec))
        with patch.object(cli,'ROOT',self.root),patch('sys.argv',['hpr','calculate','calc',str(specfile)]),redirect_stdout(io.StringIO()):
            self.assertEqual(2,cli.main())

    def test_incremental_new_claim_without_evidence_is_rejected(self):
        self.run_case('before')
        fixture=json.loads(FIXTURE.read_text());case=next(c for c in fixture['cases'] if c['id']=='fact-ko-01')
        case['sources']['S1']+=' Changed fact.'
        path=self.root/'changed.json';path.write_text(json.dumps(fixture))
        actual=pipeline.run_step
        def unsupported(name,*args,**kwargs):
            result,usage=actual(name,*args,**kwargs)
            if name=='analyst_update':
                result={'claims':[{'id':'NEW','text':'Unsupported new assertion.','sources':[],'confidence':'high'}],'contradictions':[],'gaps':[]}
            return result,usage
        with patch.object(pipeline,'run_step',side_effect=unsupported),self.assertRaises(pipeline.Blocked):
            self.run_case('delta',fixture=path,update_from='before')
        self.assertFalse((self.root/'research/runs/delta/claims.json').exists())

    def test_adaptive_writer_contract_includes_interim_results(self):
        case=next(c for c in json.loads(FIXTURE.read_text())['cases'] if c['id']=='fact-ko-01')
        actual=pipeline.run_step;seen=[]
        def capture(name,prompt,schema,inputs,*args,**kwargs):
            if name=='writer': seen.append((prompt,inputs))
            return actual(name,prompt,schema,inputs,*args,**kwargs)
        with patch.object(pipeline,'run_step',side_effect=capture):
            pipeline.run(self.root,case['prompt'],'full',run_id='contract',quiet=True,lang=case['lang'],
                         replay_file=str(FIXTURE),case_id=case['id'],report_format='facts',efficiency={'strategy':'adaptive'})
        self.assertIn('interim/*.md',seen[0][0]);self.assertTrue(any(k.startswith('interim/') for k in seen[0][1]))
