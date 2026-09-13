import json
import tempfile
import unittest
from pathlib import Path

from hprc.evaluation import compare, evaluate, main
from hprc.vault import write_note


FIXTURE = Path(__file__).parent / "fixtures" / "evaluation_cases.json"


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
        self.case = self.cases[0]

    def test_fixture_reference_is_literal_coverage_not_fact_accuracy(self):
        result = evaluate(self.case["reference_report"], self.case, [{"in": 10, "cached": 4, "out": 2, "backend": "mock", "model": "mock", "effort": "none"}], 1.5,
                          {"status": "passed", "issues": []}, {"model": "mock"})
        self.assertEqual(1.0, result["required_text_coverage"])
        self.assertEqual((10, 4, 2, 0), (result["input_tokens"], result["cache_tokens"], result["output_tokens"], result["unknowncalls"]))
        self.assertIn("not factual-accuracy", result["coverage_note"])
        self.assertEqual([{"backend": "mock", "model": "mock", "effort": "none"}], result["usage_models"])

    def test_all_fixed_fixture_examples_match_only_their_declared_synthetic_expectations(self):
        for case in self.cases:
            result = evaluate(case["reference_report"], case, [], 0, {"status": "passed", "issues": [], "scope": {"selected_count": 0, "checked_count": 0}})
            for key, expected in case["expected_findings"].items():
                self.assertEqual(expected, result[key], case["id"])

    def test_quality_and_unknown_usage_are_counted(self):
        quality = {"status": "review_required", "issues": [{"kind": "citation_unsupported"}], "scope": {"selected_count": 2, "checked_count": 1}}
        result = evaluate("", self.case, [{"usage_known": False}], 0, quality)
        self.assertEqual((1, 1, 1), (result["unsupported_count"], result["missing_judgment_count"], result["unknowncalls"]))
        self.assertEqual("review_required", result["quality_status"])

    def test_compare_rejects_case_hash_or_model_config_mismatch(self):
        left = evaluate(self.case["reference_report"], self.case, [], 1, None, {"model": "a"})
        right = evaluate(self.case["reference_report"], self.case, [], 2, None, {"model": "a"})
        self.assertEqual(1, compare(left, right)["delta"]["elapsed_seconds"])
        changed_model = dict(right, model_config={"model": "b"})
        with self.assertRaises(ValueError):
            compare(left, changed_model)
        changed_hash = dict(right, input_hash="different")
        with self.assertRaises(ValueError):
            compare(left, changed_hash)

    def test_module_command_reads_explicit_run_paths_and_writes_json(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"; run.mkdir()
            (run / "report.md").write_text(self.case["reference_report"], encoding="utf-8")
            notes = run / "notes"
            sources = []
            for source_id, text in self.case["sources"].items():
                note = write_note(notes, source_id, {"url": f"https://fixture.test/{source_id}", "title": source_id,
                                                      "domain": "fixture.test", "text": text, "sha256": source_id * 32})
                sources.append({"id": source_id, "path": str(note)})
            (run / "sources.json").write_text(json.dumps({"sources": sources}), encoding="utf-8")
            manifest = {"prompt": self.case["prompt"], "usage": [{"backend": "mock", "model": "mock", "effort": "none"}],
                        "created_at": 10, "steps": [{"finished_at": 13}]}
            (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            output = Path(temp) / "review" / "evaluation.json"
            self.assertEqual(0, main(["--cases", str(FIXTURE), "--case", self.case["id"], "--run-dir", str(run), "--output", str(output), "--model-config", '{"model":"mock"}']))
            self.assertEqual("facts-ko-v1", json.loads(output.read_text(encoding="utf-8"))["case_id"])

    def test_module_command_rejects_prompt_or_source_mismatch_and_unknown_elapsed(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"; run.mkdir()
            (run / "report.md").write_text("x", encoding="utf-8")
            (run / "manifest.json").write_text(json.dumps({"prompt": "다른 질문", "usage": []}), encoding="utf-8")
            (run / "sources.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
            with self.assertRaises(ValueError):
                main(["--cases", str(FIXTURE), "--case", self.case["id"], "--run-dir", str(run), "--output", str(Path(temp) / "x.json")])
        result = evaluate("", self.case, [], None, None)
        self.assertIsNone(result["elapsed_seconds"])

    def test_module_command_rejects_source_body_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"; run.mkdir()
            note = run / "S1.md"
            note.write_text("---\nid: \"x\"\n---\n\n# S1\n\n바뀐 본문\n", encoding="utf-8")
            (run / "report.md").write_text("x", encoding="utf-8")
            (run / "manifest.json").write_text(json.dumps({"prompt": self.case["prompt"], "usage": []}), encoding="utf-8")
            (run / "sources.json").write_text(json.dumps({"sources": [{"id": "S1", "path": "S1.md"}]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                main(["--cases", str(FIXTURE), "--case", self.case["id"], "--run-dir", str(run), "--output", str(Path(temp) / "x.json")])

    def test_module_command_rejects_extra_or_duplicate_source_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"; run.mkdir()
            (run / "report.md").write_text("x", encoding="utf-8")
            (run / "manifest.json").write_text(json.dumps({"prompt": self.case["prompt"], "usage": []}), encoding="utf-8")
            notes = run / "notes"
            sources = []
            for source_id, text in self.case["sources"].items():
                note = write_note(notes, source_id, {"url": f"https://fixture.test/{source_id}", "title": source_id,
                                                      "domain": "fixture.test", "text": text, "sha256": source_id * 32})
                sources.append({"id": source_id, "path": str(note)})
            extra = write_note(notes, "S3", {"url": "https://fixture.test/S3", "title": "S3", "domain": "fixture.test",
                                               "text": "추가 원문", "sha256": "3" * 64})
            output = str(Path(temp) / "x.json")
            for invalid_sources in (sources + [{"id": "S3", "path": str(extra)}], sources + [dict(sources[0])]):
                (run / "sources.json").write_text(json.dumps({"sources": invalid_sources}), encoding="utf-8")
                with self.assertRaises(ValueError):
                    main(["--cases", str(FIXTURE), "--case", self.case["id"], "--run-dir", str(run), "--output", output])
