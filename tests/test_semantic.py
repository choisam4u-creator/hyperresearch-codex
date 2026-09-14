import unittest

from hprc.semantic import SEMANTIC_CITECHECK, validate_semantic_checks


def atom(quote, verdict, evidence, conditions="", limitations=""):
    return {"quote": quote, "verdict": verdict, "evidence": evidence,
            "conditions": conditions, "limitations": limitations}


def evidence(source_id, quote, relation="supports"):
    return {"source_id": source_id, "quote": quote, "relation": relation}


class SemanticCheckTests(unittest.TestCase):
    def setUp(self):
        self.samples = [{"sentence": "Alpha is fast and Beta is audited. [S1][S2]", "cites": ["S1", "S2"], "line": 7}]
        self.sources = {"S1": "Tests state that Alpha is fast under warm-cache conditions.",
                        "S2": "The registry records that Beta is audited."}

    def response(self, atoms, supported=True):
        return {"checks": [{"sentence": self.samples[0]["sentence"], "cites": ["S2", "S1"],
                            "supported": supported, "reason": "model assertion", "atoms": atoms}]}

    def test_schema_is_strict_and_requires_semantic_fields(self):
        self.assertFalse(SEMANTIC_CITECHECK["additionalProperties"])
        check = SEMANTIC_CITECHECK["properties"]["checks"]["items"]
        self.assertFalse(check["additionalProperties"])
        self.assertEqual({"sentence", "cites", "supported", "reason", "atoms"}, set(check["required"]))
        atom_schema = check["properties"]["atoms"]["items"]
        self.assertEqual({"quote", "verdict", "evidence", "conditions", "limitations"}, set(atom_schema["required"]))

    def test_valid_support_is_legacy_compatible_and_bound_to_exact_offsets(self):
        response = self.response([
            atom("Alpha is fast", "supported", [evidence("S1", "Alpha is fast")], conditions="warm cache"),
            atom("Beta is audited", "supported", [evidence("S2", "Beta is audited")]),
        ])
        result = validate_semantic_checks(response, self.samples, self.sources)
        self.assertEqual([{"sentence": self.samples[0]["sentence"], "cites": ["S1", "S2"],
                           "supported": True, "reason": "model assertion", "line": 7}], result["checks"])
        record = result["semantic"]["records"][0]
        bound = record["validated_atoms"][0]["evidence"][0]
        self.assertEqual("Alpha is fast", self.sources["S1"][bound["char_start"]:bound["char_end"]])
        self.assertEqual(64, len(bound["source_sha256"]))
        self.assertFalse(result["semantic"]["scope"]["semantic_decomposition_complete"])
        self.assertFalse(result["semantic"]["scope"]["factual_accuracy_truth_guarantee"])
        self.assertFalse(record["deterministic_character_coverage"]["is_semantic_coverage"])
        self.assertTrue(record["deterministic_character_coverage"]["complete"])

    def test_mixed_compound_claim_is_not_overall_supported(self):
        response = self.response([
            atom("Alpha is fast", "supported", [evidence("S1", "Alpha is fast")]),
            atom("Beta is audited", "insufficient", []),
        ])
        result = validate_semantic_checks(response, self.samples, self.sources)
        self.assertFalse(result["checks"][0]["supported"])
        self.assertEqual("insufficient", result["semantic"]["records"][0]["overall_verdict"])

    def test_fabricated_atom_quote_leaves_sample_unchecked(self):
        response = self.response([atom("Gamma is certified", "supported", [evidence("S1", "Alpha is fast")])])
        result = validate_semantic_checks(response, self.samples, self.sources)
        self.assertEqual([], result["checks"])
        self.assertEqual("unchecked", result["semantic"]["records"][0]["status"])
        self.assertIn("atom_not_exact_substring", {issue["kind"] for issue in result["semantic"]["records"][0]["issues"]})

    def test_fabricated_source_quote_leaves_sample_unchecked(self):
        response = self.response([atom("Alpha is fast", "supported", [evidence("S1", "Alpha won every test")])])
        result = validate_semantic_checks(response, self.samples, self.sources)
        self.assertEqual([], result["checks"])
        self.assertIn("evidence_quote_not_exact_substring", {issue["kind"] for issue in result["semantic"]["records"][0]["issues"]})

    def test_evidence_source_must_be_in_parent_cites_and_sent_inputs(self):
        sources = {**self.sources, "S3": "Alpha is fast."}
        response = self.response([atom("Alpha is fast", "supported", [evidence("S3", "Alpha is fast")])])
        result = validate_semantic_checks(response, self.samples, sources)
        self.assertEqual([], result["checks"])
        self.assertIn("evidence_source_not_parent_cite", {issue["kind"] for issue in result["semantic"]["records"][0]["issues"]})

        no_sent_source = self.response([atom("Alpha is fast", "supported", [evidence("S1", "Alpha is fast")])])
        result = validate_semantic_checks(no_sent_source, self.samples, {"S2": self.sources["S2"]})
        self.assertIn("evidence_source_not_sent", {issue["kind"] for issue in result["semantic"]["records"][0]["issues"]})

    def test_missing_or_duplicate_atoms_remain_unchecked(self):
        missing = validate_semantic_checks(self.response([]), self.samples, self.sources)
        self.assertEqual([], missing["checks"])
        self.assertIn("atoms_missing", {issue["kind"] for issue in missing["semantic"]["records"][0]["issues"]})

        repeated = atom("Alpha is fast", "supported", [evidence("S1", "Alpha is fast")])
        duplicate = validate_semantic_checks(self.response([repeated, repeated]), self.samples, self.sources)
        self.assertEqual([], duplicate["checks"])
        self.assertIn("duplicate_atom", {issue["kind"] for issue in duplicate["semantic"]["records"][0]["issues"]})

    def test_unknown_verdict_is_rejected_even_if_schema_would_also_reject_it(self):
        response = self.response([atom("Alpha is fast", "maybe", [evidence("S1", "Alpha is fast")])])
        result = validate_semantic_checks(response, self.samples, self.sources)
        self.assertEqual([], result["checks"])
        self.assertIn("unknown_atom_verdict", {issue["kind"] for issue in result["semantic"]["records"][0]["issues"]})

    def test_blank_quote_and_extra_fields_are_rejected(self):
        bad_atom = atom(" ", "insufficient", [])
        bad_atom["extra"] = "not allowed"
        result = validate_semantic_checks(self.response([bad_atom], supported=False), self.samples, self.sources)
        kinds = {issue["kind"] for issue in result["semantic"]["records"][0]["issues"]}
        self.assertTrue({"atom_not_exact_substring", "atom_fields_invalid"} <= kinds)
        self.assertEqual([], result["checks"])

    def test_mock_insufficient_atom_is_valid_but_never_supported(self):
        response = self.response([atom("Alpha is fast", "insufficient", [], limitations="mock, not a real judgment")],
                                 supported=False)
        result = validate_semantic_checks(response, self.samples, self.sources)
        self.assertEqual("validated", result["semantic"]["records"][0]["status"])
        self.assertEqual("insufficient", result["semantic"]["records"][0]["overall_verdict"])
        self.assertFalse(result["checks"][0]["supported"])
        self.assertFalse(result["semantic"]["scope"]["mock_outputs_are_real_judgments"])

    def test_clean_contradiction_returns_legacy_false(self):
        response = self.response([
            atom("Alpha is fast", "contradicted", [evidence("S1", "Alpha is fast", "contradicts")]),
            atom("Beta is audited", "supported", [evidence("S2", "Beta is audited")]),
        ])
        result = validate_semantic_checks(response, self.samples, self.sources)
        self.assertFalse(result["checks"][0]["supported"])
        self.assertEqual("contradicted", result["semantic"]["records"][0]["overall_verdict"])

    def test_unmatched_response_and_missing_sample_are_explicit(self):
        response = {"checks": [{"sentence": "Changed. [S1]", "cites": ["S1"], "supported": True,
                                "reason": "mock, not a real judgment", "atoms": []}]}
        result = validate_semantic_checks(response, self.samples, self.sources)
        self.assertEqual([], result["checks"])
        self.assertIn("check_not_exact_sample", {issue["kind"] for issue in result["semantic"]["issues"]})
        self.assertEqual("unchecked", result["semantic"]["records"][0]["status"])
        self.assertFalse(result["semantic"]["scope"]["mock_outputs_are_real_judgments"])

    def test_duplicate_matching_checks_invalidate_the_affected_sample(self):
        first = self.response([atom("Alpha is fast", "supported", [evidence("S1", "Alpha is fast")])])["checks"][0]
        second = {**first, "supported": False, "reason": "conflicting duplicate"}
        result = validate_semantic_checks({"checks": [first, second]}, self.samples, self.sources)
        self.assertEqual([], result["checks"])
        self.assertEqual("unchecked", result["semantic"]["records"][0]["status"])
        self.assertIn("duplicate_check", {issue["kind"] for issue in result["semantic"]["records"][0]["issues"]})

    def test_untrusted_non_string_identity_and_evidence_fields_do_not_raise(self):
        malformed = {"checks": [{"sentence": ["not", "hashable"], "cites": ["S1"], "supported": True,
                                 "reason": "bad", "atoms": []}]}
        result = validate_semantic_checks(malformed, self.samples, self.sources)
        self.assertIn("check_identity_invalid", {issue["kind"] for issue in result["semantic"]["issues"]})

        bad_evidence = self.response([atom("Alpha is fast", "supported", [evidence(["S1"], "Alpha is fast")])])
        result = validate_semantic_checks(bad_evidence, self.samples, self.sources)
        self.assertIn("evidence_field_types_invalid", {issue["kind"] for issue in result["semantic"]["records"][0]["issues"]})

    def test_optional_original_source_binding_records_original_offsets(self):
        response = self.response([atom("Alpha is fast", "supported", [evidence("S1", "Alpha is fast")]),
                                  atom("Beta is audited", "supported", [evidence("S2", "Beta is audited")])])
        originals = {"S1": "Earlier paragraph. " + self.sources["S1"], "S2": self.sources["S2"]}
        result = validate_semantic_checks(response, self.samples, self.sources, original_sources=originals)
        bound = result["semantic"]["records"][0]["validated_atoms"][0]["evidence"][0]
        self.assertEqual("Alpha is fast", originals["S1"][bound["original_char_start"]:bound["original_char_end"]])
        self.assertEqual(64, len(bound["original_source_sha256"]))
        self.assertTrue(result["semantic"]["scope"]["original_source_binding"])

    def test_generated_omission_marker_cannot_be_evidence_when_original_is_supplied(self):
        sentence = "Alpha is fast. [S1]"
        samples = [{"sentence": sentence, "cites": ["S1"]}]
        sent = {"S1": "Alpha is fast.\n[… 관련도 낮은 900자 생략: 이 노트는 잘렸다 …]"}
        originals = {"S1": "Alpha is fast. Original continuation."}
        response = {"checks": [{"sentence": sentence, "cites": ["S1"], "supported": True, "reason": "bad marker",
                                "atoms": [atom("Alpha is fast", "supported",
                                               [evidence("S1", "[… 관련도 낮은 900자 생략: 이 노트는 잘렸다 …]")])]}]}
        result = validate_semantic_checks(response, samples, sent, original_sources=originals)
        self.assertEqual([], result["checks"])
        self.assertIn("evidence_quote_not_in_original",
                      {issue["kind"] for issue in result["semantic"]["records"][0]["issues"]})

    def test_only_first_clause_cannot_make_compound_north_south_claim_supported(self):
        sentence = "North grew 5%, while South fell 3% in 2026. [S1][S2]"
        samples = [{"sentence": sentence, "cites": ["S1", "S2"]}]
        sources = {"S1": "North grew 5% in the measured period.", "S2": "South fell 3% in 2026."}
        response = {"checks": [{"sentence": sentence, "cites": ["S1", "S2"], "supported": True, "reason": "partial",
                                "atoms": [atom("North grew 5%", "supported", [evidence("S1", "North grew 5%")])]}]}
        result = validate_semantic_checks(response, samples, sources)
        record = result["semantic"]["records"][0]
        self.assertFalse(result["checks"][0]["supported"])
        self.assertEqual("insufficient", record["overall_verdict"])
        self.assertFalse(record["deterministic_character_coverage"]["complete"])
        self.assertIn("South", record["deterministic_character_coverage"]["uncovered_fragments"])

    def test_mixed_source_binding_cannot_borrow_quote_from_other_cited_source(self):
        sentence = "North grew 5% and South fell 3%. [S1][S2]"
        samples = [{"sentence": sentence, "cites": ["S1", "S2"]}]
        sources = {"S1": "North grew 5%.", "S2": "South fell 3%."}
        response = {"checks": [{"sentence": sentence, "cites": ["S1", "S2"], "supported": True, "reason": "mixed",
                                "atoms": [atom("North grew 5%", "supported", [evidence("S1", "North grew 5%")]),
                                          atom("South fell 3%", "supported", [evidence("S1", "South fell 3%")])]}]}
        result = validate_semantic_checks(response, samples, sources)
        self.assertEqual([], result["checks"])
        self.assertIn("evidence_quote_not_exact_substring",
                      {issue["kind"] for issue in result["semantic"]["records"][0]["issues"]})

    def test_omitted_condition_prevents_supported_even_when_core_number_is_bound(self):
        sentence = "Latency is 2 seconds only under warm cache. [S1]"
        samples = [{"sentence": sentence, "cites": ["S1"]}]
        sources = {"S1": "Latency is 2 seconds only under warm cache."}
        response = {"checks": [{"sentence": sentence, "cites": ["S1"], "supported": True, "reason": "condition omitted",
                                "atoms": [atom("Latency is 2 seconds", "supported",
                                               [evidence("S1", "Latency is 2 seconds")])]}]}
        result = validate_semantic_checks(response, samples, sources)
        record = result["semantic"]["records"][0]
        self.assertFalse(result["checks"][0]["supported"])
        self.assertIn("substantive_coverage_incomplete", {issue["kind"] for issue in record["issues"]})
        self.assertTrue({"only", "under", "warm", "cache"} <= set(record["deterministic_character_coverage"]["uncovered_fragments"]))

    def test_omitted_comparison_operator_prevents_complete_coverage(self):
        sentence = "x < 2 under load. [S1]"
        samples = [{"sentence": sentence, "cites": ["S1"]}]
        sources = {"S1": "x < 2 under load."}
        response = {"checks": [{"sentence": sentence, "cites": ["S1"], "supported": True, "reason": "operator omitted",
                                "atoms": [atom("x", "supported", [evidence("S1", "x < 2")]),
                                          atom("2 under load", "supported", [evidence("S1", "2 under load")])]}]}
        result = validate_semantic_checks(response, samples, sources)
        record = result["semantic"]["records"][0]
        self.assertFalse(result["checks"][0]["supported"])
        self.assertIn("<", record["deterministic_character_coverage"]["uncovered_fragments"])
        self.assertIn("Atomic quotes omit", result["checks"][0]["reason"])

    def test_included_operators_units_and_numeric_separators_complete_coverage(self):
        sentence = "Error is ≤ 2.5% +/- 0.5% at 20℃. [S1]"
        samples = [{"sentence": sentence, "cites": ["S1"]}]
        sources = {"S1": sentence.removesuffix(" [S1]")}
        claim = sentence.removesuffix(". [S1]")
        response = {"checks": [{"sentence": sentence, "cites": ["S1"], "supported": True, "reason": "fully quoted",
                                "atoms": [atom(claim, "supported", [evidence("S1", claim)])]}]}
        result = validate_semantic_checks(response, samples, sources)
        coverage = result["semantic"]["records"][0]["deterministic_character_coverage"]
        self.assertTrue(result["checks"][0]["supported"])
        self.assertTrue(coverage["complete"])
        self.assertEqual("comparison_range_arithmetic_unit_symbols", coverage["meaning_bearing_symbols_required"])

    def test_markdown_emphasis_markers_are_presentation_not_required_claim_content(self):
        sentence = "**Latency** is < 2 s. [S1]"
        samples = [{"sentence": sentence, "cites": ["S1"]}]
        sources = {"S1": "Latency is < 2 s."}
        response = {"checks": [{"sentence": sentence, "cites": ["S1"], "supported": True, "reason": "markup excluded",
                                "atoms": [atom("Latency", "supported", [evidence("S1", "Latency")]),
                                          atom("is < 2 s", "supported", [evidence("S1", "is < 2 s")])]}]}
        result = validate_semantic_checks(response, samples, sources)
        coverage = result["semantic"]["records"][0]["deterministic_character_coverage"]
        self.assertTrue(result["checks"][0]["supported"])
        self.assertTrue(coverage["markdown_syntax_excluded"])


if __name__ == "__main__":
    unittest.main()
