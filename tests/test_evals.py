"""evals 품질 평가 기반: 점수기가 감점 사례를 실제로 잡는지, 고정 case 전체가 실행되는지 확인한다."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evals import run, score  # noqa: E402

SOURCES = {"S1": {"text": "The pilot covered 12 buildings. Peak demand fell by 18.4 kW at the library.", "cluster": "S1"},
           "S2": {"text": "The pilot covered 12 buildings. Peak demand fell by 18.4 kW at the library.", "cluster": "S1"}}
GOOD = """# Question: q?

## Answer
The pilot covered 12 buildings [S1].

## Evidence
- Peak demand fell by 18.4 kW at the library [S1].

## Counter-evidence and limits
- Only one season was measured (judgment)

## Next actions
- Measure again (judgment)

## Sources
- [S1] memo
"""


class ScoreTests(unittest.TestCase):
    def test_clean_report_scores_full(self):
        result = score.score(GOOD, "en", "q?", SOURCES)
        for metric in score.METRICS:
            self.assertEqual(100.0, result[metric], metric)

    def test_each_flaw_lowers_its_metric(self):
        bad = (GOOD.replace("fell by 18.4 kW", "fell by 25 kW")
               .replace("[S1].\n\n## Evidence", "[S9].\n\n## Evidence")
               .replace("- Only one season was measured (judgment)", "- Only one season was measured.")
               .replace("- [S1] memo", "- [S1] memo\n- [S1] memo"))
        result = score.score(bad, "en", "q?", SOURCES)
        self.assertLess(result["citation_validity"], 100)
        self.assertLess(result["claim_source_match"], 100)
        self.assertLess(result["unmarked_unverified"], 100)
        self.assertLess(result["duplicate_sources"], 100)

    def test_same_cluster_cocitation_is_a_duplicate(self):
        result = score.score(GOOD.replace("12 buildings [S1]", "12 buildings [S1][S2]"), "en", "q?", SOURCES)
        self.assertLess(result["duplicate_sources"], 100)

    def test_empty_section_does_not_count_as_structure(self):
        result = score.score(GOOD.replace("- Only one season was measured (judgment)\n", ""), "en", "q?", SOURCES)
        self.assertLess(result["structure"], 100)

    def test_failed_run_scores_zero(self):
        self.assertTrue(all(score.score(None, "ko", "q", {})[m] == 0 for m in score.METRICS))


class HarnessTests(unittest.TestCase):
    def test_every_case_runs_through_the_pipeline(self):
        os.environ["HPR_BACKEND"] = "mock"
        with tempfile.TemporaryDirectory() as tmp:
            for case in run.load_cases():
                result = run.run_case(case, Path(tmp))
                self.assertIn("writer", result["calls"], case["id"])

    def test_clean_control_case_stays_perfect(self):
        os.environ["HPR_BACKEND"] = "mock"
        with tempfile.TemporaryDirectory() as tmp:
            result = run.run_case(run.load_cases("en-solar-rebate")[0], Path(tmp))
        for metric in score.METRICS:
            self.assertEqual(100.0, result[metric], metric)


if __name__ == "__main__":
    unittest.main()
