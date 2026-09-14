import copy
import unittest
from pathlib import Path

from hprc.efficiency_study import build_plan, validate_results


FIXTURE = Path(__file__).parent / "fixtures" / "realistic_inputs.json"


class EfficiencyStudyTests(unittest.TestCase):
    def plan(self):
        return build_plan(FIXTURE, "a" * 40)

    def records(self, plan):
        rows = []
        for run in plan["runs"]:
            rows.append({
                "run_id": run["run_id"], "case_id": run["case_id"], "arm": run["arm"],
                "input_hash": run["input_hash"], "runtime_metadata": copy.deepcopy(run["runtime_metadata"]),
                "input_tokens": 80 if run["arm"] == "baseline" else 64,
                "cached_input_tokens": 0, "output_tokens": 20 if run["arm"] == "baseline" else 16,
                "reported_total_tokens": 100 if run["arm"] == "baseline" else 80,
                "unknowncalls": 0, "retry_attempt_count": 0, "failure_attempt_count": 0,
                "attempt_count": 7, "observed_control_errors": [],
                "externally_judged_quality": True, "status": "ok", "backend": "codex",
                "report_sha256": "r-" + run["run_id"], "adjudication_report_sha256": "r-" + run["run_id"],
                "adjudication_report_bound": True,
            })
        return rows

    def test_plan_is_counterbalanced_packet_only_and_bounded_without_hard_cap_claim(self):
        plan = self.plan()
        self.assertEqual(8, plan["planned_run_count"])
        self.assertEqual(["real-ko-table", "real-en-boundary"], list(plan["cases"]))
        self.assertEqual(500_000, plan["policy"]["per_run_total_token_stop"])
        self.assertEqual(4_000_000, plan["policy"]["study_total_token_stop"])
        self.assertFalse(plan["policy"]["total_stop_is_hard_cap"])
        self.assertFalse(plan["policy"]["quality"]["automatic_calls"])
        for case in plan["cases"].values():
            baseline, packet = case["arms"]["baseline"]["config_snapshot"], case["arms"]["packet"]["config_snapshot"]
            self.assertFalse(baseline["efficiency"]["packet_inputs"])
            self.assertTrue(packet["efficiency"]["packet_inputs"])
            self.assertFalse(packet["efficiency"]["evidence_selection"])
            self.assertFalse(packet["efficiency"]["reuse_analysis"])
            self.assertEqual("standard", packet["efficiency"]["strategy"])
            self.assertEqual(700, packet["light"]["target_words"])
        self.assertTrue(plan["fixture_sha256"])
        self.assertTrue(plan["plan_sha256"])

    def test_one_repeat_plan_has_four_runs_and_counterbalances_across_cases(self):
        plan = build_plan(FIXTURE, "b" * 40, repetitions=1)
        self.assertEqual(4, plan["planned_run_count"])
        self.assertEqual(2_000_000, plan["policy"]["study_total_token_stop"])
        self.assertEqual(["real-ko-table:baseline_then_packet", "real-en-boundary:packet_then_baseline"], plan["policy"]["counterbalance"])
        result = validate_results(plan, self.records(plan))
        self.assertFalse(result["report_claim_permitted"])
        self.assertTrue(result["automatic_eligibility"])

    def test_unapproved_repeat_count_is_rejected(self):
        with self.assertRaises(ValueError):
            build_plan(FIXTURE, "c" * 40, repetitions=3)

    def test_complete_external_quality_pairs_remain_manual_review_only(self):
        result = validate_results(self.plan(), self.records(self.plan()))
        self.assertFalse(result["report_claim_permitted"])
        self.assertTrue(result["automatic_eligibility"])
        self.assertTrue(result["manual_review_required"])
        self.assertTrue(result["all_pairs_qualify"])
        self.assertEqual([-20.0] * 4, [pair["paired_token_percent"] for pair in result["pairs"]])
        self.assertFalse(result["general_performance_claim_permitted"])

    def test_retry_failure_or_inconsistent_token_accounting_blocks_automatic_eligibility(self):
        plan = self.plan(); rows = self.records(plan)
        rows[0]["retry_attempt_count"] = 1
        rows[1]["failure_attempt_count"] = 1
        rows[2]["cached_input_tokens"] = rows[2]["input_tokens"] + 1
        rows[3]["reported_total_tokens"] = 1
        result = validate_results(plan, rows)
        self.assertFalse(result["automatic_eligibility"])
        self.assertIn("retry_policy_violation", result["control_errors"][rows[0]["run_id"]])
        self.assertIn("failure_policy_violation", result["control_errors"][rows[1]["run_id"]])
        self.assertIn("cached_input_exceeds_input", result["control_errors"][rows[2]["run_id"]])
        self.assertIn("reported_total_tokens_mismatch", result["control_errors"][rows[3]["run_id"]])

    def test_attempt_limit_and_observed_control_error_are_required_records(self):
        plan = self.plan(); rows = self.records(plan)
        rows[0]["attempt_count"] = 9
        rows[1].pop("observed_control_errors")
        rows[2]["observed_control_errors"] = ["runtime hash changed"]
        result = validate_results(plan, rows)
        self.assertEqual(58, result["totals"]["attempt_count"])
        self.assertIn("attempt_count", result["control_errors"][rows[0]["run_id"]])
        self.assertIn("observed_control_errors", result["control_errors"][rows[1]["run_id"]])
        self.assertIn("observed_control_errors", result["control_errors"][rows[2]["run_id"]])

    def test_missing_or_duplicate_record_is_not_silently_dropped(self):
        plan = self.plan(); rows = self.records(plan)
        missing = validate_results(plan, rows[:-1])
        self.assertEqual(1, len(missing["missing_run_ids"]))
        self.assertFalse(missing["report_claim_permitted"])
        with self.assertRaises(ValueError):
            validate_results(plan, rows + [copy.deepcopy(rows[0])])

    def test_unknown_usage_or_unjudged_quality_blocks_percent_claim_and_autopass(self):
        plan = self.plan(); rows = self.records(plan)
        rows[0]["unknowncalls"] = 1
        rows[1].pop("externally_judged_quality")
        result = validate_results(plan, rows)
        self.assertTrue(result["unknown_usage"])
        self.assertIsNone(result["pairs"][0]["paired_token_percent"])
        self.assertFalse(result["report_claim_permitted"])

    def test_unbound_positive_quality_is_unknown_and_status_or_counts_cannot_default_to_success(self):
        plan = self.plan(); rows = self.records(plan)
        rows[0].pop("adjudication_report_bound")
        rows[2].pop("status")
        rows[3]["unknowncalls"] = -1
        result = validate_results(plan, rows)
        self.assertIsNone(result["pairs"][0]["quality_preserved"])
        self.assertIn(rows[3]["run_id"], result["control_errors"])
        self.assertFalse(result["report_claim_permitted"])

    def test_control_mismatch_and_mock_backend_block_performance_claim(self):
        plan = self.plan(); rows = self.records(plan)
        rows[0]["runtime_metadata"]["config_snapshot"]["light"]["target_words"] = 701
        rows[0]["backend"] = "mock"
        result = validate_results(plan, rows)
        self.assertIn(rows[0]["run_id"], result["control_errors"])
        self.assertFalse(result["report_claim_permitted"])

    def test_changed_plan_or_policy_hash_is_rejected(self):
        plan = self.plan(); rows = self.records(plan)
        plan["policy"]["max_calls_per_run"] = 7
        with self.assertRaises(ValueError):
            validate_results(plan, rows)

    def test_quality_failure_propagates_to_pair(self):
        plan = self.plan(); rows = self.records(plan)
        rows[0]["externally_judged_quality"] = False
        result = validate_results(plan, rows)
        self.assertFalse(result["pairs"][0]["quality_preserved"])
        self.assertFalse(result["all_pairs_qualify"])


if __name__ == "__main__":
    unittest.main()
