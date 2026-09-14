"""분석에 남은 근거가 작성 단계에서 빠진 실제 입력 경로를 모의 재현한다."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hprc import pipeline

FIXTURE = Path(__file__).parent / 'fixtures/realistic_inputs.json'
CLAIM = ('Staff logged 58 corrections: 21 after a sick call, 17 after a late-opening program, '
         '12 after a ticket-printer restart, and 8 free-text descriptions.')


class ClaimDeliveryTests(unittest.TestCase):
    def test_writer_receives_missing_evidence_with_both_packaging_modes(self):
        case = next(c for c in json.loads(FIXTURE.read_text(encoding='utf-8'))['cases']
                    if c['id'] == 'real-en-long')
        actual = pipeline.run_step
        for packet, evidence in ((False, False), (True, False), (False, True), (True, True)):
            seen = []

            def record(name, prompt, schema, inputs, *args, **kwargs):
                result, usage = actual(name, prompt, schema, inputs, *args, **kwargs)
                if name == 'analyst':
                    result = {'claims': [{'id': 'c1', 'text': CLAIM, 'sources': ['S2'], 'confidence': 'high'},
                                         {'id': 'c2', 'text': 'Pilot match rate was 71%.', 'sources': ['S1'], 'confidence': 'high'}],
                              'contradictions': [], 'gaps': []}
                if name == 'writer':
                    seen.append(inputs)
                return result, usage

            with (self.subTest(packet=packet, evidence=evidence), tempfile.TemporaryDirectory() as tmp,
                  patch.dict(os.environ, {'HPR_BACKEND': 'mock'}),
                  patch.object(pipeline, 'run_step', side_effect=record)):
                pipeline.run(Path(tmp), case['prompt'], 'light', run_id='delivery', quiet=True,
                             preset='lean', lang='en', replay_file=str(FIXTURE), case_id=case['id'],
                             efficiency={'packet_inputs': packet, 'evidence_selection': evidence})
                text = '\n'.join(seen[0].values())
                self.assertIn('21 followed a sick call', text)
                self.assertIn('not independently audited', text)
                self.assertIn('excluded from the matching calculation', text)
                budget = json.loads((Path(tmp) / 'research/runs/delivery/writer_evidence_budget.json').read_text(encoding='utf-8'))
                self.assertLessEqual(budget['selected_chars'], budget['total_cap_chars'])
                self.assertEqual(10000, budget['total_cap_chars'])
                if evidence:
                    records = json.loads((Path(tmp) / 'research/runs/delivery/evidence_selections.json').read_text(encoding='utf-8'))
                    supplemented = [r for r in records if r['supplemental_queries']]
                    self.assertTrue(supplemented)
                    self.assertTrue(any(r['source_id'] == 'S2' and CLAIM in r['supplemental_queries'] for r in supplemented))
                    self.assertTrue(all(len(r['selection_queries_sha256']) == 64 for r in supplemented))
