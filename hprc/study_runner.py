"""Explicit, sequential efficiency pilot runner; default command only prints a plan."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

from .blind_eval import prepare_blind_packet
from .efficiency_study import build_plan, validate_results
from .evaluation import runtime_metadata_from_manifest, case_input_hash
from .token_policy import usage_summary


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def revision(repo):
    return subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()


def assert_frozen(repo, inputs, plan, backend):
    if revision(repo) != plan['code_sha'] or hashlib.sha256(inputs.read_bytes()).hexdigest() != plan['fixture_sha256']:
        raise ValueError('Code revision or frozen inputs changed; stop without rerunning')
    if backend == 'codex' and subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo, text=True).strip():
        raise ValueError('Live measurement requires a clean committed checkout')
    current = build_plan(inputs, plan['code_sha'], plan['policy']['repetitions_per_case'])
    if current != plan:
        raise ValueError('Runtime/configuration changed after preregistration')


def observed_controls(manifest, folder, case, roles, backend):
    errors = []
    for key, expected in {'prompt': case['prompt'], 'lang': case['lang'], 'tier': 'light',
                          'run_id': 'trial', 'frozen_input_hash': case_input_hash(case),
                          'no_search': True}.items():
        if manifest.get(key) != expected:
            errors.append('manifest_' + key)
    frozen_path = folder / 'frozen_input.json'
    frozen = json.loads(frozen_path.read_text(encoding='utf-8')) if frozen_path.exists() else None
    if frozen != case:
        errors.append('frozen_case')
    rows = manifest.get('usage', [])
    if not rows or len(rows) > 8:
        errors.append('attempt_count')
    for row in rows:
        expected_role = {'analyst': 'analyst', 'writer': 'writer',
                         'critic_dialectic': 'critic', 'critic_instruction': 'critic',
                         'patcher': 'patcher', 'citecheck': 'citecheck'}.get(row.get('step'))
        if expected_role is None or row.get('role') != expected_role:
            errors.append('attempt_step_role')
        role = roles.get(expected_role)
        if row.get('backend') != backend:
            errors.append('attempt_backend')
        if not role or any(row.get(key) != role[key] for key in ('model', 'effort')):
            errors.append('attempt_model_role')
        if row.get('web_search') is not False:
            errors.append('attempt_web_search')
    observed_backends = {row.get('backend') for row in rows}
    observed_backend = next(iter(observed_backends)) if len(observed_backends) == 1 else 'unknown_or_mixed'
    return sorted(set(errors)), frozen, observed_backend


def execute(repo, inputs, output, plan, *, backend, approved_total_tokens=None):
    if backend not in {'mock', 'codex'}:
        raise ValueError('Explicit mock or codex backend required')
    total_stop = plan['policy']['study_total_token_stop']
    if backend == 'codex' and (type(approved_total_tokens) is not int or approved_total_tokens != total_stop):
        raise ValueError('Live execution requires explicit approval of this exact study token stop')
    assert_frozen(repo, inputs, plan, backend)
    # Exclusive directory prevents accidental repeats, including interrupted studies.
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / 'plan.json', plan)
    fixture = json.loads(inputs.read_text(encoding='utf-8'))
    cases = {case['id']: case for case in fixture['cases'] if case.get('split') == 'dev'}
    state = {'status': 'running', 'backend': backend, 'records': [], 'known_tokens': 0,
             'quality': 'unjudged', 'total_stop_is_hard_cap': False}
    write_json(output / 'experiment.json', state)
    try:
        for run in plan['runs']:
            assert_frozen(repo, inputs, plan, backend)
            if state['known_tokens'] + plan['policy']['per_run_total_token_stop'] > total_stop:
                state.update(status='stopped', reason='Insufficient room for next fixed-budget run')
                break
            case = cases[run['case_id']]
            workspace = output / run['run_id']
            (workspace / 'research').mkdir(parents=True)
            cfg = run['runtime_metadata']['config_snapshot']
            write_json(workspace / 'research/config.json', cfg)
            state['in_progress'] = run['run_id']
            write_json(output / 'experiment.json', state)
            command = [sys.executable, str(repo / 'hpr.py'), 'run', case['prompt'],
                       '--tier', 'light', '--preset', 'lean', '--lang', case['lang'],
                       '--format', cfg['report_format'], '--total-budget', '500000', '--budget', '500000',
                       '--max-calls', '8', '--replay', str(inputs), '--case', case['id'], '--run-id', 'trial']
            started = time.monotonic()
            print('START', run['run_id'], flush=True)
            with (workspace / 'run.log').open('w', encoding='utf-8') as log:
                completed = subprocess.run(command, cwd=repo,
                    env=dict(os.environ, HPR_HOME=str(workspace), HPR_BACKEND=backend),
                    stdout=log, stderr=subprocess.STDOUT)
            folder = workspace / 'research/runs/trial'
            manifest_file = folder / 'manifest.json'
            manifest = json.loads(manifest_file.read_text()) if manifest_file.exists() else {}
            observed_errors, frozen_case, observed_backend = observed_controls(manifest, folder, case, cfg['models'], backend)
            usage = usage_summary(manifest.get('usage', []))
            # No manifest/attempt ledger cannot establish zero cost.
            unknown = usage['unknown_calls'] + int(not manifest.get('usage'))
            runtime = runtime_metadata_from_manifest(manifest, fixture)
            runtime['backend'] = observed_backend
            runtime['study_code_sha'] = revision(repo)
            report_path = folder / 'report.md'
            if not report_path.exists():
                report_path = folder / 'final_report.md'
            report = report_path.read_text(encoding='utf-8') if report_path.exists() else ''
            record = {key: run[key] for key in ('run_id', 'case_id', 'arm', 'repetition', 'sequence', 'input_hash')}
            record['input_hash'] = case_input_hash(frozen_case) if frozen_case else None
            record.update(backend=observed_backend, runtime_metadata=runtime, observed_control_errors=observed_errors,
                attempt_count=usage['calls'],
                status='ok' if completed.returncode in (0, 3) and report and not unknown and not usage['failed_calls'] and not observed_errors else 'failed',
                returncode=completed.returncode, elapsed_seconds=time.monotonic() - started,
                reported_total_tokens=usage['total_tokens'], input_tokens=usage['input_tokens'],
                cached_input_tokens=usage['cached_input_tokens'], output_tokens=usage['output_tokens'],
                unknowncalls=unknown, retry_attempt_count=usage['retry_calls'], failure_attempt_count=usage['failed_calls'],
                report_sha256=hashlib.sha256(report.encode()).hexdigest() if report else None)
            state['records'].append(record)
            state['known_tokens'] += usage['total_tokens']
            state.pop('in_progress', None)
            if report:
                opaque = secrets.token_hex(12)
                packet, identity = prepare_blind_packet(report, case, opaque)
                (output / 'blind').mkdir(exist_ok=True)
                write_json(output / 'blind' / (opaque + '.json'), packet)
                write_json(workspace / 'blind-identity.json', identity)
            write_json(output / 'experiment.json', state)
            summary = validate_results(plan, state['records'])
            # Mock control mismatch is expected; real mismatches must stop immediately.
            control_errors = summary['control_errors'].get(run['run_id'], [])
            control_errors = [error for error in control_errors if backend != 'mock' or error != 'backend_not_codex']
            print('FINISH', run['run_id'], record['status'], usage['total_tokens'], flush=True)
            if record['status'] != 'ok' or control_errors or usage['retry_calls'] or state['known_tokens'] >= total_stop:
                state.update(status='stopped', reason='Run failed, unknown usage, changed controls, retry or token stop')
                break
        else:
            state['status'] = 'completed_attempts'
    except BaseException as error:
        state.update(status='interrupted', reason=type(error).__name__, usage_may_be_unrecorded=True)
        write_json(output / 'experiment.json', state)
        raise
    write_json(output / 'experiment.json', state)
    write_json(output / 'summary.json', validate_results(plan, state['records']))
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, default=Path('tests/fixtures/realistic_inputs.json'))
    parser.add_argument('--repetitions', type=int, choices=(1, 2), default=2)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--mock', action='store_true')
    mode.add_argument('--execute', action='store_true', help='Requires explicit user budget approval; never inferred')
    parser.add_argument('--approved-total-tokens', type=int)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    inputs = args.inputs.resolve()
    plan = build_plan(inputs, revision(repo), args.repetitions)
    if not (args.mock or args.execute):
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    if args.output is None:
        parser.error('--output must name a new private study directory')
    result = execute(repo, inputs, args.output.resolve(), plan,
                     backend='mock' if args.mock else 'codex', approved_total_tokens=args.approved_total_tokens)
    return 0 if result['status'] == 'completed_attempts' else 1


if __name__ == '__main__':
    raise SystemExit(main())
