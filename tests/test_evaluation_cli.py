"""분리 정답·고정 재생 실행을 evaluator CLI로 읽는 계약."""
import json
import tempfile
import unittest
from pathlib import Path

from hprc.evaluation import case_input_hash, main, report_sha256
from hprc.vault import write_note


FIXTURES = Path(__file__).parent / "fixtures"
INPUTS = FIXTURES / "benchmark_inputs.json"
ANSWERS = FIXTURES / "benchmark_answers.json"


class EvaluationCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = next(case for case in json.loads(INPUTS.read_text(encoding="utf-8"))["cases"] if case["id"] == "fact-ko-01")

    def _run_dir(self, root: Path, name: str, *, model: str = "fixed", corrupt_hash: bool = False) -> tuple[Path, str]:
        run = root / name; run.mkdir()
        report = "A submitted replay report."
        (run / "report.md").write_text(report, encoding="utf-8")
        sources = []
        for source_id, text in self.case["sources"].items():
            note = write_note(run / "notes", source_id, {"url": f"https://fixture.invalid/{source_id}", "title": source_id,
                                                          "domain": "fixture.invalid", "text": text, "sha256": source_id * 32})
            sources.append({"id": source_id, "path": str(note)})
        (run / "sources.json").write_text(json.dumps({"sources": sources}), encoding="utf-8")
        runtime = {"config_hash": f"cfg-{model}", "code_hash": "code", "prompt_hash": "prompt",
                   "models": {"writer": {"model": model, "effort": "low"}}}
        config = {"models": runtime["models"], "default_model": model, "light": {"target_words": 900}}
        manifest = {"prompt": self.case["prompt"], "lang": self.case["lang"], "as_of": self.case["baseline_time"],
                    "frozen_input_hash": "bad" if corrupt_hash else case_input_hash(self.case), "runtime": runtime,
                    "config_snapshot": config, "effective_config_snapshot": config,
                    "usage": [{"attempt": 1, "status": "ok", "usage": {"input_tokens": 10, "output_tokens": 2},
                               "runtime": {"config_hash": runtime["config_hash"], "code_hash": "code", "prompt_hash": "prompt"}}],
                    "created_at": 10, "steps": [{"finished_at": 12}]}
        (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (run / "frozen_input.json").write_text(json.dumps(self.case), encoding="utf-8")
        (run / "quality.json").write_text(json.dumps({"status": "passed", "issues": []}), encoding="utf-8")
        return run, report

    def _envelope(self, root: Path, report: str, *, wrong_hash: bool = False) -> Path:
        answer = next(item for item in json.loads(ANSWERS.read_text(encoding="utf-8"))["cases"] if item["id"] == self.case["id"])
        items = [{"item_id": item["item_id"], "verdict": "supported", "evidence_ids": item["evidence"]["all_of"]} for item in answer["items"]]
        path = root / "adjudications.json"
        path.write_text(json.dumps({"report_sha256": "wrong" if wrong_hash else report_sha256(report), "items": items}), encoding="utf-8")
        return path

    def _args(self, run: Path, output: Path) -> list[str]:
        return ["--cases", str(INPUTS), "--answers", str(ANSWERS), "--case", self.case["id"], "--run-dir", str(run), "--output", str(output)]

    def test_bound_frozen_replay_writes_runtime_metadata_and_quality_result(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); run, report = self._run_dir(root, "run")
            output = root / "evaluation.json"
            self.assertEqual(0, main(self._args(run, output) + ["--adjudications", str(self._envelope(root, report))]))
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(result["quality_qualified"])
            self.assertTrue(result["adjudication_report_bound"])
            self.assertEqual(case_input_hash(self.case), result["input_hash"])
            self.assertTrue(result["runtime_metadata"]["runtime_consistent"])
            self.assertEqual(12, result["total_tokens_per_quality_qualified_report"])

    def test_missing_adjudications_stay_unbound_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); run, _ = self._run_dir(root, "run")
            output = root / "evaluation.json"
            self.assertEqual(0, main(self._args(run, output)))
            result = json.loads(output.read_text(encoding="utf-8"))
            self.assertIsNone(result["quality_qualified"])
            self.assertEqual(2, result["adjudication"]["unknown_required_count"])
            self.assertIsNone(result["total_tokens_per_quality_qualified_report"])

    def test_cli_rejects_bad_envelope_answer_set_and_frozen_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); run, report = self._run_dir(root, "run")
            output = root / "out.json"
            with self.assertRaises(ValueError):
                main(self._args(run, output) + ["--adjudications", str(self._envelope(root, report, wrong_hash=True))])
            bad_answers = root / "answers.json"
            bad_answers.write_text(json.dumps({"cases": [{"id": "other", "items": []}]}), encoding="utf-8")
            with self.assertRaises(ValueError):
                main(["--cases", str(INPUTS), "--answers", str(bad_answers), "--case", self.case["id"], "--run-dir", str(run), "--output", str(output)])
            bad_run, _ = self._run_dir(root, "bad", corrupt_hash=True)
            with self.assertRaises(ValueError):
                main(self._args(bad_run, output))

    def test_optional_code_and_routing_comparisons_are_saved_without_model_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            baseline, report = self._run_dir(root, "baseline", model="fixed")
            prior = root / "prior.json"
            main(self._args(baseline, prior) + ["--adjudications", str(self._envelope(root, report))])
            current, report = self._run_dir(root, "current", model="fixed")
            code_out = root / "code.json"
            self.assertEqual(0, main(self._args(current, code_out) + ["--adjudications", str(self._envelope(root, report)),
                                                                       "--compare", str(prior), "--comparison-mode", "code_only"]))
            self.assertEqual("code_only", json.loads(code_out.read_text())["comparison"]["comparison_mode"])
            routed, report = self._run_dir(root, "routed", model="routed")
            routing_out = root / "routing.json"
            self.assertEqual(0, main(self._args(routed, routing_out) + ["--adjudications", str(self._envelope(root, report)),
                                                                          "--compare", str(prior), "--comparison-mode", "model_routing"]))
            self.assertIn("writer", json.loads(routing_out.read_text())["comparison"]["routing_change"])


if __name__ == "__main__":
    unittest.main()
