import unittest

from hprc.verification import verify_report


class VerificationTests(unittest.TestCase):
    def test_exact_long_quote_in_cited_source_passes_without_claiming_full_coverage(self):
        quote = "모델은 사람이 검토한 근거만 사용해야 한다"
        report = f'설명: "{quote}" [S1]\n'
        result = verify_report(report, {"S1": f"서문. {quote}. 끝."}, [],
                               {"scope": "sample_only", "eligible_count": 1, "selected_count": 0, "checked_count": 0}, report, [], [])
        self.assertEqual("passed", result["status"])
        self.assertFalse(result["scope"]["full_report_verification"])

    def test_short_and_multiline_quotes_do_not_create_false_direct_quote_issue(self):
        report = '짧은 "인용" [S1]\n"여러\n줄 인용문입니다" [S1]\n'
        result = verify_report(report, {"S1": "다른 원문"}, [], {"selected_count": 0, "checked_count": 0}, report, [], [])
        self.assertFalse(any(issue["kind"].startswith("direct_quote") for issue in result["issues"]))

    def test_apostrophe_contraction_is_not_treated_as_direct_quote(self):
        result = verify_report("It's a documented limitation. [S1]\n", {"S1": "다른 원문"}, [],
                               {"selected_count": 0, "checked_count": 0}, "It's a documented limitation. [S1]\n", [], [])
        self.assertFalse(any(issue["kind"].startswith("direct_quote") for issue in result["issues"]))

    def test_source_line_wrap_does_not_make_a_matching_direct_quote_fail(self):
        quote = "모델은 사람이 검토한 근거만 사용해야 한다"
        wrapped = "모델은 사람이 검토한\n근거만 사용해야 한다"
        result = verify_report(f'"{quote}" [S1]\n', {"S1": wrapped}, [],
                               {"selected_count": 0, "checked_count": 0}, f'"{quote}" [S1]\n', [], [])
        self.assertFalse(any(issue["kind"] == "direct_quote_not_found" for issue in result["issues"]))

    def test_unknown_number_requires_review_not_false_confirmation(self):
        report = "비용은 42% 줄었다. [S1]\n"
        result = verify_report(report, {"S1": "비용 변화는 측정하지 못했다."}, [], {"selected_count": 0, "checked_count": 0}, report, [], [])
        issue = next(issue for issue in result["issues"] if issue["kind"] == "numeric_evidence_unclear")
        self.assertEqual("medium", issue["severity"])
        self.assertEqual("review_required", result["status"])

    def test_numeric_comparison_uses_complete_tokens_not_substrings(self):
        result = verify_report("비용은 20% 줄었다. [S1]\n", {"S1": "비용은 120%였다."}, [],
                               {"selected_count": 0, "checked_count": 0}, "비용은 20% 줄었다. [S1]\n", [], [])
        self.assertTrue(any(issue["kind"] == "numeric_evidence_unclear" for issue in result["issues"]))

    def test_unsupported_and_high_unresolved_findings_require_review(self):
        report = "근거 문장 [S1]\n"
        result = verify_report(report, {"S1": "근거"}, [{"sentence": "근거 문장 [S1]", "cites": ["S1"], "supported": False,
                                                        "reason": "부분 지지", "line": 1}],
                               {"selected_count": 1, "checked_count": 1}, report,
                               [{"id": "F1", "severity": "high"}], ["F1"])
        self.assertEqual({"citation_unsupported", "high_finding_unresolved"}, {issue["kind"] for issue in result["issues"]})

    def test_changed_cited_claim_and_legacy_metadata_require_review(self):
        result = verify_report("수정 근거 [S1]\n", {"S1": "근거"}, [], None, "이전 근거 [S1]\n", [], [])
        kinds = {issue["kind"] for issue in result["issues"]}
        self.assertIn("sampling_metadata_missing", kinds)
        self.assertIn("cited_claim_changed_after_check", kinds)

    def test_missing_or_unmatched_sampling_results_require_review(self):
        result = verify_report("근거 [S1]\n", {"S1": "근거"}, [],
                               {"selected_count": 3, "checked_count": 1, "unmatched_count": 2}, "근거 [S1]\n", [], [])
        self.assertEqual({"citation_sample_missing", "citation_check_unmatched"}, {issue["kind"] for issue in result["issues"]})

    def test_non_cited_insert_does_not_look_like_post_polish_citation_change(self):
        result = verify_report("새 설명\n근거 문장 [S1]\n", {"S1": "근거 문장"}, [],
                               {"selected_count": 0, "checked_count": 0}, "근거 문장 [S1]\n", [], [])
        self.assertFalse(any(issue["kind"] == "cited_claim_changed_after_check" for issue in result["issues"]))

    def test_equivalent_time_units_pass_when_context_matches(self):
        report = "Measured latency was 2 seconds. [S1]\n"
        result = verify_report(report, {"S1": "Measured latency was 2000 ms."}, [],
                               {"selected_count": 0, "checked_count": 0}, report, [], [])
        self.assertFalse(any(issue["kind"].startswith("numeric_") for issue in result["issues"]))

    def test_same_number_in_different_context_requires_review(self):
        report = "Revenue increased by 20%. [S1]\n"
        result = verify_report(report, {"S1": "Network latency increased by 20%."}, [],
                               {"selected_count": 0, "checked_count": 0}, report, [], [])
        self.assertTrue(any(issue["kind"] == "numeric_context_unclear" for issue in result["issues"]))

    def test_opposite_direction_with_same_number_requires_review(self):
        report = "Measured cost decreased by 20%. [S1]\n"
        result = verify_report(report, {"S1": "Measured cost increased by 20%."}, [],
                               {"selected_count": 0, "checked_count": 0}, report, [], [])
        self.assertTrue(any(issue["kind"] == "numeric_context_unclear" for issue in result["issues"]))

    def test_equivalent_date_formats_pass_and_wrong_date_does_not(self):
        report = "The release date was September 14, 2026. [S1]\n"
        good = verify_report(report, {"S1": "The release date was 2026-09-14."}, [],
                             {"selected_count": 0, "checked_count": 0}, report, [], [])
        self.assertFalse(any(issue["kind"].startswith("date_") for issue in good["issues"]))
        bad = verify_report(report, {"S1": "The release date was 2026-09-15."}, [],
                            {"selected_count": 0, "checked_count": 0}, report, [], [])
        self.assertTrue(any(issue["kind"] == "date_evidence_unclear" for issue in bad["issues"]))

    def test_korean_date_ranges_are_not_treated_as_independent_quantities(self):
        report = "2026년 7월 22~24일과 8월 6~8일에는 자동 명령을 중단했다. [S1]\n"
        source = "7월 22일부터 24일, 8월 6일부터 8일에는 자동 명령을 중단했다."
        result = verify_report(report, {"S1": source}, [], {"selected_count": 0, "checked_count": 0}, report, [], [])
        numeric = [issue for issue in result["issues"] if issue["kind"].startswith("numeric_")]
        self.assertEqual([], numeric)
        self.assertTrue(any(issue["kind"] == "date_evidence_unclear" for issue in result["issues"]))

    def test_invalid_korean_date_range_stays_under_date_review(self):
        report = "2026년 2월 30~31일에 점검했다. [S1]\n"
        result = verify_report(report, {"S1": "점검 기록"}, [], {"selected_count": 0, "checked_count": 0}, report, [], [])
        self.assertTrue(any(issue["kind"] == "date_evidence_unclear" for issue in result["issues"]))
        self.assertFalse(any(issue["kind"].startswith("numeric_") for issue in result["issues"]))

    def test_reversed_date_ranges_cannot_match_valid_source_ranges(self):
        for date in ("2026년 7월 24~22일", "2026년 7월 24일부터 22일"):
            report = date + "에 점검했다. [S1]\n"
            result = verify_report(report, {"S1": "2026년 7월 22~24일에 점검했다."}, [],
                                   {"selected_count": 0, "checked_count": 0}, report, [], [])
            self.assertTrue(any(issue["kind"] == "date_evidence_unclear" for issue in result["issues"]))
            self.assertFalse(any(issue["kind"].startswith("numeric_") for issue in result["issues"]))

    def test_unknown_source_power_unit_cannot_support_unitless_value(self):
        report = "Measured value was 12. [S1]\n"
        result = verify_report(report, {"S1": "Measured value was 12 MW."}, [],
                               {"selected_count": 0, "checked_count": 0}, report, [], [])
        self.assertTrue(any(issue["kind"] == "numeric_evidence_unclear" for issue in result["issues"]))

    def test_power_and_energy_units_are_distinct_but_scale_within_dimension(self):
        power = verify_report("Measured power was 12 kW. [S1]\n", {"S1": "Measured power was 12000 W."}, [],
                              {"selected_count": 0, "checked_count": 0}, "Measured power was 12 kW. [S1]\n", [], [])
        energy = verify_report("Measured energy was 12 kWh. [S1]\n", {"S1": "Measured energy was 12000 Wh."}, [],
                               {"selected_count": 0, "checked_count": 0}, "Measured energy was 12 kWh. [S1]\n", [], [])
        mismatch = verify_report("Measured energy was 12 kW. [S1]\n", {"S1": "Measured energy was 12 kWh."}, [],
                                 {"selected_count": 0, "checked_count": 0}, "Measured energy was 12 kW. [S1]\n", [], [])
        self.assertFalse(any(issue["kind"].startswith("numeric_") for issue in power["issues"]))
        self.assertFalse(any(issue["kind"].startswith("numeric_") for issue in energy["issues"]))
        self.assertTrue(any(issue["kind"] == "numeric_evidence_unclear" for issue in mismatch["issues"]))

    def test_unspaced_unsupported_power_units_remain_review_required(self):
        for unit in ("mW", "MW", "mWh", "MWh"):
            report = f"Measured power was 12{unit}. [S1]\n"
            result = verify_report(report, {"S1": f"Measured power was 12{unit}."}, [],
                                   {"selected_count": 0, "checked_count": 0}, report, [], [])
            self.assertTrue(any(issue["kind"] == "numeric_evidence_unclear" for issue in result["issues"]))

    def test_unsupported_milli_or_mega_watt_units_remain_review_required(self):
        report = "Measured power was 12 mW. [S1]\n"
        result = verify_report(report, {"S1": "Measured power was 12 MW."}, [],
                               {"selected_count": 0, "checked_count": 0}, report, [], [])
        self.assertTrue(any(issue["kind"] == "numeric_evidence_unclear" for issue in result["issues"]))

    def test_quote_normalization_accepts_unicode_apostrophe_and_space_variants(self):
        quote = "The model’s result is source backed"
        report = f'“{quote}” [S1]\n'
        source = "The model's   result is source backed"
        result = verify_report(report, {"S1": source}, [], {"selected_count": 0, "checked_count": 0}, report, [], [])
        self.assertFalse(any(issue["kind"].startswith("direct_quote") for issue in result["issues"]))

    def test_words_containing_no_or_fall_are_not_treated_as_negation_or_direction(self):
        report = "Notebook fallback latency was 2 seconds. [S1]\n"
        source = "Notebook fallback latency was 2000 ms."
        result = verify_report(report, {"S1": source}, [], {"selected_count": 0, "checked_count": 0}, report, [], [])
        self.assertFalse(any(issue["kind"].startswith("numeric_") for issue in result["issues"]))

    def test_unrelated_attribution_negation_does_not_conflict_with_quantity(self):
        report = "Registry latency was 2 seconds. [S1]\n"
        source = "The registry, not the vendor, published the result. Registry latency was 2000 ms."
        result = verify_report(report, {"S1": source}, [], {"selected_count": 0, "checked_count": 0}, report, [], [])
        self.assertFalse(any(issue["kind"] == "numeric_context_unclear" for issue in result["issues"]))

    def test_korean_claim_and_english_equivalent_quantity_do_not_fail_lexical_context(self):
        report = "지연 시간은 2초다. [S1]\n"
        source = "Latency is 2000 ms."
        result = verify_report(report, {"S1": source}, [], {"selected_count": 0, "checked_count": 0}, report, [], [])
        self.assertFalse(any(issue["kind"].startswith("numeric_") for issue in result["issues"]))

    def test_negation_bound_to_the_quantity_still_requires_review(self):
        report = "Latency was 2 seconds. [S1]\n"
        source = "Latency was not 2000 ms."
        result = verify_report(report, {"S1": source}, [], {"selected_count": 0, "checked_count": 0}, report, [], [])
        self.assertTrue(any(issue["kind"] == "numeric_context_unclear" for issue in result["issues"]))
