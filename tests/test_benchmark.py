"""Phase 8 합성 기준판: 실제 모델 호출·문장 의미 자동 판정 없이 계약만 검증한다."""
import json
import unittest
from pathlib import Path

from hprc.evaluation import (compare, evaluate, frozen_input_export, load_benchmark, report_sha256,
                             materialize_mutation_cases, runtime_metadata_from_manifest, summarize_reports)


FIXTURES = Path(__file__).parent / "fixtures"


class BenchmarkFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs, cls.answers = load_benchmark(FIXTURES / "benchmark_inputs.json", FIXTURES / "benchmark_answers.json")

    def test_frozen_inputs_have_24_balanced_cases_and_no_answers(self):
        cases = self.inputs["cases"]
        self.assertEqual(24, len(cases))
        self.assertEqual({"fact_check", "conditional_comparison", "date_version_change", "number_unit",
                          "conflicting_evidence", "insufficient_or_adversarial"}, {case["category"] for case in cases})
        self.assertEqual({category: 4 for category in {case["category"] for case in cases}},
                         {category: sum(case["category"] == category for case in cases) for category in {case["category"] for case in cases}})
        self.assertEqual(12, sum(case["lang"] == "ko" for case in cases))
        self.assertEqual(12, sum(case["lang"] == "en" for case in cases))
        self.assertEqual(16, sum(case["split"] == "dev" for case in cases))
        self.assertEqual(8, sum(case["split"] == "holdout" for case in cases))
        text = json.dumps(frozen_input_export(json.loads((FIXTURES / "benchmark_inputs.json").read_text(encoding="utf-8"))), ensure_ascii=False)
        self.assertNotIn("accepted_verdicts", text)
        self.assertNotIn("reference_report", text)

    def test_mutation_inventory_is_100_normal_and_100_diverse_errors(self):
        mutation_inputs = json.loads((FIXTURES / "benchmark_mutation_inputs.json").read_text(encoding="utf-8"))
        mutation_answers = json.loads((FIXTURES / "benchmark_mutation_answers.json").read_text(encoding="utf-8"))
        cases, answers = materialize_mutation_cases(mutation_inputs, mutation_answers)
        self.assertEqual(200, len(cases))
        self.assertEqual(100, sum(case["group"] == "normal" for case in cases))
        self.assertEqual(100, sum(case["group"] == "error" for case in cases))
        self.assertEqual(10, len({case["semantic_tag"] for case in cases if case["group"] == "normal"}))
        self.assertEqual(10, len({case["semantic_tag"] for case in cases if case["group"] == "error"}))
        self.assertEqual(10, len({case["source"] for case in cases if case["semantic_tag"] == "negation_flip"}))
        self.assertEqual({"contradicted"}, {answer["expected_verdict"] for case_id, answer in answers.items() if case_id.startswith("error-")})

    def test_explicit_adjudications_keep_missing_and_unknown_as_unknown(self):
        case = self.inputs["cases"][0]
        answer = self.answers[case["id"]]
        report = "unrelated prose"
        result = evaluate(report, case,
                          [{"attempt": 1, "status": "error", "usage_known": True, "usage": {"input_tokens": 7, "cached_input_tokens": 2, "output_tokens": 1}},
                           {"attempt": 2, "status": "ok", "usage_known": False}], 2.0, {"status": "passed", "issues": []},
                          benchmark_answer=answer,
                          submitted_adjudications=[{"item_id": "sandbox", "verdict": "supported", "evidence_ids": ["S1"]},
                                                   {"item_id": "release-date", "verdict": "unknown", "evidence_ids": []}],
                          adjudication_report_sha256=report_sha256(report))
        adjudication = result["adjudication"]
        self.assertEqual((2, 2, 0), (adjudication["required_item_count"], adjudication["submitted_required_count"], adjudication["missing_required_count"]))
        self.assertEqual(1, adjudication["unknown_required_count"])
        self.assertEqual("unknown", adjudication["items"][1]["verdict"])
        self.assertFalse(result["quality_qualified"])
        self.assertEqual((2, 1, 1), (result["attempt_count"], result["retry_attempt_count"], result["failure_attempt_count"]))
        self.assertEqual(1, result["unknowncalls"])

    def test_adjudication_scores_submitted_verdicts_not_report_assertion_text(self):
        case = self.inputs["cases"][0]
        answer = self.answers[case["id"]]
        # 이 문장은 S1의 부정을 말하지만 evaluator는 문장 의미를 자동 판정하지 않는다.
        result = evaluate("Atlas API is writable and the release happened in 2020.", case, [], 0,
                          {"status": "passed", "issues": []}, benchmark_answer=answer,
                          submitted_adjudications=[{"item_id": "sandbox", "verdict": "supported", "evidence_ids": ["S1"]},
                                                   {"item_id": "release-date", "verdict": "supported", "evidence_ids": ["S2"]}])
        self.assertEqual("not_performed", result["adjudication"]["semantic_validation"])
        self.assertEqual(2, result["adjudication"]["matched_required_count"])
        wrong_labels = [{"item_id": "sandbox", "verdict": "contradicted", "evidence_ids": ["S1"]},
                        {"item_id": "release-date", "verdict": "contradicted", "evidence_ids": ["S2"]}]
        self.assertEqual(2, evaluate("", case, [], 0, {"status": "passed", "issues": []},
                                     benchmark_answer=answer, submitted_adjudications=wrong_labels)["adjudication"]["incorrect_required_count"])

    def test_quality_qualified_cost_includes_failed_attempts_and_unqualified_runs(self):
        case = self.inputs["cases"][0]
        answer = self.answers[case["id"]]
        submitted = [{"item_id": item["item_id"], "verdict": "supported", "evidence_ids": item["evidence"]["all_of"]} for item in answer["items"]]
        good = evaluate("", case, [{"attempt": 1, "status": "error", "usage": {"input_tokens": 10, "output_tokens": 2}},
                                   {"attempt": 2, "status": "ok", "usage": {"input_tokens": 5, "output_tokens": 1}}], 1, {"status": "passed", "issues": []},
                        benchmark_answer=answer, submitted_adjudications=submitted, adjudication_report_sha256=report_sha256(""))
        bad = evaluate("", case, [{"attempt": 1, "status": "ok", "usage": {"input_tokens": 9, "output_tokens": 3}}], 1,
                       {"status": "review_required", "issues": []}, benchmark_answer=answer, submitted_adjudications=submitted, adjudication_report_sha256=report_sha256(""))
        summary = summarize_reports([good, bad])
        self.assertTrue(good["quality_qualified"])
        self.assertFalse(bad["quality_qualified"])
        self.assertEqual(1, summary["quality_qualified_report_count"])
        self.assertEqual(30, summary["reported_total_tokens"])
        self.assertEqual(30, summary["total_tokens_per_quality_qualified_report"])

    def test_adjudication_envelope_requires_matching_report_hash_and_unique_known_items(self):
        case = self.inputs["cases"][0]
        answer = self.answers[case["id"]]
        with self.assertRaises(ValueError):
            evaluate("report", case, [], 0, {"status": "passed", "issues": []}, benchmark_answer=answer,
                     submitted_adjudications=[], adjudication_report_sha256="wrong")
        for entries in ([{"item_id": "sandbox", "verdict": "supported", "evidence_ids": ["S1"]},
                         {"item_id": "sandbox", "verdict": "supported", "evidence_ids": ["S1"]}],
                        [{"item_id": "not-registered", "verdict": "supported", "evidence_ids": ["S1"]}]):
            with self.assertRaises(ValueError):
                evaluate("report", case, [], 0, {"status": "passed", "issues": []}, benchmark_answer=answer,
                         submitted_adjudications=entries, adjudication_report_sha256=report_sha256("report"))

    def test_unbound_or_unknown_cost_never_claims_complete_token_per_report(self):
        case = self.inputs["cases"][0]
        answer = self.answers[case["id"]]
        entries = [{"item_id": item["item_id"], "verdict": "supported", "evidence_ids": item["evidence"]["all_of"]} for item in answer["items"]]
        unbound = evaluate("", case, [], 0, {"status": "passed", "issues": []}, benchmark_answer=answer, submitted_adjudications=entries)
        unknown_cost = evaluate("", case, [{"usage_known": False}], 0, {"status": "passed", "issues": []}, benchmark_answer=answer,
                                submitted_adjudications=entries, adjudication_report_sha256=report_sha256(""))
        self.assertIsNone(unbound["quality_qualified"])
        self.assertTrue(unknown_cost["quality_qualified"])
        self.assertIsNone(unknown_cost["total_tokens_per_quality_qualified_report"])
        self.assertEqual(0, unknown_cost["known_total_tokens_per_quality_qualified_report"])

    def test_unknown_acknowledgement_with_required_evidence_needs_that_evidence(self):
        case = next(case for case in self.inputs["cases"] if case["id"] == "fact-en-02")
        answer = self.answers[case["id"]]
        result = evaluate("", case, [], 0, {"status": "passed", "issues": []}, benchmark_answer=answer,
                          submitted_adjudications=[{"item_id": "checks", "verdict": "supported", "evidence_ids": ["S1"]},
                                                   {"item_id": "satisfaction", "verdict": "unknown", "evidence_ids": []}],
                          adjudication_report_sha256=report_sha256(""))
        self.assertEqual("unknown", result["adjudication"]["items"][1]["outcome"])
        self.assertFalse(result["quality_qualified"])

    def test_compare_separates_fixed_model_code_and_routing_modes(self):
        case = self.inputs["cases"][0]
        runtime = {"benchmark_version": "phase8-synthetic-v1", "frozen_at": "2026-09-14T00:00:00Z", "code_revision": "a",
                   "frozen_input_hash": "frozen", "as_of": "2026-09-01", "config_hash": "cfg",
                   "config_snapshot": {"models": {"writer": {"model": "fixed"}}, "light": {"target_words": 900}},
                   "non_model_config_snapshot": {"light": {"target_words": 900}}, "runtime_consistent": True,
                   "prompt_hashes": {"writer": "p"}, "role_assignments": {"writer": {"model": "fixed", "effort": "low"}}}
        left = evaluate("", case, [], 1, None, runtime_metadata=runtime)
        right = evaluate("", case, [], 2, None, runtime_metadata={**runtime, "code_revision": "b"})
        self.assertEqual("code_only", compare(left, right, mode="code_only")["comparison_mode"])
        routed = evaluate("", case, [], 2, None, runtime_metadata={**runtime, "role_assignments": {"writer": {"model": "routed", "effort": "low"}}})
        change = compare(left, routed, mode="model_routing")["routing_change"]
        self.assertIn("writer", change)
        with self.assertRaises(ValueError):
            compare(left, routed, mode="code_only")
        with self.assertRaises(ValueError):
            compare(evaluate("", case, [], 1, None), evaluate("", case, [], 2, None), mode="code_only")
        changed_words = evaluate("", case, [], 2, None, runtime_metadata={**runtime, "config_hash": "cfg-2",
                                  "config_snapshot": {"models": {"writer": {"model": "fixed"}}, "light": {"target_words": 100}},
                                  "non_model_config_snapshot": {"light": {"target_words": 100}}})
        with self.assertRaises(ValueError):
            compare(left, changed_words, mode="code_only")

    def test_runtime_metadata_preserves_pipeline_snapshot_and_hashes(self):
        runtime = runtime_metadata_from_manifest(
            {"as_of": "2026-09-01", "config_snapshot": {"tier": "light"},
             "runtime": {"config_hash": "cfg", "models": {"writer": {"model": "fixed"}},
                         "prompt_hash": {"writer": "prompt"}, "code_hash": "code"},
             "usage": [{"runtime": {"config_hash": "cfg", "prompt_hash": {"writer": "prompt"}, "code_hash": "code"}}]}, self.inputs)
        self.assertEqual("code", runtime["code_revision"])
        self.assertEqual({"writer": "prompt"}, runtime["prompt_hashes"])
        self.assertEqual({"writer": {"model": "fixed"}}, runtime["role_assignments"])
        self.assertEqual("2026-09-01", runtime["as_of"])
        self.assertTrue(runtime["frozen_input_hash"])
        self.assertTrue(runtime["runtime_consistent"])

    def test_runtime_metadata_uses_effective_config_and_marks_mixed_or_missing_attempt_runtime_unknown(self):
        current = {"config_hash": "after", "models": {"writer": {"model": "fixed"}}, "prompt_hash": "p", "code_hash": "c"}
        base = {"as_of": "2026-09-01", "config_snapshot": {"budget": {"max_input_tokens": 10}},
                "effective_config_snapshot": {"budget": {"max_input_tokens": 20}}, "runtime": current}
        mixed = runtime_metadata_from_manifest({**base, "usage": [{"runtime": {"config_hash": "before", "prompt_hash": "p", "code_hash": "c"}}]}, self.inputs)
        missing = runtime_metadata_from_manifest({**base, "usage": [{"step": "writer"}]}, self.inputs)
        self.assertEqual({"budget": {"max_input_tokens": 20}}, mixed["config_snapshot"])
        self.assertFalse(mixed["runtime_consistent"])
        self.assertIsNone(missing["runtime_consistent"])
        case = self.inputs["cases"][0]
        with self.assertRaises(ValueError):
            compare(evaluate("", case, [], 0, None, runtime_metadata=mixed),
                    evaluate("", case, [], 0, None, runtime_metadata=mixed), mode="code_only")

    def test_routing_allows_only_model_difference_in_real_manifest_shape(self):
        baseline_snapshot = {"default_model": "fixed", "models": {"writer": {"model": "fixed", "effort": "low"}},
                             "routing": {"enabled": True, "escalation_model": "fixed"}, "light": {"target_words": 900}}
        candidate_snapshot = {"default_model": "routed", "models": {"writer": {"model": "routed", "effort": "low"}},
                              "routing": {"enabled": True, "escalation_model": "routed"}, "light": {"target_words": 900}}
        frozen = {"benchmark_version": "phase8-synthetic-v1", "frozen_at": "2026-09-14T00:00:00Z", "cases": []}
        left_runtime = runtime_metadata_from_manifest({"as_of": "2026-09-01", "config_snapshot": baseline_snapshot,
                                                       "runtime": {"config_hash": "left-cfg", "models": baseline_snapshot["models"], "prompt_hash": "p", "code_hash": "c"},
                                                       "usage": [{"runtime": {"config_hash": "left-cfg", "prompt_hash": "p", "code_hash": "c"}}]}, frozen)
        right_runtime = runtime_metadata_from_manifest({"as_of": "2026-09-01", "config_snapshot": candidate_snapshot,
                                                        "runtime": {"config_hash": "right-cfg", "models": candidate_snapshot["models"], "prompt_hash": "p", "code_hash": "c"},
                                                        "usage": [{"runtime": {"config_hash": "right-cfg", "prompt_hash": "p", "code_hash": "c"}}]}, frozen)
        case = self.inputs["cases"][0]
        left, right = evaluate("", case, [], 0, None, runtime_metadata=left_runtime), evaluate("", case, [], 0, None, runtime_metadata=right_runtime)
        self.assertIn("writer", compare(left, right, mode="model_routing")["routing_change"])
        changed_words = json.loads(json.dumps(candidate_snapshot)); changed_words["light"]["target_words"] = 901
        changed_runtime = runtime_metadata_from_manifest({"as_of": "2026-09-01", "config_snapshot": changed_words,
                                                          "runtime": {"config_hash": "third-cfg", "models": changed_words["models"], "prompt_hash": "p", "code_hash": "c"},
                                                          "usage": [{"runtime": {"config_hash": "third-cfg", "prompt_hash": "p", "code_hash": "c"}}]}, frozen)
        with self.assertRaises(ValueError):
            compare(left, evaluate("", case, [], 0, None, runtime_metadata=changed_runtime), mode="model_routing")


if __name__ == "__main__":
    unittest.main()
