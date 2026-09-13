"""근거 원장·부분 재검증·선택 조사·모델 배정의 통합 회귀."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hprc import pipeline
from hprc.config import load
from hprc.evidence import validate_evidence_ledger
from hprc.gap_plan import plan_gaps
from hprc.vault import write_note


class PhaseIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        backend = mock.patch.dict("os.environ", {"HPR_BACKEND": "mock"})
        backend.start()
        self.addCleanup(backend.stop)
        self.run = pipeline.Run(self.root, '조건별 비교', 'full', 'phases', quiet=True)
        self.run.cfg['verification']['recheck_changed'] = True
        text = 'The duration is 2000 ms. The updated duration is 3000 ms.'
        path = write_note(self.run.notes_dir, 'S1', {'url': 'https://fixture.invalid/a', 'title': '시간', 'text': text,
                         'sha256': hashlib.sha256(text.encode()).hexdigest(), 'fetched_at': '2026-09-01'})
        self.run.sources = [{'id': 'S1', 'note_id': 'N-source', 'path': str(path), 'url': 'https://fixture.invalid/a', 'title': '시간', 'domain': 'fixture.invalid'}]
        self.run.known = self.run.relevant = {'S1'}

    def initial_check(self, report):
        (self.run.dir / 'report.md').write_text(report, encoding='utf-8')
        with mock.patch.dict('os.environ', {'HPR_BACKEND': 'mock'}):
            self.run.step_citecheck()

    def test_only_changed_or_unchecked_citations_are_sent_again(self):
        report = 'The duration is 2000 ms. [S1]\nThe duration is 3000 ms. [S1]\n'
        self.initial_check(report)
        updated = report.replace('3000 ms.', '3 s.')
        (self.run.dir / 'report.md').write_text(updated, encoding='utf-8')
        def check(name, prompt, schema, inputs, role):
            selected = json.loads(inputs['samples.json'])
            self.assertEqual(1, len(selected))
            self.assertIn('3 s.', selected[0]['sentence'])
            return {'checks': [{**s, 'supported': True, 'reason': 'fixture'} for s in selected]}
        with mock.patch.object(self.run, 'call', side_effect=check) as call:
            self.run.step_recheck()
            call.assert_called_once()
            self.run.step_recheck()
            call.assert_called_once()
        saved = json.loads((self.run.dir / 'citecheck_final.json').read_text())
        self.assertEqual(2, saved['sampling']['checked_count'])
        self.assertEqual(0, saved['unchecked_count'])

    def test_unchanged_report_needs_no_extra_model(self):
        self.initial_check('The duration is 2000 ms. [S1]\n')
        with mock.patch.object(self.run, 'call') as call:
            self.run.step_recheck()
            call.assert_not_called()

    def test_source_changes_invalidate_previous_judgments(self):
        self.initial_check('The duration is 2000 ms. [S1]\n')
        path = Path(self.run.sources[0]['path'])
        path.write_text(path.read_text().replace('2000 ms', '3000 ms'), encoding='utf-8')
        with mock.patch.object(self.run, 'call', return_value={'checks': []}) as call:
            self.run.step_recheck()
            call.assert_called_once()
        self.assertEqual(1, json.loads((self.run.dir / 'citecheck_final.json').read_text())['unchecked_count'])

    def test_evidence_source_hash_matches_original_body(self):
        sources = self.run.evidence_sources()
        src = sources['S1']
        self.assertEqual(src['metadata']['sha256'], hashlib.sha256(src['text'].encode()).hexdigest())

    def test_gap_ranks_conflict_without_expanding_limit(self):
        result = plan_gaps('제품 속도 비교', {'gaps': ['가격', '속도 조건', '설치'], 'contradictions': [{'note': '속도 조건이 다르다'}]}, 50)
        self.assertEqual(2, len(result['selected']))
        self.assertEqual('속도 조건', result['selected'][0]['gap'])
        self.assertEqual(1, len(result['deferred']))

    def test_high_findings_change_role_without_adding_call(self):
        self.run.cfg['routing']['enabled'] = True
        (self.run.dir / 'findings.json').write_text(json.dumps({'findings': [{'severity': 'high'}]}))
        chosen, reason = self.run.role_for_call('patcher', 'patcher')
        self.assertEqual('gpt-6-astra', chosen['model'])
        self.assertEqual('high_finding', reason)
        self.assertEqual(0, self.run.m.data['routing_events'][0]['extra_calls'])
        self.assertEqual((chosen, reason), self.run.role_for_call('patcher', 'patcher'))
        self.assertEqual(1, len(self.run.m.data['routing_events']))

    def test_explicit_model_and_budget_override_economy_candidates(self):
        (self.root / 'research' / 'config.json').write_text(json.dumps({'models': {'writer': {'model': 'custom'}}, 'budget': {'max_retries': 1}}))
        cfg = load(self.root, preset='economy')
        self.assertEqual('custom', cfg['models']['writer']['model'])
        self.assertEqual(1, cfg['budget']['max_retries'])

    def test_replay_runs_exact_short_sources_without_network_or_answers(self):
        from hprc.replay import load_case
        inputs = Path(__file__).parent / 'fixtures' / 'benchmark_inputs.json'
        case = load_case(inputs, 'fact-ko-01')
        with mock.patch.object(pipeline, 'fetch_all', side_effect=AssertionError('network')), \
             mock.patch.object(pipeline.searchmod, 'duckduckgo', side_effect=AssertionError('network')):
            out = pipeline.run(self.root, case['prompt'], 'light', run_id='replay', quiet=True,
                               replay_file=str(inputs), case_id=case['id'])
            self.assertTrue(out.is_file())
            with mock.patch.object(pipeline, 'run_step', side_effect=AssertionError('model re-call')):
                self.assertEqual(out, pipeline.run(self.root, case['prompt'], run_id='replay', quiet=True))
        replay = pipeline.Run(self.root, case['prompt'], 'light', 'replay', quiet=True)
        replay.load_sources()
        self.assertEqual(case['sources'], {k: v['text'] for k, v in replay.evidence_sources().items()})
        self.assertTrue((out.parent / 'evidence_ledger.json').exists())
        self.assertTrue((out.parent / 'usage_summary.json').exists())
        self.assertTrue((out.parent / 'review.md').exists())
        self.assertEqual([], validate_evidence_ledger(json.loads((out.parent / 'evidence_ledger.json').read_text()), replay.evidence_sources(), (out.parent / 'report.md').read_text()))

    def test_verification_prompt_change_invalidates_reuse(self):
        self.initial_check('The duration is 2000 ms. [S1]\n')
        original = pipeline._prompt
        with mock.patch.object(pipeline, '_prompt', side_effect=lambda *a, **k: original(*a, **k) + ' updated'), \
             mock.patch.object(self.run, 'call', return_value={'checks': []}) as call:
            self.run.step_recheck()
            call.assert_called_once()

    def test_changed_runtime_blocks_resumed_model_call(self):
        resumed = pipeline.Run(self.root, '조건별 비교', 'full', 'phases', quiet=True)
        hashes = pipeline.runtime_hashes(resumed.lang)
        with mock.patch.object(pipeline, 'runtime_hashes', return_value={**hashes, 'prompt_hash': 'changed'}), \
             mock.patch.object(pipeline, 'run_step') as call:
            with self.assertRaises(pipeline.Blocked):
                resumed.call('analyst', 'prompt', {}, {}, 'analyst')
            call.assert_not_called()

    def test_effective_budget_is_recorded_for_comparison(self):
        run = pipeline.Run(self.root, 'q', 'light', 'overrides', quiet=True, budget=4321, max_calls=7)
        self.assertEqual(4321, run.m.data['effective_config_snapshot']['budget']['max_input_tokens'])
        self.assertEqual(7, run.m.data['effective_config_snapshot']['budget']['max_model_calls'])
        self.assertEqual(pipeline.fingerprint(run.cfg), run.m.data['runtime']['config_hash'])

    def test_stale_citation_context_requires_review(self):
        self.initial_check('The documented behavior is supported. [S1]')
        (self.run.dir / 'findings.json').write_text('{"findings": []}')
        (self.run.dir / 'sources.json').write_text('{"warnings": []}')
        original = pipeline._prompt
        with mock.patch.object(pipeline, '_prompt', side_effect=lambda *a, **k: original(*a, **k) + ' changed'), \
             mock.patch.object(pipeline, 'report_lint', return_value=[]):
            self.run.step_final()
        quality = json.loads((self.run.dir / 'quality.json').read_text())
        self.assertEqual('review_required', quality['status'])
        self.assertIn('stale_citation_context', [i['kind'] for i in quality['issues']])
