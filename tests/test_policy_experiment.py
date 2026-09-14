import copy
import unittest
from hprc.policy_experiment import compare_policy
from hprc.token_policy import fingerprint
class PolicyExperimentTests(unittest.TestCase):
    def pair(self):
        cfg={'verification':{'semantic':False},'light':{'target_words':700}}
        meta={k:'fixed' for k in ('code_revision','prompt_hashes','benchmark_version','frozen_at','frozen_input_hash','as_of')}
        meta.update(role_assignments={'writer':{'model':'fixed'}},runtime_consistent=True,config_snapshot=cfg,config_hash=fingerprint(cfg))
        a={'case_id':'case','input_hash':'same','runtime_metadata':meta,'reported_total_tokens':100,'unknowncalls':0,'quality_qualified':True}
        b=copy.deepcopy(a);b['runtime_metadata']['config_snapshot']['verification']['semantic']=True;b['runtime_metadata']['config_hash']=fingerprint(b['runtime_metadata']['config_snapshot']);b['reported_total_tokens']=120
        return a,b
    def test_explicit_toggle_only(self):
        a,b=self.pair();self.assertEqual(20,compare_policy(a,b,['verification.semantic'])['total_token_delta'])
    def test_length_change_rejected(self):
        a,b=self.pair();b['runtime_metadata']['config_snapshot']['light']['target_words']=50;b['runtime_metadata']['config_hash']=fingerprint(b['runtime_metadata']['config_snapshot'])
        with self.assertRaises(ValueError):compare_policy(a,b,['verification.semantic'])
    def test_unknown_cost_has_no_complete_delta(self):
        a,b=self.pair();b['unknowncalls']=1;self.assertIsNone(compare_policy(a,b,['verification.semantic'])['total_token_delta'])

    def test_unverified_quality_is_unknown_not_a_failure(self):
        a,b=self.pair();b['quality_qualified']=None
        self.assertIsNone(compare_policy(a,b,['verification.semantic'])['quality_preserved'])
        a['quality_qualified']=False
        self.assertFalse(compare_policy(a,b,['verification.semantic'])['quality_preserved'])

    def test_missing_usage_completeness_does_not_produce_a_token_delta(self):
        a,b=self.pair();del b['unknowncalls']
        self.assertIsNone(compare_policy(a,b,['verification.semantic'])['total_token_delta'])

    def test_efficiency_packet_is_an_explicit_allowed_toggle(self):
        a,b=self.pair()
        b['runtime_metadata']['config_snapshot']['verification']['semantic']=False
        for row in (a,b):
            row['runtime_metadata']['config_snapshot']['efficiency']={'packet_inputs':False,'evidence_selection':False}
            row['runtime_metadata']['config_hash']=fingerprint(row['runtime_metadata']['config_snapshot'])
        b['runtime_metadata']['config_snapshot']['efficiency']['packet_inputs']=True
        b['runtime_metadata']['config_hash']=fingerprint(b['runtime_metadata']['config_snapshot'])
        self.assertEqual({'baseline':False,'candidate':True},compare_policy(a,b,['efficiency.packet_inputs'])['changes']['efficiency.packet_inputs'])

    def test_efficiency_inline_is_an_explicit_allowed_toggle(self):
        a,b=self.pair()
        b['runtime_metadata']['config_snapshot']['verification']['semantic']=False
        for row in (a,b):
            row['runtime_metadata']['config_snapshot']['efficiency']={'packet_inputs':False,'inline_inputs':False,'evidence_selection':False}
            row['runtime_metadata']['config_hash']=fingerprint(row['runtime_metadata']['config_snapshot'])
        b['runtime_metadata']['config_snapshot']['efficiency']['inline_inputs']=True
        b['runtime_metadata']['config_hash']=fingerprint(b['runtime_metadata']['config_snapshot'])
        self.assertEqual({'baseline':False,'candidate':True},compare_policy(a,b,['efficiency.inline_inputs'])['changes']['efficiency.inline_inputs'])

    def test_non_boolean_quality_flag_is_not_a_pass(self):
        a,b=self.pair();a['quality_qualified']=1;b['quality_qualified']=1
        self.assertIsNone(compare_policy(a,b,['verification.semantic'])['quality_preserved'])
