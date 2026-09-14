"""공개 실측 사본의 사용량 산술과 원문 결속을 확인한다. 의미 판정을 대신하지 않는다."""
import hashlib
import json
from pathlib import Path
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(folder):
    if not __debug__:
        raise RuntimeError('검증에는 assert가 필요하므로 Python 최적화 모드(-O)를 허용하지 않습니다')
    data = json.loads((folder/'records.json').read_text())
    quality = json.loads((folder/'quality.json').read_text())
    reviews = {r['run_id']: r for r in quality['records']}
    assert len(reviews) == len(quality['records']) == len(data['records'])
    assert len({r['run_id'] for r in data['records']}) == len(data['records'])
    total = atoms = quotes = 0
    for row in data['records']:
        assert sha(folder/(row['run_id']+'.md')) == row['report_sha256']
        assert row['reported_total_tokens'] == row['input_tokens'] + row['output_tokens']
        assert row['attempt_count'] == len(row['attempts'])
        assert row['unknowncalls'] == 0
        assert row['observed_control_errors'] == []
        assert row['retry_attempt_count'] == row['failure_attempt_count'] == 0
        for key in ('input_tokens','cached_input_tokens','output_tokens'):
            assert sum(a['usage'][key] for a in row['attempts']) == row[key]
        for attempt in row['attempts']:
            assert attempt['usage_known'] is True
            assert all(type(attempt['usage'][k]) is int and attempt['usage'][k] >= 0 for k in ('input_tokens','cached_input_tokens','output_tokens'))
            assert attempt['usage']['cached_input_tokens'] <= attempt['usage']['input_tokens']
        qr = reviews[row['run_id']]
        rp = folder/qr['review_file']
        assert sha(rp) == qr['review_sha256']
        review = json.loads(rp.read_text())
        packet = json.loads((folder/'reviews'/(row['opaque_id']+'.json')).read_text())
        # 공개 사본은 report.md 본문이다. wrapper 변환을 암묵적으로 허용하지 않는다.
        assert (folder/(row['run_id']+'.md')).read_text() == packet['report']
        assert row['report_sha256'] == row['blind_report_sha256']
        assert row['opaque_id'] == qr['opaque_id'] == review['opaque_id'] == packet['opaque_id']
        assert row['blind_quality'] == qr['blind_quality'] == review['quality']
        assert row['blind_report_sha256'] == review['report_sha256'] == hashlib.sha256(packet['report'].encode()).hexdigest()
        for sid, expected in review['source_sha256'].items():
            assert hashlib.sha256(packet['sources'][sid].encode()).hexdigest() == expected
        for entry in review['entries']:
            assert packet['report'][entry['report_start']:entry['report_end']] == entry['claim_text']
            for quote in entry.get('evidence',[]):
                assert packet['sources'][quote['source_id']][quote['source_start']:quote['source_end']] == quote['exact_quote']
                quotes += 1
            atoms += 1
        total += row['reported_total_tokens']
    assert total == data['known_tokens']
    print(folder.name, len(data['records']), 'runs;', total, 'tokens;', atoms, 'review entries;', quotes, 'quotes; bindings PASS (not semantic proof)')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('사용법: python3 verify_efficiency_results.py RESULT_DIRECTORY [RESULT_DIRECTORY ...]')
    for arg in sys.argv[1:]:
        verify(Path(arg))
