import unittest
from hprc.research_review import check_calculation, evidence_matrix, render_matrix

class ReviewToolsTests(unittest.TestCase):
    def spec(self, op='percent_change'):
        return {'operation': op, 'operands': [
            {'source_id':'S1','start':0,'end':5,'quote':'10 kW','unit':'kW'},
            {'source_id':'S2','start':0,'end':5,'quote':'15 kW','unit':'kW'}], 'expected':'50'}
    def test_bound_percent_and_hashes(self):
        result=check_calculation(self.spec(),{'S1':'10 kW','S2':'15 kW'})
        self.assertEqual('50.0',result['result']);self.assertTrue(result['matches_expected'])
        self.assertEqual(64,len(result['bindings'][0]['source_sha256']))
    def test_quotes_units_and_zero_denominator_fail_closed(self):
        for sources in ({'S1':'11 kW','S2':'15 kW'},{'S1':'10 kg','S2':'15 kW'}):
            with self.assertRaises(ValueError):check_calculation(self.spec(),sources)
        spec=self.spec();spec['operands'][0].update(end=4,quote='0 kW')
        with self.assertRaises(ValueError):check_calculation(spec,{'S1':'0 kW','S2':'15 kW'})
    def test_partial_number_cannot_be_bound(self):
        spec={'operation':'sum','operands':[{'source_id':'S1','start':1,'end':2,'quote':'2','unit':''}]}
        with self.assertRaises(ValueError):check_calculation(spec,{'S1':'12'})
    def test_matrix_does_not_invent_support(self):
        matrix=evidence_matrix({'claims':[{'statement':'a|b','evidence_links':[{'source_alias':'S1','relation':'unchecked'}]}]})
        self.assertIn('unchecked',render_matrix(matrix));self.assertIn('unknown',render_matrix(matrix))
        self.assertIn('a\\|b',render_matrix(matrix))

    def test_unit_and_exponent_suffixes_cannot_be_truncated(self):
        for text,quote,unit in [('12 kWh','12 kW','kW'),('1e3','1',''),('12 kW','12','')]:
            spec={'operation':'sum','operands':[{'source_id':'S1','start':0,'end':len(quote),'quote':quote,'unit':unit}]}
            with self.assertRaises(ValueError):check_calculation(spec,{'S1':text})

    def test_unicode_sign_counter_and_group_separator_cannot_be_cut(self):
        for text,start,quote,unit in [('−12 kW',1,'12 kW','kW'),('12 개소',0,'12 개','개'),('1,234',0,'1','')]:
            spec={'operation':'sum','operands':[{'source_id':'S1','start':start,'end':start+len(quote),'quote':quote,'unit':unit}]}
            with self.assertRaises(ValueError):check_calculation(spec,{'S1':text})

    def test_sentence_period_after_unit_is_not_a_partial_token(self):
        spec={'operation':'sum','operands':[{'source_id':'S1','start':0,'end':5,'quote':'10 kW','unit':'kW'}]}
        self.assertEqual('10',check_calculation(spec,{'S1':'10 kW.'})['result'])
