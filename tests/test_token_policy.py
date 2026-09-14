"""토큰 예약·재시도·모델 배정은 실제 모델을 호출하지 않고 검증한다."""
import contextlib
import io
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from unittest import mock

from hprc import cli, pipeline, token_policy
from hprc.config import load
from hprc.codex_runner import CodexError


class TokenPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def run_object(self, **kwargs):
        return pipeline.Run(self.root, '질문', 'light', 'cost', quiet=True, **kwargs)

    def test_summary_includes_failures_and_no_double_count_of_cache(self):
        rows = [{'usage_known': True, 'status': 'error', 'attempt': 1,
                 'usage': {'input_tokens': 100, 'cached_input_tokens': 80, 'output_tokens': 10}},
                {'usage_known': False, 'status': 'error', 'attempt': 2}]
        result = token_policy.usage_summary(rows)
        self.assertEqual(110, result['total_tokens'])
        self.assertEqual(80, result['cached_input_tokens'])
        self.assertEqual(2, result['failed_calls'])
        self.assertEqual(1, result['retry_calls'])
        self.assertFalse(result['complete'])

    def test_first_call_reservation_stops_before_model(self):
        run = self.run_object(budget=100)
        run.cfg['budget']['reserve_input'] = True
        with mock.patch.object(pipeline, 'run_step') as model:
            with self.assertRaises(pipeline.Blocked):
                run.call('analyst', 'p', {}, {'data': 'x' * 100}, 'analyst')
            model.assert_not_called()
        self.assertEqual([], run.m.data['usage'])

    def test_parallel_reservation_does_not_spend_same_remaining_budget_twice(self):
        run = self.run_object(budget=5000)
        run.cfg['budget']['reserve_input'] = True
        entered, release = Event(), Event()
        def model(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(5))
            return {}, {'usage_known': True, 'usage': {'input_tokens': 20}}
        with mock.patch.object(pipeline, 'run_step', side_effect=model), ThreadPoolExecutor(1) as pool:
            future = pool.submit(run.call, 'one', 'x' * 1000, {}, {}, 'analyst')
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaises(pipeline.Blocked):
                    run.call('two', 'x' * 1000, {}, {}, 'analyst')
            finally:
                release.set()
            future.result(5)
        self.assertEqual({}, run._reservations)

    def test_failure_consumes_max_calls_and_releases_reservation(self):
        run = self.run_object(max_calls=1)
        with mock.patch.object(pipeline, 'run_step', side_effect=CodexError('bad', usage={'input_tokens': 1}, usage_known=True)) as model:
            with self.assertRaises(pipeline.Blocked):
                run.call('analyst', 'p', {}, {}, 'analyst')
            self.assertEqual(1, model.call_count)
        self.assertEqual({}, run._reservations)
        self.assertEqual(1, len(run.m.data['usage']))

    def test_unknown_usage_stops_economy_retry(self):
        run = self.run_object(preset='economy')
        run.cfg['budget']['max_retries'] = 1
        with mock.patch.object(pipeline, 'run_step', side_effect=CodexError('bad')) as model:
            with self.assertRaisesRegex(pipeline.Blocked, '미측정'):
                run.call('analyst', 'p', {}, {}, 'analyst')
            self.assertEqual(1, model.call_count)

    def test_resume_preserves_budget_and_model_config(self):
        first = self.run_object(budget=9000, max_calls=3, preset='economy')
        (self.root / 'research' / 'config.json').write_text(json.dumps({'models': {'analyst': {'model': 'changed'}}}), encoding='utf-8')
        resumed = self.run_object()
        self.assertEqual(9000, resumed.cfg['budget']['max_input_tokens'])
        self.assertEqual(3, resumed.cfg['budget']['max_model_calls'])
        self.assertEqual(first.cfg['models'], resumed.cfg['models'])
        self.assertEqual(12000, self.run_object(budget=12000).cfg['budget']['max_input_tokens'])

    def test_plan_counts_search_gap_and_retry_caps(self):
        cfg = load(self.root)
        full = token_policy.plan_run(cfg, 'full')
        cfg['gap_fetch']['enabled'] = True
        gap = token_policy.plan_run(cfg, 'full')
        self.assertEqual(full['planned_calls_max'] + 1, gap['planned_calls_max'])
        no = token_policy.plan_run(cfg, 'full', no_search=True)
        self.assertEqual(full['planned_calls_max'] - 1, no['planned_calls_max'])
        cfg['budget']['max_model_calls'] = 2
        self.assertEqual(2, token_policy.plan_run(cfg, 'full')['attempts_max'])

    def test_dry_plan_does_not_wait_or_call_model(self):
        with mock.patch.object(cli, 'ROOT', self.root), \
             mock.patch('sys.argv', ['hpr', 'run', '질문', '--preset', 'economy', '--plan-json', '--at', '23:59']), \
             mock.patch.object(pipeline, 'run') as run, mock.patch('time.sleep') as sleep, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(0, cli.main())
            result = json.loads(output.getvalue())
            self.assertEqual('economy', result['preset'])
            self.assertTrue(result['reservation_enabled'])
            run.assert_not_called()
            sleep.assert_not_called()
        self.assertFalse((self.root / 'research').exists())

    def test_invalid_max_calls_does_not_create_run(self):
        with self.assertRaises(pipeline.Blocked):
            self.run_object(max_calls=0)
        self.assertFalse((self.root / 'research').exists())

    def test_history_calibrates_estimate_but_not_as_hard_cap(self):
        estimate = token_policy.estimate_next_input('x' * 100, {},
            [{'role': 'analyst', 'input_bytes': 100, 'usage_known': True, 'usage': {'input_tokens': 20000}}], 'analyst')
        self.assertGreaterEqual(estimate['input_reservation'], 25000)
        self.assertFalse(estimate['hard_cap'])
