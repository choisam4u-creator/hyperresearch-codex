"""실패한 모델 호출의 사용량, 로그, 장부와 재개 동작 회귀 테스트."""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hprc import cli, codex_runner, ledger, pipeline  # noqa: E402


FAKE_CODEX = """#!/bin/sh
out=""; prev=""
for arg in "$@"; do
  if [ "$prev" = "-o" ]; then out="$arg"; fi
  prev="$arg"
done
echo '{"type":"turn.completed","usage":{"input_tokens":7,"cached_input_tokens":2,"output_tokens":1}}'
printf '%s' '{"ok":true}' > "$out"
"""


class UsageRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="hpr-usage-recovery-"))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _fake_codex(self):
        bindir = self.root / "bin"
        bindir.mkdir(exist_ok=True)
        binary = bindir / "codex"
        binary.write_text(FAKE_CODEX, encoding="utf-8")
        binary.chmod(0o755)
        return bindir

    def test_usage_limit_accepts_and_preserves_all_call_metadata(self):
        error = codex_runner.UsageLimit(
            "limit", "09:00", usage={"input_tokens": 3}, usage_known=True,
            backend="codex", model="gpt", effort="high", web_search=True,
            seconds=1.25, stderr="limit detail",
        )
        self.assertEqual(
            ({"input_tokens": 3}, True, "codex", "gpt", "high", True, 1.25, "limit detail"),
            (error.usage, error.usage_known, error.backend, error.model, error.effort,
             error.web_search, error.seconds, error.stderr),
        )

    def test_uuid_logs_never_overwrite_legacy_or_colliding_attempt_logs(self):
        bindir = self._fake_codex()
        logs = self.root / "logs"
        logs.mkdir()
        legacy = logs / "writer.stderr.log"
        legacy.write_bytes(b"legacy-bytes\x00")
        ids = [SimpleNamespace(hex="same-id"), SimpleNamespace(hex="same-id"), SimpleNamespace(hex="different-id")]
        env = {"HPR_BACKEND": "codex", "PATH": f"{bindir}:{os.environ.get('PATH', '')}"}
        with mock.patch.dict(os.environ, env), mock.patch("hprc.codex_runner.uuid.uuid4", side_effect=ids):
            for _ in range(2):
                codex_runner.run_step("writer", "p", {}, {}, {"model": "gpt"}, {"timeout": 2}, logs, attempt=1)
        self.assertEqual(b"legacy-bytes\x00", legacy.read_bytes())
        self.assertEqual(2, len(list(logs.glob("writer.attempt-1.*.events.jsonl"))))
        self.assertEqual(2, len(list(logs.glob("writer.attempt-1.*.stderr.log"))))

    def test_next_attempt_reads_uuid_orphan_logs_and_ignores_malformed_names(self):
        run = pipeline.Run(self.root, "질문", "light", "resume-logs", quiet=True)
        run.logs.mkdir(parents=True)
        (run.logs / "writer.attempt-4.orphan.stderr.log").write_text("partial", encoding="utf-8")
        (run.logs / "writer.attempt-bad.deadbeef.stderr.log").write_text("bad", encoding="utf-8")
        self.assertEqual(5, run._next_attempt("writer"))

    def test_legacy_flat_ledger_and_manifest_usage_stay_known_and_backfill_is_idempotent(self):
        now = time.time()
        ledger.append(self.root, {"ts": now - 1, "run_id": "old-ledger", "step": "writer", "in": 11,
                                  "cached": 2, "out": 3, "seconds": 4, "backend": "codex"})
        run_dir = self.root / "research" / "runs" / "old-manifest"
        run_dir.mkdir(parents=True)
        at = now - 0.5
        manifest = {"run_id": "old-manifest", "prompt": "q", "tier": "light", "lang": "ko", "preset": "standard",
                    "usage": [{"step": "analyst", "at": at, "backend": "codex",
                               "usage": {"input_tokens": 13, "cached_input_tokens": 5, "output_tokens": 7}}]}
        (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.assertEqual(1, ledger.backfill(self.root))
        self.assertEqual(0, ledger.backfill(self.root))
        rows = ledger.rows(self.root)
        backfilled = next(row for row in rows if row["run_id"] == "old-manifest")
        self.assertEqual(at, backfilled["ts"])
        summary = ledger.summarize(self.root, include_mock=True)
        self.assertEqual((2, 0, 24, 7, 10),
                         (summary["total"]["known_calls"], summary["total"]["unknown_calls"],
                          summary["total"]["in"], summary["total"]["cached"], summary["total"]["out"]))

    def test_backfill_recognizes_a_legacy_row_without_record_id(self):
        at = time.time()
        path = ledger.path(self.root)
        path.parent.mkdir(parents=True)
        legacy = {"ts": at, "date": time.strftime("%Y-%m-%d", time.localtime(at)), "run_id": "same",
                  "step": "writer", "in": 9, "cached": 1, "out": 2, "backend": "codex"}
        path.write_text(json.dumps(legacy) + "\n", encoding="utf-8")
        run_dir = self.root / "research" / "runs" / "same"
        run_dir.mkdir(parents=True)
        manifest = {"tier": "light", "lang": "ko", "preset": "standard",
                    "usage": [{"step": "writer", "at": at,
                               "usage": {"input_tokens": 9, "cached_input_tokens": 1, "output_tokens": 2}}]}
        (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.assertEqual(0, ledger.backfill(self.root))
        self.assertEqual([legacy], ledger.rows(self.root))

    def test_unknown_usage_is_not_reported_as_zero_or_a_complete_price_cap(self):
        cost = pipeline.estimate_cost(
            [{"usage": {}, "usage_known": False},
             {"usage": {}, "usage_known": True},
             {"usage": {"input_tokens": 10, "cached_input_tokens": 1, "output_tokens": 2}}],
            {"price_input_per_m": 10, "price_output_per_m": 20, "price_cached_per_m": None},
        )
        self.assertEqual(1, cost["unknown_calls"])
        self.assertEqual(2, cost["known_calls"])
        run = pipeline.Run(self.root, "질문", "light", "unknown-final", quiet=True)
        run.m.usage({"step": "writer", "usage": {}, "usage_known": False, "seconds": 1})
        run.dir.joinpath("report.md").write_text("# 질문: 질문\n\n확인할 수 없는 사용량입니다.\n", encoding="utf-8")
        run.dir.joinpath("citecheck.json").write_text('{"checks":[]}', encoding="utf-8")
        run.dir.joinpath("findings.json").write_text('{"findings":[]}', encoding="utf-8")
        run.dir.joinpath("sources.json").write_text('{"warnings":[]}', encoding="utf-8")
        report = run.step_final().read_text(encoding="utf-8")
        self.assertIn("미측정 1회", report)
        self.assertIn("요금 상한 미확정", report)

    def test_failure_metadata_falls_back_and_resume_continues_attempt_numbers(self):
        run = pipeline.Run(self.root, "질문", "light", "retry-resume", quiet=True)
        calls = []

        def fail_then_succeed(name, *args, attempt=1, **kwargs):
            calls.append(attempt)
            if attempt < 3:
                raise codex_runner.CodexError("broken", backend="", model=None, effort=None,
                                              web_search=None, seconds=None, usage_known=False)
            return {"ok": True}, {"usage": {"input_tokens": 2, "output_tokens": 1}, "usage_known": True,
                                   "backend": "mock", "seconds": 0.1}

        with mock.patch.dict(os.environ, {"HPR_BACKEND": "mock"}), mock.patch("hprc.pipeline.run_step", fail_then_succeed):
            with self.assertRaises(pipeline.Blocked):
                run.call("writer", "p", {}, {}, "writer", web_search=True)
            self.assertEqual({"ok": True}, run.call("writer", "p", {}, {}, "writer", web_search=True))
        self.assertEqual([1, 2, 3], calls)
        rows = [row for row in run.m.data["usage"] if row["step"] == "writer"]
        self.assertEqual([1, 2, 3], [row["attempt"] for row in rows])
        self.assertEqual("mock", rows[0]["backend"])
        self.assertEqual(run.cfg["models"]["writer"]["model"], rows[0]["model"])
        self.assertEqual(run.cfg["models"]["writer"]["effort"], rows[0]["effort"])
        self.assertTrue(rows[0]["web_search"])
        self.assertEqual(0, rows[0]["seconds"])

    def test_malformed_event_usage_is_unknown_and_input_escape_is_rejected(self):
        events = self.root / "events.jsonl"
        events.write_text('{bad json}\n{"type":"turn.completed","usage":"bad"}\n', encoding="utf-8")
        self.assertEqual({"usage": {}, "items": {}, "usage_known": False}, codex_runner.parse_events(events))
        work = self.root / "work"
        work.mkdir()
        with self.assertRaises(codex_runner.CodexError):
            codex_runner.write_inputs(work, {"../escape.txt": "x"})
        self.assertFalse((self.root / "escape.txt").exists())

    def test_budget_must_be_positive_in_cli_and_direct_pipeline_use(self):
        with mock.patch.object(sys, "argv", ["hpr", "run", "q", "--budget", "0"]), \
                mock.patch.object(cli.pipeline, "run", side_effect=AssertionError("invalid budget reached pipeline")), \
                self.assertRaises(SystemExit) as ctx:
            cli.main()
        self.assertEqual(2, ctx.exception.code)
        with self.assertRaises(pipeline.Blocked):
            pipeline.Run(self.root, "q", "light", "bad-budget", quiet=True, budget=-1)
        self.assertFalse((self.root / "research" / "runs" / "bad-budget" / "manifest.json").exists())

    def test_budget_is_checked_before_first_call_and_before_retry(self):
        run = pipeline.Run(self.root, "q", "light", "budget-call", quiet=True, budget=5)
        run.m.usage({"step": "old", "usage": {"input_tokens": 5}, "usage_known": True})
        with mock.patch("hprc.pipeline.run_step") as run_step:
            with self.assertRaises(pipeline.Blocked):
                run.call("writer", "p", {}, {}, "writer")
        run_step.assert_not_called()

        retry = pipeline.Run(self.root, "q", "light", "budget-retry", quiet=True, budget=5)
        calls = []

        def measured_failure(name, *args, attempt=1, **kwargs):
            calls.append(attempt)
            raise codex_runner.CodexError("bad", usage={"input_tokens": 5}, usage_known=True)

        with mock.patch("hprc.pipeline.run_step", measured_failure):
            with self.assertRaises(pipeline.Blocked) as ctx:
                retry.call("writer", "p", {}, {}, "writer")
        self.assertIn("예산 상한", str(ctx.exception))
        self.assertEqual([1], calls)

    def test_same_run_lock_rejects_overlap_and_releases_after_exit(self):
        run_dir = self.root / "research" / "runs" / "locked"
        with pipeline._run_lock(run_dir):
            with self.assertRaises(pipeline.Blocked) as ctx:
                with pipeline._run_lock(run_dir):
                    pass
            self.assertIn("이미 실행 중", str(ctx.exception))
        with pipeline._run_lock(run_dir):
            pass
        with mock.patch.object(pipeline, "fcntl", None):
            with self.assertRaises(pipeline.Blocked) as ctx:
                with pipeline._run_lock(run_dir):
                    pass
        self.assertIn("지원하지 않음", str(ctx.exception))

    def test_parallel_critic_resume_reuses_completed_partial_result(self):
        run = pipeline.Run(self.root, "q", "light", "partial", quiet=True)
        run.T["critics"], run.T["parallel"] = ["dialectic", "depth"], 1
        run.dir.joinpath("draft.md").write_text("사실 문장이다. [S1]", encoding="utf-8")
        run.dir.joinpath("claims.json").write_text('{"claims":[],"contradictions":[],"gaps":[]}', encoding="utf-8")
        calls = []

        def interrupted(name, *args, **kwargs):
            calls.append(name)
            if name == "critic_depth":
                raise pipeline.Blocked("interrupted")
            return {"findings": []}

        with mock.patch.object(run, "call", side_effect=interrupted):
            with self.assertRaises(pipeline.Blocked):
                run.step_critics()
        self.assertTrue(run.dir.joinpath("critics", "dialectic.json").exists())

        resumed = pipeline.Run(self.root, "q", "light", "partial", quiet=True)
        resumed.T["critics"], resumed.T["parallel"] = ["dialectic", "depth"], 1
        with mock.patch.object(resumed, "call", side_effect=lambda name, *a, **k: calls.append(name) or {"findings": []}):
            resumed.step_critics()
        self.assertEqual(1, calls.count("critic_dialectic"))
        self.assertEqual(2, calls.count("critic_depth"))


if __name__ == "__main__":
    unittest.main()
