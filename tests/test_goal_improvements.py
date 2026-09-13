"""남은 목표의 총 토큰 보호와 출력 형식 연결 회귀."""
import io
import json
import contextlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from hprc import pipeline, cli
from hprc.report_format import format_instruction
from hprc.brief import render_brief


class GoalImprovementsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def run_obj(self, **kwargs):
        return pipeline.Run(self.root, 'q', 'light', 'goal', quiet=True, **kwargs)

    def test_output_spend_stops_next_call_even_with_input_room(self):
        run = self.run_obj(total_budget=10000)
        run.m.data['usage'] = [{'usage_known': True, 'usage': {'input_tokens': 1, 'output_tokens': 9999}}]
        with mock.patch.object(pipeline, 'run_step') as call:
            with self.assertRaisesRegex(pipeline.Blocked, '총'):
                run.call('writer', 'p', {}, {}, 'writer')
            call.assert_not_called()

    def test_total_reservation_counts_inflight_output(self):
        run = self.run_obj(total_budget=14000)
        run._reserve_call('first', 'writer', 'p', {}, 'writer')
        run._reserve_call('second', 'writer', 'p', {}, 'writer')
        with self.assertRaisesRegex(pipeline.Blocked, '총'):
            run._reserve_call('third', 'writer', 'p', {}, 'writer')

    def test_total_budget_stops_unknown_even_standard(self):
        run = self.run_obj(total_budget=99999)
        run.m.data['usage'] = [{'usage_known': False}]
        with self.assertRaisesRegex(pipeline.Blocked, '미측정'):
            run._reserve_call('a', 'writer', 'p', {}, 'writer')

    def test_total_budget_and_format_persist_on_resume(self):
        self.run_obj(total_budget=20000, report_format='comparison')
        resumed = self.run_obj()
        self.assertEqual(20000, resumed.cfg['budget']['max_total_tokens'])
        self.assertEqual('comparison', resumed.cfg['report_format'])
        self.assertEqual(30000, self.run_obj(total_budget=30000).cfg['budget']['max_total_tokens'])
        self.assertIn('비교표', resumed.writing_prompt('writer', target_words=700))

    def test_dry_plan_exposes_total_and_format_without_files(self):
        with mock.patch.object(cli, 'ROOT', self.root), mock.patch('sys.argv', ['hpr', 'run', 'q', '--plan-json', '--total-budget', '20000', '--format', 'facts']), contextlib.redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(0, cli.main())
        result = json.loads(buf.getvalue())
        self.assertEqual(20000, result['total_token_stop_threshold'])
        self.assertEqual('facts', result['report_format'])
        self.assertTrue(result['stop_on_unknown'])
        self.assertFalse((self.root / 'research').exists())

    def test_invalid_total_budget_has_no_artifacts(self):
        with self.assertRaises(pipeline.Blocked):
            pipeline.run(self.root, 'q', total_budget=0)
        self.assertFalse((self.root / 'research').exists())

    def test_format_keeps_length_and_unknowns(self):
        self.assertEqual('', format_instruction())
        for lang in ('ko', 'en'):
            for kind in ('facts', 'comparison', 'analysis'):
                self.assertTrue(format_instruction(kind, lang))
        with self.assertRaises(ValueError):
            format_instruction('bad')

    def test_review_marks_partial_tokens(self):
        usage = dict(input_tokens=10,cached_input_tokens=0,output_tokens=1,calls=1,failed_calls=1,retry_calls=0,unknown_calls=1,complete=False)
        text = render_brief('## Answer\nA [S1]', {'status':'review_required'}, usage, 'en', 'facts')
        self.assertIn('Known tokens only', text)
        self.assertIn('facts', text)

    def semantic_run(self):
        from hprc.vault import write_note
        import hashlib
        run = self.run_obj()
        run.cfg['verification']['semantic'] = True
        text = 'Atlas runs in a sandbox. The timeout is 2 seconds.'
        path = write_note(run.notes_dir, 'S1', {'url':'https://fixture.invalid/a','title':'Atlas','text':text,'sha256':hashlib.sha256(text.encode()).hexdigest()})
        run.sources = [{'id':'S1','note_id':'N1','path':str(path),'url':'https://fixture.invalid/a','title':'Atlas','domain':'fixture.invalid'}]
        run.known = run.relevant = {'S1'}
        (run.dir / 'report.md').write_text('Atlas runs in a sandbox. [S1]\n', encoding='utf-8')
        (run.dir / 'findings.json').write_text('{"findings": []}')
        (run.dir / 'sources.json').write_text('{"warnings": []}')
        return run

    def test_semantic_check_shares_existing_call_and_attaches_exact_evidence(self):
        run = self.semantic_run()
        def response(name, prompt, schema, inputs, role):
            self.assertEqual('citecheck', name)
            sample = json.loads(inputs['samples.json'])[0]
            return {'checks':[{**{k:sample[k] for k in ('sentence','cites')},'supported':True,'reason':'fixture',
                              'atoms':[{'quote':'Atlas runs in a sandbox.', 'verdict':'supported',
                                        'evidence':[{'source_id':'S1','quote':'Atlas runs in a sandbox.','relation':'supports'}],
                                        'conditions':'unknown','limitations':'fixture'}]}]}
        with mock.patch.object(run, 'call', side_effect=response) as call, mock.patch.object(pipeline, 'report_lint', return_value=[]):
            run.step_citecheck()
            run.step_final()
            self.assertEqual(1, call.call_count)
        evidence = json.loads((run.dir / 'evidence_ledger.json').read_text())
        atoms = evidence['claims'][0]['semantic_atoms']
        self.assertEqual('supported', atoms[0]['verdict'])
        self.assertFalse(evidence['scope']['semantic']['complete'])
        self.assertTrue((run.dir / 'citecheck_semantic.json').is_file())

    def test_semantic_mock_is_insufficient_not_fake_support(self):
        run = self.semantic_run()
        with mock.patch.dict('os.environ', {'HPR_BACKEND':'mock'}):
            run.step_citecheck()
        record = json.loads((run.dir / 'citecheck.json').read_text())
        self.assertFalse(record['checks'][0]['supported'])
        self.assertEqual(1, len(run.m.data['usage']))

    def test_changed_sentence_does_not_inherit_semantic_atoms(self):
        run = self.semantic_run()
        with mock.patch.dict('os.environ', {'HPR_BACKEND':'mock'}):
            run.step_citecheck()
            from hprc.evidence import build_evidence_ledger
            ledger = build_evidence_ledger('Atlas has no sandbox. [S1]', run.evidence_sources())
            run.attach_semantic_evidence(ledger)
            self.assertNotIn('semantic_atoms', ledger['claims'][0])

    def test_final_resolves_only_freshly_passed_structural_findings(self):
        run = self.semantic_run()
        findings = [
            {'id':'F1','quote':'old title','problem':'title','severity':'high','source_ids':[],
             'origin':'deterministic','check_id':'first_line_question'},
            {'id':'F2','quote':'Atlas','problem':'unsupported claim','severity':'high','source_ids':[]},
            {'id':'F3','quote':'old section','problem':'missing','severity':'high','source_ids':[],
             'origin':'deterministic','check_id':'required_section_1'}]
        (run.dir/'report.md').write_text('# 질문: q\nAtlas runs in a sandbox. [S1]\n')
        (run.dir/'findings.json').write_text(json.dumps({'findings':findings}))
        with mock.patch.dict('os.environ', {'HPR_BACKEND':'mock'}):
            run.step_citecheck()
        with mock.patch.object(pipeline,'verify_report',wraps=pipeline.verify_report) as verify:
            run.step_final()
        self.assertEqual(['F2','F3'],verify.call_args.args[6])
