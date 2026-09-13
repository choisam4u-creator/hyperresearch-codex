"""run_id 경로 검증과 CLI의 안전한 실패 동작."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hprc import cli
from hprc.run_paths import InvalidRunId, run_directory


class RunDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_korean_and_legacy_safe_characters_are_preserved(self):
        got = run_directory(self.root, "한글 실행-01_test")
        self.assertEqual((self.root / "research" / "runs" / "한글 실행-01_test").resolve(), got)

    def test_rejects_path_syntax_blank_and_control_characters(self):
        invalid = ["", "   ", ".", "..", "../escaped", "a/b", "a\\b", "/tmp/absolute", "line\nfeed", "delete\x7f"]
        for run_id in invalid:
            with self.subTest(run_id=repr(run_id)), self.assertRaises(InvalidRunId):
                run_directory(self.root, run_id)

    def test_rejects_leaf_and_runs_root_symlink_escape(self):
        runs = self.root / "research" / "runs"
        outside = self.root / "outside"
        runs.mkdir(parents=True)
        outside.mkdir()
        (runs / "escaped").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(InvalidRunId):
            run_directory(self.root, "escaped")
        (runs / "parent-alias").symlink_to(runs, target_is_directory=True)
        with self.assertRaises(InvalidRunId):
            run_directory(self.root, "parent-alias")

        other_root = self.root / "other-project"
        other_root.mkdir()
        (other_root / "research").mkdir()
        (other_root / "research" / "runs").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(InvalidRunId):
            run_directory(other_root, "safe-name")


class RunPathCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.old_root = cli.ROOT
        cli.ROOT = self.root

    def tearDown(self):
        cli.ROOT = self.old_root
        self.tmp.cleanup()

    def invoke(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "argv", ["hpr", *argv]), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main()
        return code, out.getvalue(), err.getvalue()

    def test_run_resume_and_status_reject_invalid_id_before_pipeline_or_read(self):
        for argv in (("run", "질문", "--run-id", "../escaped"),
                     ("resume", "../escaped"),
                     ("status", "../escaped")):
            with self.subTest(argv=argv), mock.patch.object(cli.pipeline, "run") as run:
                code, _, err = self.invoke(*argv)
            self.assertEqual(2, code)
            self.assertIn("BLOCKED:", err)
            self.assertIn("run_id", err)
            run.assert_not_called()

    def test_missing_explicit_status_is_readable_exit_two(self):
        code, _, err = self.invoke("status", "없는-실행")
        self.assertEqual(2, code)
        self.assertIn("실행 기록 없음", err)

    def test_status_listing_skips_external_symlink_without_reading_it(self):
        runs = self.root / "research" / "runs"
        safe = runs / "정상-실행"
        outside = self.root / "outside"
        safe.mkdir(parents=True)
        outside.mkdir()
        safe.joinpath("manifest.json").write_text(json.dumps({"prompt": "정상", "tier": "light", "usage": [], "steps": []}), encoding="utf-8")
        outside.joinpath("manifest.json").write_text(json.dumps({"prompt": "외부 비밀", "tier": "light", "usage": [], "steps": []}), encoding="utf-8")
        (runs / "외부-link").symlink_to(outside, target_is_directory=True)

        code, out, err = self.invoke("status")
        self.assertEqual(0, code)
        self.assertIn("정상-실행", out)
        self.assertNotIn("외부 비밀", out + err)
        self.assertIn("건너뜀", err)


if __name__ == "__main__":
    unittest.main()
