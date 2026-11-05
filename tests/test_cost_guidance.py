import json
import tempfile
import unittest
from pathlib import Path
from hprc.config import load
from hprc.cost_guidance import cost_guidance,render_cost_guidance
from hprc import pipeline

class CostGuidanceTests(unittest.TestCase):
    def test_unknown_does_not_display_fake_remaining_tokens(self):
        cfg={'budget':{'max_input_tokens':100,'max_total_tokens':200,'max_model_calls':4}}
        data=cost_guidance(cfg,[{'usage_known':False}],{'a':20},'측정 실패')
        self.assertIsNone(data['remaining']['total'])
        self.assertEqual(3,data['remaining']['calls'])
        self.assertIn('미확정',render_cost_guidance(data))
        self.assertIn('측정 실패',render_cost_guidance(data))
    def test_step_costs_include_failed_attempts_without_double_cache(self):
        rows=[{'step':'writer','status':'error','attempt':2,'usage_known':True,'usage':{'input_tokens':100,'cached_input_tokens':80,'output_tokens':20}}]
        data=cost_guidance({'budget':{'max_total_tokens':200}},rows)
        self.assertEqual(120,data['by_step']['writer']['total_tokens'])
        self.assertEqual(80,data['remaining']['total'])
        self.assertIn('writer',render_cost_guidance(data))
    def test_mixed_usage_keeps_known_costs_but_leaves_token_balance_unknown(self):
        cfg={'budget':{'max_input_tokens':100,'max_total_tokens':200,'max_model_calls':4,'output_reservation':30}}
        rows=[{'step':'writer','status':'ok','usage_known':True,
               'usage':{'input_tokens':40,'cached_input_tokens':20,'output_tokens':10}},
              {'step':'critic','status':'error','attempt':2,'usage_known':False}]
        data=cost_guidance(cfg,rows,{'next':25})
        self.assertEqual(50,data['usage']['total_tokens'])
        self.assertEqual(1,data['usage']['unknown_calls'])
        self.assertEqual(1,data['usage']['failed_calls'])
        self.assertEqual(1,data['usage']['retry_calls'])
        self.assertEqual({'input':None,'total':None,'calls':2},data['remaining'])
        self.assertEqual((25,30),(data['reserved_input'],data['reserved_output']))
        self.assertTrue(data['by_step']['writer']['complete'])
        self.assertFalse(data['by_step']['critic']['complete'])
        for lang,unknown,qualifier in [('ko','미확정','측정분'),('en','unknown','known only')]:
            with self.subTest(lang=lang):
                rendered=render_cost_guidance(data,lang)
                self.assertIn('Input + output: 50 ('+qualifier+')',rendered)
                self.assertIn('Remaining input: '+unknown+' · total: '+unknown+' · calls: 2',rendered)

    def test_exhausted_limits_do_not_render_negative_balances(self):
        cfg={'budget':{'max_input_tokens':10,'max_total_tokens':20,'max_model_calls':0}}
        data=cost_guidance(cfg,[{'usage_known':True,'usage':{'input_tokens':30,'output_tokens':5}}])
        self.assertEqual({'input':0,'total':0,'calls':0},data['remaining'])
        self.assertIn('Remaining input: 0 · total: 0 · calls: 0',render_cost_guidance(data,'en'))

    def test_budget_stop_has_persistent_explanation(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=pipeline.Run(Path(tmp),'q','light','stop',quiet=True,total_budget=10)
            with self.assertRaises(pipeline.Blocked):run._reserve_call('a','writer','p',{},'writer')
            state=json.loads((run.dir/'state.json').read_text())
            self.assertTrue(state['stop_reason'])
            self.assertEqual(state['stop_reason'],json.loads((run.dir/'cost_guidance.json').read_text())['stop_reason'])

    def test_inflight_completion_refreshes_stopped_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=pipeline.Run(Path(tmp),'q','light','parallel-stop',quiet=True,total_budget=7000)
            run._reserve_call('writer:1','writer','p',{},'writer')
            with self.assertRaises(pipeline.Blocked):run._reserve_call('critic:1','critic','p',{},'critic')
            before=json.loads((run.dir/'state.json').read_text())
            run._record_attempt('writer',1,{'usage_known':True,'usage':{'input_tokens':100,'output_tokens':20}},1,'ok')
            state=json.loads((run.dir/'state.json').read_text())
            guide=json.loads((run.dir/'cost_guidance.json').read_text())
            self.assertEqual(before['stop_reason'],state['stop_reason'])
            self.assertEqual('budget_stop',state['status'])
            self.assertEqual(120,guide['usage']['total_tokens'])
            self.assertEqual(6880,guide['remaining']['total'])
            self.assertEqual(0,guide['reserved_input']+guide['reserved_output'])
