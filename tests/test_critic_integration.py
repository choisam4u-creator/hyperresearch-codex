import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from hprc import pipeline
from hprc.config import load
from hprc.token_policy import plan_run

class CriticIntegrationTests(unittest.TestCase):
    def make_run(self, root):
        r=pipeline.Run(root,'q','light','critics',quiet=True,preset='lean')
        (r.dir/'draft.md').write_text('# 질문: q\n\n## 답\n사실. [S1]\n\n## 근거\n사실. [S1]\n\n## 반대 근거와 한계\n미확인.\n\n## 다음 행동\n확인. (판단)\n\n## 출처\n[S1]')
        (r.dir/'claims.json').write_text('{"claims":[],"contradictions":[],"gaps":[]}')
        r.sources=[];r.relevant={'S1'}
        return r
    def test_instruction_gets_no_source_payload_and_resume_no_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.make_run(Path(tmp));received={}
            def call(name,prompt,schema,inputs,role):received[name]=inputs;return {'findings':[]}
            with mock.patch.object(r,'call',side_effect=call):r.step_critics();r.step_critics()
            self.assertEqual(2,len(received))
            self.assertEqual({'question.txt','draft.md','deterministic_checks.json'},set(received['critic_instruction']))
    def test_opt_in_combines_two_calls_without_dropping_other_critics(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=self.make_run(Path(tmp));r.cfg['critic_policy']['combine_light']=True
            with mock.patch.object(r,'call',return_value={'findings':[]}) as call:r.step_critics()
            self.assertEqual(1,call.call_count)
            self.assertEqual('critic_combined',call.call_args.args[0])
            cfg=load(Path(tmp),preset='lean');a=plan_run(cfg,'light');cfg['critic_policy']['combine_light']=True;b=plan_run(cfg,'light')
            self.assertEqual(a['planned_calls_max']-1,b['planned_calls_max'])
            cfg['light']['critics'].append('depth')
            self.assertFalse(plan_run(cfg,'light')['combined_critic'])
