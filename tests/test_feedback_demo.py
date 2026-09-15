import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hprc import cli
from hprc.demo import demo_payload
from hprc.feedback import FeedbackError, build_feedback


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.run = self.root / "research/runs/safe"
        self.run.mkdir(parents=True)

    def write_json(self, name, value):
        (self.run / name).write_text(json.dumps(value), encoding="utf-8")

    def test_strict_allowlist_drops_private_sentinels_and_unknown_strings(self):
        secret = "PRIVATE_SENTINEL prompt source /Users/name raw-error account@example.test"
        self.write_json("manifest.json", {"prompt": secret, "tier": "invented", "lang": "ko", "usage": [
            {"step": secret, "backend": "mock", "seconds": 1.25, "usage": {"input_tokens": 10, "cached_input_tokens": 2, "output_tokens": 3}, "stderr": secret}],
            "steps": [{"name": secret, "status": "ok", "error": secret}], "effective_config_snapshot": {"preset": "lean", "report_format": "facts", "private": secret}})
        self.write_json("state.json", {"status": "failed", "error": secret, "path": secret})
        self.write_json("quality.json", {"status": "review_required", "issues": [secret]})
        payload = build_feedback(self.run)
        encoded = json.dumps(payload)
        self.assertNotIn("PRIVATE_SENTINEL", encoded)
        self.assertEqual(set(payload), {"schema_version", "run_status", "backend", "token_measurement", "tier", "preset", "language", "report_format", "quality_status", "model_calls", "known_usage_calls", "input_tokens", "cached_input_tokens", "output_tokens", "unknown_usage_calls", "model_seconds", "step_counts"})
        self.assertIsNone(payload["tier"])
        self.assertEqual(("mock", 10, 1), (payload["backend"], payload["input_tokens"], payload["step_counts"]["ok"]))
        self.assertEqual("estimated", payload["token_measurement"])

    def test_unknown_usage_and_mixed_backend_are_not_presented_as_measured(self):
        self.write_json("manifest.json", {"usage": [
            {"backend": "mock", "seconds": 1, "usage_known": True, "usage": {"input_tokens": 10, "cached_input_tokens": 2, "output_tokens": 3}},
            {"backend": "codex", "usage_known": False, "usage": {"input_tokens": 999, "cached_input_tokens": 1, "output_tokens": 1}},
        ]})
        payload = build_feedback(self.run)
        self.assertEqual((None, "unknown", 1, 10, None), (payload["backend"], payload["token_measurement"], payload["unknown_usage_calls"], payload["input_tokens"], payload["model_seconds"]))

    def test_missing_backend_and_unbounded_duration_stay_unknown(self):
        self.write_json("manifest.json", {"usage": [{"seconds": 10**1000, "usage_known": True, "usage": {"input_tokens": 8, "cached_input_tokens": 2, "output_tokens": 1}}]})
        payload = build_feedback(self.run)
        self.assertEqual((None, "unknown", 1, 0, None), (payload["backend"], payload["token_measurement"], payload["known_usage_calls"], payload["unknown_usage_calls"], payload["model_seconds"]))
        json.dumps(payload, allow_nan=False)

    def test_completed_review_required_run_preserves_warn_state(self):
        self.write_json("manifest.json", {"tier": "light", "lang": "ko", "usage": [], "steps": [{"name": "final", "status": "warn"}]})
        self.write_json("state.json", {"step": "final", "status": "warn"})
        self.write_json("quality.json", {"status": "review_required"})
        payload = build_feedback(self.run)
        self.assertEqual(("warn", "review_required", 1), (payload["run_status"], payload["quality_status"], payload["step_counts"]["warn"]))

    def test_invalid_cached_count_and_symlink_metadata_are_blocked_or_unknown(self):
        self.write_json("manifest.json", {"usage": [{"backend": "codex", "seconds": 0, "usage_known": True, "usage": {"input_tokens": 2, "cached_input_tokens": 3, "output_tokens": 1}}]})
        payload = build_feedback(self.run)
        self.assertEqual((1, 0, "unknown"), (payload["unknown_usage_calls"], payload["input_tokens"], payload["token_measurement"]))
        target = self.run / "real-state.json"
        target.write_text("{}", encoding="utf-8")
        (self.run / "state.json").symlink_to(target)
        with self.assertRaises(FeedbackError): build_feedback(self.run)

    def test_malformed_and_wrong_schema_are_blocked(self):
        (self.run / "manifest.json").write_text("{bad", encoding="utf-8")
        with self.assertRaises(FeedbackError): build_feedback(self.run)
        self.write_json("manifest.json", [])
        with self.assertRaises(FeedbackError): build_feedback(self.run)
        self.write_json("manifest.json", {"usage": "PRIVATE_SENTINEL", "steps": []})
        with self.assertRaises(FeedbackError): build_feedback(self.run)
        self.write_json("manifest.json", {"usage": [], "steps": ["PRIVATE_SENTINEL"]})
        with self.assertRaises(FeedbackError): build_feedback(self.run)

    def test_cli_rejects_traversal_without_pipeline(self):
        with mock.patch.object(cli, "ROOT", self.root), mock.patch("sys.argv", ["hpr", "feedback", "../safe"]), mock.patch.object(cli.pipeline, "run", side_effect=AssertionError("pipeline called")), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, cli.main())

    def test_feedback_cli_never_runs_pipeline(self):
        self.write_json("manifest.json", {"usage": []})
        with mock.patch.object(cli, "ROOT", self.root), mock.patch("sys.argv", ["hpr", "feedback", "safe"]), mock.patch.object(cli.pipeline, "run", side_effect=AssertionError("pipeline called")), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(0, cli.main())
        self.assertEqual(0, json.loads(output.getvalue())["model_calls"])

    def test_demo_is_explicitly_synthetic_and_offline(self):
        data = demo_payload()
        self.assertEqual(("synthetic_preview", False, 0), (data["demo"], data["research_run"], data["model_calls"]))
        with mock.patch.object(cli, "ROOT", self.root), mock.patch("sys.argv", ["hpr", "demo"]), mock.patch.object(cli.pipeline, "run", side_effect=AssertionError("pipeline called")), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(0, cli.main())
        self.assertIn("실제 조사 결과나 품질 증명이 아닙니다", output.getvalue())
        self.assertIn("수정 전:", output.getvalue())
        self.assertIn("수정 후:", output.getvalue())


if __name__ == "__main__":
    unittest.main()
