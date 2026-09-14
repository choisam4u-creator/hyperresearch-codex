import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hprc.efficiency_study import build_plan
from hprc.study_runner import execute, main, revision

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ROOT / 'tests/fixtures/realistic_inputs.json'
REVISION = revision(ROOT)


@patch('hprc.study_runner.revision', return_value=REVISION)
class StudyRunnerTests(unittest.TestCase):
    def test_live_without_exact_approval_does_not_create_output_or_start_process(self, _revision):
        plan = build_plan(INPUTS, REVISION)
        with tempfile.TemporaryDirectory() as tmp, patch('hprc.study_runner.subprocess.run') as run:
            output = Path(tmp) / 'pilot'
            for budget in (None, 2000000, True):
                with self.assertRaises(ValueError):
                    execute(ROOT, INPUTS, output, plan, backend='codex', approved_total_tokens=budget)
            self.assertFalse(output.exists())
            run.assert_not_called()

    def test_plan_only_never_starts_model(self, _revision):
        with patch('hprc.study_runner.subprocess.run') as run, patch('builtins.print'):
            self.assertEqual(main(['--inputs', str(INPUTS)]), 0)
            run.assert_not_called()

    def test_missing_manifest_is_unknown_not_zero_cost_success_and_no_retry(self, _revision):
        plan = build_plan(INPUTS, REVISION, 1)
        with tempfile.TemporaryDirectory() as tmp, patch('hprc.study_runner.subprocess.run') as run:
            run.return_value.returncode = 1
            output = Path(tmp) / 'pilot'
            result = execute(ROOT, INPUTS, output, plan, backend='mock')
            self.assertEqual(run.call_count, 1)
            self.assertEqual(result['status'], 'stopped')
            self.assertEqual(result['records'][0]['unknowncalls'], 1)
            self.assertFalse(json.loads((output / 'summary.json').read_text())['report_claim_permitted'])
            with self.assertRaises(FileExistsError):
                execute(ROOT, INPUTS, output, plan, backend='mock')
            self.assertEqual(run.call_count, 1)

    def test_fixture_change_rejected_before_launch(self, _revision):
        with tempfile.TemporaryDirectory() as tmp, patch('hprc.study_runner.subprocess.run') as run:
            inputs = Path(tmp) / 'inputs.json'
            inputs.write_bytes(INPUTS.read_bytes())
            plan = build_plan(inputs, REVISION, 1)
            inputs.write_text(inputs.read_text() + '\n')
            with self.assertRaises(ValueError):
                execute(ROOT, inputs, Path(tmp) / 'out', plan, backend='mock')
            run.assert_not_called()

    def test_interrupted_launch_persists_in_progress_and_refuses_rerun(self, _revision):
        plan = build_plan(INPUTS, REVISION, 1)
        with tempfile.TemporaryDirectory() as tmp, patch('hprc.study_runner.subprocess.run', side_effect=KeyboardInterrupt):
            output = Path(tmp) / 'pilot'
            with self.assertRaises(KeyboardInterrupt):
                execute(ROOT, INPUTS, output, plan, backend='mock')
            state = json.loads((output / 'experiment.json').read_text())
            self.assertEqual(state['status'], 'interrupted')
            self.assertTrue(state['usage_may_be_unrecorded'])
            self.assertIn('in_progress', state)

class ObservedControlsTests(unittest.TestCase):
    def test_wrong_manifest_or_attempt_cannot_pass_planned_metadata(self):
        from hprc.study_runner import observed_controls
        from hprc.evaluation import case_input_hash
        import copy
        fixture = json.loads(INPUTS.read_text())
        case = next(c for c in fixture['cases'] if c['id'] == 'real-ko-table')
        roles = {'analyst': {'model': 'model-test', 'effort': 'low'}}
        manifest = dict(prompt=case['prompt'], lang=case['lang'], tier='light', run_id='trial',
                        frozen_input_hash=case_input_hash(case), no_search=True,
                        usage=[dict(step='analyst', role='analyst', model='model-test', effort='low', backend='mock', web_search=False)])
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / 'frozen_input.json').write_text(json.dumps(case))
            self.assertEqual(observed_controls(manifest, folder, case, roles, 'mock')[0], [])
            for key in ('prompt', 'lang', 'tier', 'run_id', 'frozen_input_hash', 'no_search'):
                changed = copy.deepcopy(manifest); changed[key] = 'wrong'
                self.assertIn('manifest_' + key, observed_controls(changed, folder, case, roles, 'mock')[0])
            for key in ('model', 'effort', 'backend', 'role', 'web_search', 'step'):
                changed = copy.deepcopy(manifest); changed['usage'][0][key] = 'wrong'
                self.assertTrue(observed_controls(changed, folder, case, roles, 'mock')[0])
            changed = copy.deepcopy(manifest); changed['usage'][0]['step'] = 'writer'
            self.assertIn('attempt_step_role', observed_controls(changed, folder, case, roles, 'mock')[0])
            changed = copy.deepcopy(manifest); changed['usage'] *= 9
            self.assertIn('attempt_count', observed_controls(changed, folder, case, roles, 'mock')[0])
            wrong = dict(case, prompt='wrong'); (folder / 'frozen_input.json').write_text(json.dumps(wrong))
            self.assertIn('frozen_case', observed_controls(manifest, folder, case, roles, 'mock')[0])
