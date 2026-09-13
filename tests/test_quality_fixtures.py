"""B3 합성 품질 자료: 표본 범위와 출처 게이트가 서로의 역할을 침범하지 않는지 검증한다."""
import json
import unittest
from pathlib import Path

from hprc import gates
from hprc.citation_sampling import enrich_checks, render_summary, select_samples


FIXTURE = Path(__file__).parent / "fixtures" / "quality_cases.json"


def cases():
    return {case["id"]: case for case in json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]}


class QualityFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = cases()

    def test_fixture_inventory_covers_the_quality_boundaries(self):
        tags = {tag for case in self.cases.values() for tag in case["tags"]}
        self.assertTrue({"korean", "english", "mixed-language", "table", "list", "truncated-evidence",
                         "partial-support", "judgment", "internal-citation", "source-gate"} <= tags)

    def test_korean_mixed_structures_are_sampled_but_judgment_and_internal_only_refs_are_not(self):
        case = self.cases["ko_mixed_table_list_internal_and_judgment"]
        expected = case["expected"]
        cleaned, fixed = gates.clean_internal_cites(case["report"], case["lang"])
        selected = select_samples(cleaned, case["limit"], case["judgment_marker"])

        self.assertEqual(expected["clean_fixed"], fixed)
        self.assertEqual(expected["eligible_count"], selected["eligible_count"])
        self.assertEqual(expected["excluded_judgment_count"], selected["excluded_judgment_count"])
        self.assertEqual(expected["selected_lines"], [sample["line"] for sample in selected["samples"]])
        self.assertEqual(expected["selected_cites"], [sample["cites"] for sample in selected["samples"]])
        self.assertFalse(any("(판단)" in sample["sentence"] for sample in selected["samples"]))
        for text in expected["contains_after_clean"]:
            self.assertIn(text, cleaned)
        for text in expected["absent_after_clean"]:
            self.assertNotIn(text, cleaned)
        problems = gates.report_lint(cleaned, "혼합 문서의 근거는?", set(case["known"]), case["lang"])
        self.assertFalse(any(problem.split(":", 1)[0] in expected["lint_absent"] for problem in problems), problems)

    def test_truncated_and_partial_support_are_both_visible_as_unsupported(self):
        case = self.cases["en_truncated_and_partial_support"]
        expected = case["expected"]
        selected = select_samples(case["report"], case["limit"], case["judgment_marker"])
        self.assertEqual(expected["eligible_count"], selected["eligible_count"])
        self.assertEqual(expected["excluded_judgment_count"], selected["excluded_judgment_count"])
        self.assertEqual(expected["selected_lines"], [sample["line"] for sample in selected["samples"]])

        checks = enrich_checks(case["returned_checks"], selected)
        unsupported = [check for check in checks
                       if check.get("supported") is False or check.get("verdict") == "unsupported"]
        self.assertEqual(expected["unsupported_count"], len(unsupported))
        self.assertEqual(4, selected["checked_count"])
        summary = render_summary(checks, selected, case["lang"])
        for text in expected["summary_contains"]:
            self.assertIn(text, summary)
        self.assertNotIn("No unsupported sentence among returned judgments", summary)

    def test_sampler_does_not_make_an_unknown_source_valid(self):
        case = self.cases["unknown_source_must_fail_gate"]
        expected = case["expected"]
        selected = select_samples(case["report"], case["limit"], case["judgment_marker"])
        sampled_cites = {cite for sample in selected["samples"] for cite in sample["cites"]}
        self.assertIn(expected["selected_cites_include"], sampled_cites)
        problems = gates.report_lint(case["report"], "출처 식별자는 유효한가?", set(case["known"]), case["lang"])
        self.assertIn(expected["lint_contains"], problems)
        self.assertNotIn("no_citations", problems)


if __name__ == "__main__":
    unittest.main()
