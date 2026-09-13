"""출처 보존·날짜·실행 경계의 통합 회귀. 실제 모델이나 네트워크를 쓰지 않는다."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hprc import pipeline, mcp_server, vault


class PhaseOneIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_runs_keep_original_evidence_and_forward_dates(self):
        runs = []
        for index in range(2):
            run = pipeline.Run(self.root, '질문', 'light', f'run-{index}', quiet=True)
            page = dict(url=f'https://example.test/{index}', title='같은 제목', domain='example.test',
                        text=f'{index}번째 근거 ' * 100, sha256='fixture', error='',
                        published='2025-01-02', published_source='meta:datePublished',
                        modified='2026-09-01', modified_source='last-modified')
            (run.dir / 'candidates.json').write_text(json.dumps({'candidates': [{'url': page['url']}]}))
            with mock.patch.object(pipeline, 'fetch_all', return_value=[page]), mock.patch.object(pipeline, 'sync'):
                run.step_fetch()
            run.load_sources()
            runs.append(run)
        first, second = (r.sources[0] for r in runs)
        self.assertEqual(first['id'], second['id'])
        self.assertNotEqual(first['note_id'], second['note_id'])
        self.assertNotEqual(first['path'], second['path'])
        inputs = runs[0].notes()
        note = inputs['S1-note.md']
        self.assertIn('0번째 근거', note)
        self.assertNotIn('1번째 근거', note)
        for value in ('published: 2025-01-02', 'modified: 2026-09-01', 'meta:datePublished', 'last-modified'):
            self.assertIn(value, note)
        self.assertIn('0번째 근거', mcp_server.call_tool(self.root, 'read_note', {'id': first['note_id']}))

    def test_legacy_metadata_falls_back_to_run_source_without_rewriting(self):
        run = pipeline.Run(self.root, '질문', 'light', 'legacy', quiet=True)
        path = self.root / 'legacy.md'
        text = '---\nid: "S1"\ntitle: "옛 노트"\n---\n\n옛 근거'
        path.write_text(text)
        run.sources = [{'id': 'S1', 'path': str(path), 'published': '2024-02-03',
                        'published_source': 'row', 'modified': '2025-03-04'}]
        self.assertIn('published: 2024-02-03', run.notes()['S1-note.md'])
        self.assertIn('modified: 2025-03-04', run.notes()['S1-note.md'])
        self.assertEqual(text, path.read_text())

    def test_invalid_run_stops_before_manifest_or_model_and_mcp_read(self):
        with mock.patch.object(pipeline, 'run_step', side_effect=AssertionError('model call')):
            for name in ('', '.', '..', '../escaped', '/absolute', 'a/b'):
                with self.subTest(name=name), self.assertRaises(pipeline.Blocked):
                    pipeline.run(self.root, '질문', run_id=name, quiet=True)
        self.assertFalse((self.root / 'research').exists())
        result = mcp_server.call_tool(self.root, 'read_report', {'run_id': '../escaped'})
        self.assertTrue(result)
        self.assertNotEqual('보고서 없음', result)
