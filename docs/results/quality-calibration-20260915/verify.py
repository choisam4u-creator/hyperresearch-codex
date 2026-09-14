"""Recheck this frozen dataset without model calls: python3 verify.py."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

def read(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))

def require(condition, message):
    if not condition:
        raise ValueError(message)

def verify():
    manifest = read('manifest.json')['sha256']
    require(set(manifest) == {p.name for p in HERE.iterdir() if p.is_file() and p.name != 'manifest.json'}, 'Manifest file set mismatch')
    for name, digest in manifest.items():
        require(hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest, 'Hash mismatch: ' + name)
    study = read('study.json')
    require(study['status'] == 'stopped' and study['research'] == [], 'Expected stopped study with no research')
    require(len(study['evaluation']) == 1, 'Expected exactly one evaluator attempt')
    usage = study['evaluation'][0]['usage']
    require(usage['known'] is True, 'Unknown usage')
    require(0 <= usage['cached_input_tokens'] <= usage['input_tokens'], 'Invalid cache subset')
    require(usage['input_tokens'] + usage['output_tokens'] == usage['total_tokens'] == 86033, 'Usage mismatch')
    packet = read('calibration-input.json')
    reports = {r['opaque_id']: r for r in packet['reports']}
    key = {r['opaque_id']: r for r in read('calibration-key.json')}
    responses = read('calibration-terra.response.json')['reports']
    require(len(responses) == len(reports) == len(key) == 6, 'Example count mismatch')
    require({r['opaque_id'] for r in responses} == set(key) == set(reports), 'Example identity mismatch')
    gold = {c['case_id']: c for c in read('gold.json')['cases']}
    analysis = read('analysis.json')
    calculated_checks = []
    detected = good_pass = complete = 0
    for row in responses:
        report = reports[row['opaque_id']]
        context = packet['contexts'][report['context_id']]
        expected = key[row['opaque_id']]
        case = gold[expected['case_id']]
        require(hashlib.sha256(report['report'].encode()).hexdigest() == expected['report_sha256'], 'Report/key hash mismatch')
        require(case['prompt'] == context['question'] and case['language'] == context['lang'], 'Case/context mismatch')
        require(context['rubric'] == {k: case[k] for k in ('required_facts','required_qualifiers','correct_abstentions','critical_errors')}, 'Rubric mismatch')
        required = {i['id'] for category in ('required_facts', 'required_qualifiers', 'correct_abstentions') for i in context['rubric'][category]}
        require(len(row['requirements']) == len(required) and {j['id'] for j in row['requirements']} == required, 'Required item mismatch')
        for j in row['requirements'] + row['issues']:
            require(j['report_quote'] in report['report'], 'Report quote mismatch')
            for evidence in j['source_evidence']:
                require(bool(evidence['quote']) and evidence['quote'] in context['sources'].get(evidence['source_id'], ''), 'Source quote mismatch')
        failed = {j['id'] for j in row['requirements'] if j['status'] in ('missing', 'incorrect')} | {i['id'] for i in row['issues']}
        expected = key[row['opaque_id']]
        detected += expected['expected_disposition'] == 'fail' and set(expected['expected_failure_ids']) <= failed
        good_pass += expected['expected_disposition'] == 'pass' and row['overall'] == 'pass'
        complete += row['full_report_reviewed'] is True
        calculated_checks.append({'opaque_id':row['opaque_id'],'expected':expected['expected_disposition'],'actual':row['overall'],'full_report_reviewed':row['full_report_reviewed'],'expected_errors_detected':set(expected['expected_failure_ids']) <= failed,'disposition_matches':expected['expected_disposition']==row['overall'],'unresolved':row['unresolved']})
    require((detected, good_pass, complete) == (4, 0, 0), 'Assessment summary mismatch')
    require(analysis['checks'] == calculated_checks, 'Stored checks mismatch')
    require(analysis['usage'] == usage and analysis['overshoot_tokens'] == usage['total_tokens'] - analysis['per_call_stop'] == 26033, 'Analysis usage mismatch')
    require(analysis['budget_fraction_percent'] == round(usage['total_tokens']/study['budget']['combined_stop']*100,3), 'Budget fraction mismatch')
    require((analysis['expected_bad_examples_detected'], analysis['expected_good_examples_passed'], analysis['full_reviews']) == (detected, good_pass, complete), 'Stored summary mismatch')
    print(json.dumps({'evidence_integrity': 'pass', 'research_runs': 0, 'evaluation_tokens': 86033, 'expected_error_examples_detected': detected, 'correct_examples_passed': good_pass, 'complete_reviews': complete, 'quality_improvement': 'not_measured'}))

if __name__ == '__main__':
    verify()
