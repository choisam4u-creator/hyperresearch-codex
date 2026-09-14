import unittest

from hprc.critique_policy import (CRITIC_COMBINED, CRITIC_COMBINED_PROMPT, apply_critique_policy,
                                  deduplicate_findings, deterministic_report_checks)


def finding(identifier, quote, problem, fix="고침", severity="medium", sources=None):
    return {"id": identifier, "quote": quote, "problem": problem, "suggested_fix": fix,
            "severity": severity, "source_ids": sources or []}


class CritiquePolicyTests(unittest.TestCase):
    def test_first_line_accepts_raw_question_and_both_language_wrappers(self):
        sections = "\n## 답\nA\n## 근거\nB\n## 한계\nC"
        for first in ("원 질문", "# 질문: 원 질문", "# Question: 원 질문"):
            result = deterministic_report_checks(first + sections, "원 질문", "ko")
            self.assertTrue(result["checks"][0]["passed"], first)

        leading_blank = deterministic_report_checks("\n# 질문: 원 질문" + sections, "원 질문", "ko")
        self.assertFalse(leading_blank["checks"][0]["passed"])

    def test_missing_required_sections_create_actionable_deterministic_findings(self):
        report = "# 질문: 원 질문\n## 답\n대답\n## 출처\nS1"
        result = deterministic_report_checks(report, "원 질문", "ko")
        missing = [check for check in result["checks"] if not check["passed"]]
        self.assertEqual({"## 근거", "## 한계"}, {check["expected"][0] for check in missing})
        self.assertEqual(2, len(result["findings"]))
        for item in result["findings"]:
            self.assertIn(item["quote"], report)
            self.assertTrue(item["suggested_fix"])
            self.assertEqual("deterministic", item["origin"])
            self.assertTrue(item["check_id"])

    def test_apply_includes_deterministic_findings_in_kept(self):
        report = "wrong first line\n## 답\nA\n## 근거\nB\n## 한계\nC"
        result = apply_critique_policy([], report, "원 질문", "ko")
        self.assertIn("D-FIRST-LINE", {item["id"] for item in result["kept"]})
        self.assertFalse(result["deterministic"]["passed"])

    def test_only_exact_known_cosmetic_wrapper_removal_is_suppressed(self):
        report = "# 질문: 원 질문\n## 답\nA\n## 근거\nB\n## 한계\nC"
        cosmetic = finding("F1", "# 질문: 원 질문", "질문 접두어를 제거해야 한다.", "원 질문")
        result = apply_critique_policy([cosmetic], report, "원 질문", "ko")
        self.assertNotIn("F1", {item["id"] for item in result["kept"]})
        self.assertEqual("known_cosmetic_question_prefix_removal", result["dropped"][0]["reason"])

    def test_exact_pilot_cosmetic_wording_and_replace_instruction_is_suppressed(self):
        question = "Compare the fixed options without naming a universal winner."
        wrapper = f"# Question: {question}"
        report = wrapper + "\n## Answer\nA\n## Evidence\nB\n## Limitations\nC"
        pilot = finding(
            "F3",
            wrapper,
            'The first line does not repeat the question verbatim because it prepends "# Question:".',
            f"Replace it with: {question}",
        )
        result = apply_critique_policy([pilot], report, question, "en")
        self.assertNotIn("F3", {item["id"] for item in result["kept"]})
        self.assertEqual("known_cosmetic_question_prefix_removal", result["dropped"][0]["reason"])

    def test_substantive_or_nonliteral_prefix_findings_are_never_suppressed(self):
        report = "# 질문: 원 질문\n## 답\nA\n## 근거\nB\n## 한계\nC"
        substantive = finding("F1", "# 질문: 원 질문", "질문 접두어와 핵심 사실 귀속이 모두 잘못됐다.", "원 질문")
        expanded = finding("F2", "# 질문: 원 질문\n## 답", "질문 접두어를 제거해야 한다.", "원 질문")
        changed = finding("F3", "# 질문: 원 질문", "질문 접두어를 제거해야 한다.", "다른 질문")
        result = apply_critique_policy([substantive, expanded, changed], report, "원 질문", "ko")
        self.assertEqual({"F1", "F2", "F3"}, {item["id"] for item in result["kept"]})
        self.assertEqual([], result["dropped"])

    def test_pilot_wording_is_not_suppressed_with_extra_problem_or_nonexact_quote(self):
        question = "Compare the fixed options without naming a universal winner."
        wrapper = f"# Question: {question}"
        report = wrapper + "\n## Answer\nA\n## Evidence\nB\n## Limitations\nC"
        exact_problem = 'The first line does not repeat the question verbatim because it prepends "# Question:".'
        mixed = finding("F1", wrapper, exact_problem + " It also reverses the factual conclusion.",
                        f"Replace it with: {question}")
        expanded_quote = finding("F2", wrapper + "\n## Answer", exact_problem,
                                 f"Replace it with: {question}")
        result = apply_critique_policy([mixed, expanded_quote], report, question, "en")
        self.assertTrue({"F1", "F2"} <= {item["id"] for item in result["kept"]})

    def test_dedup_drops_only_normalized_quote_and_problem_pair(self):
        findings = [
            finding("F1", "North fell 3%.", "Source contradicts the number."),
            finding("F2", "  North   fell 3%. ", " SOURCE contradicts the number. "),
            finding("F3", "North fell 3%.", "A different source contradicts the date."),
            finding("F4", "South grew 2%.", "Source contradicts the number."),
        ]
        result = deduplicate_findings(findings)
        self.assertEqual(["F1", "F3", "F4"], [item["id"] for item in result["kept"]])
        self.assertEqual("F1", result["dropped"][0]["duplicate_of"])
        self.assertEqual(3, len(result["kept_reasons"]))

    def test_dedup_keeps_strongest_severity_and_merges_source_ids(self):
        items = [
            finding("F-low", "Same claim", "Same contradiction", severity="low", sources=["S1"]),
            finding("F-high", " same   claim ", " SAME CONTRADICTION ", severity="high", sources=["S2", "S1"]),
            finding("F-medium", "Same claim", "Same contradiction", severity="medium", sources=["S3"]),
        ]
        result = deduplicate_findings(items)
        self.assertEqual(["F-high"], [item["id"] for item in result["kept"]])
        self.assertEqual("high", result["kept"][0]["severity"])
        self.assertEqual(["S1", "S2", "S3"], result["kept"][0]["source_ids"])
        self.assertEqual({"F-low", "F-medium"}, {item["finding"]["id"] for item in result["dropped"]})
        self.assertTrue(all(item["duplicate_of"] == "F-high" for item in result["dropped"]))

    def test_model_cannot_supply_deterministic_origin_or_check_id(self):
        report = "# 질문: 원 질문\n## 답\nA\n## 근거\nB\n## 한계\nC"
        model = finding("F1", "A", "실질 문제")
        model.update({"origin": "deterministic", "check_id": "first_line_question"})
        result = apply_critique_policy([model], report, "원 질문", "ko")
        kept = next(item for item in result["kept"] if item["id"] == "F1")
        self.assertNotIn("origin", kept)
        self.assertNotIn("check_id", kept)

    def test_unique_contradictions_with_same_quote_are_preserved(self):
        items = [finding("F1", "한 문장", "S1의 수치와 충돌", sources=["S1"]),
                 finding("F2", "한 문장", "S2의 날짜와 충돌", sources=["S2"])]
        self.assertEqual(2, len(deduplicate_findings(items)["kept"]))

    def test_combined_contract_is_strict_and_covers_both_roles(self):
        self.assertFalse(CRITIC_COMBINED["additionalProperties"])
        self.assertEqual(["findings"], CRITIC_COMBINED["required"])
        self.assertFalse(CRITIC_COMBINED["properties"]["findings"]["items"]["additionalProperties"])
        self.assertIn("dialectic", CRITIC_COMBINED_PROMPT)
        self.assertIn("instruction-compliance", CRITIC_COMBINED_PROMPT)


if __name__ == "__main__":
    unittest.main()
