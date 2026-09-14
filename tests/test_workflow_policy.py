import copy
import unittest
from hprc.config import DEFAULTS
from hprc.workflow_policy import workflow_config
from hprc.token_policy import plan_run

class WorkflowPolicyTests(unittest.TestCase):
    def test_only_opted_in_full_facts_uses_single_draft(self):
        cfg=copy.deepcopy(DEFAULTS);cfg['efficiency']['strategy']='adaptive';cfg['report_format']='facts'
        changed,route=workflow_config(cfg,'full')
        self.assertTrue(route['single_draft']);self.assertEqual(1,changed['full']['drafts'])
        self.assertFalse(changed['full']['polish']);self.assertEqual(cfg['full']['critics'],changed['full']['critics'])
        self.assertEqual(cfg['full']['cite_sample'],changed['full']['cite_sample'])
        self.assertEqual(3,cfg['full']['drafts'])
        self.assertFalse(workflow_config(cfg,'light')[1]['single_draft'])
        cfg['report_format']='comparison';self.assertFalse(workflow_config(cfg,'full')[1]['single_draft'])
    def test_plan_accounts_for_removed_drafts_synthesis_and_polish(self):
        cfg=copy.deepcopy(DEFAULTS);before=plan_run(cfg,'full')['planned_calls_max']
        cfg['efficiency']['strategy']='adaptive';cfg['report_format']='facts'
        after=plan_run(cfg,'full')['planned_calls_max']
        self.assertEqual(4,before-after)
