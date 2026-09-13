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
