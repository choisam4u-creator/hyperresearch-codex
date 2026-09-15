import json
import multiprocessing
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from hprc import artifact_reuse, pipeline, vault


FIXTURE = Path(__file__).parent / "fixtures" / "benchmark_inputs.json"


def _run_fake_analysis(root_text, run_id, fixture_text, reuse, barrier, events_text,
                       outcomes, fail_first=False):
    """별도 프로세스에서 실제 pipeline과 mock backend를 통과한다."""
    root = Path(root_text)
    fixture = Path(fixture_text)
    case = next(row for row in json.loads(fixture.read_text(encoding="utf-8"))["cases"]
                if row["id"] == "fact-ko-01")
    actual = pipeline.run_step

    def counted(name, *args, **kwargs):
        if name == "analyst":
            fd = os.open(events_text, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                os.write(fd, f"{run_id}\n".encode("utf-8"))
            finally:
                os.close(fd)
            time.sleep(0.25)
            if fail_first:
                marker = root / "fail-first.claimed"
                try:
                    claim = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                except FileExistsError:
                    pass
                else:
                    os.close(claim)
                    raise pipeline.Blocked("intentional fake analyst failure")
        return actual(name, *args, **kwargs)

    try:
        with patch.dict(os.environ, {"HPR_BACKEND": "mock"}), \
             patch.object(pipeline, "run_step", side_effect=counted):
            barrier.wait(timeout=10)
            pipeline.run(root, case["prompt"], "light", run_id=run_id, quiet=True,
                         lang=case["lang"], replay_file=str(fixture), case_id=case["id"],
                         efficiency={"reuse_analysis": reuse})
        outcomes.put((run_id, "ok"))
    except Exception as error:  # 결과를 부모 테스트가 구체적으로 판정한다.
        outcomes.put((run_id, f"{type(error).__name__}:{error}"))


def _hold_key_lock(root_text, key, ready, release):
    with artifact_reuse.analysis_singleflight(Path(root_text), key, timeout=2):
        ready.set()
        release.wait(timeout=5)


def _sync_vault(root_text, barrier, outcomes):
    try:
        barrier.wait(timeout=5)
        outcomes.put(("ok", vault.sync(Path(root_text))))
    except Exception as error:
        outcomes.put((type(error).__name__, str(error)))


class AnalysisSingleFlightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "research").mkdir()
        (self.root / "research" / "config.json").write_text(
            json.dumps({"budget": {"max_retries": 0}, "codex": {"timeout": 2}}),
            encoding="utf-8",
        )
        self.events = self.root / "analyst-events.txt"
        self.ctx = multiprocessing.get_context("spawn")

    def _pair(self, fixtures, *, reuse=True, fail_first=False):
        barrier = self.ctx.Barrier(2)
        outcomes = self.ctx.Queue()
        processes = [
            self.ctx.Process(
                target=_run_fake_analysis,
                args=(str(self.root), f"run-{index}", str(fixture), reuse, barrier,
                      str(self.events), outcomes, fail_first),
            )
            for index, fixture in enumerate(fixtures)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(20)
            self.assertFalse(process.is_alive(), "fake backend worker did not finish")
            self.assertEqual(0, process.exitcode)
        return [outcomes.get(timeout=2) for _ in processes]

    def _event_count(self):
        if not self.events.exists():
            return 0
        return len(self.events.read_text(encoding="utf-8").splitlines())

    def test_same_key_concurrent_miss_calls_fake_analyst_once(self):
        outcomes = self._pair([FIXTURE, FIXTURE])
        self.assertEqual(["ok", "ok"], sorted(status for _, status in outcomes))
        self.assertEqual(1, self._event_count())
        manifests = [json.loads((self.root / "research" / "runs" / f"run-{i}" /
                                 "manifest.json").read_text(encoding="utf-8")) for i in range(2)]
        self.assertEqual(1, sum(any(row["step"] == "analyst" for row in data["usage"])
                                for data in manifests))
        self.assertTrue(any(any(event.get("singleflight_wait") for event in data.get("reuse_events", []))
                            for data in manifests))

    def test_failed_owner_releases_lock_and_waiter_populates_cache(self):
        outcomes = self._pair([FIXTURE, FIXTURE], fail_first=True)
        statuses = [status for _, status in outcomes]
        self.assertEqual(1, statuses.count("ok"))
        self.assertEqual(1, sum("intentional fake analyst failure" in status for status in statuses))
        self.assertEqual(2, self._event_count())

        # 성공한 대기자가 저장한 결과는 다음 실행에서 호출 없이 재사용된다.
        barrier = self.ctx.Barrier(1)
        queue = self.ctx.Queue()
        _run_fake_analysis(str(self.root), "recovered", str(FIXTURE), True, barrier,
                           str(self.events), queue)
        self.assertEqual("ok", queue.get(timeout=2)[1])
        self.assertEqual(2, self._event_count())

    def test_different_keys_do_not_coalesce(self):
        changed = json.loads(FIXTURE.read_text(encoding="utf-8"))
        case = next(row for row in changed["cases"] if row["id"] == "fact-ko-01")
        case["prompt"] += " 다른 키"
        alternate = self.root / "alternate.json"
        alternate.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
        outcomes = self._pair([FIXTURE, alternate])
        self.assertEqual(["ok", "ok"], sorted(status for _, status in outcomes))
        self.assertEqual(2, self._event_count())

    def test_opt_out_keeps_two_independent_calls(self):
        outcomes = self._pair([FIXTURE, FIXTURE], reuse=False)
        self.assertEqual(["ok", "ok"], sorted(status for _, status in outcomes))
        self.assertEqual(2, self._event_count())

    def test_wait_is_bounded_and_timeout_does_not_poison_lock(self):
        key = "a" * 64
        ready = self.ctx.Event()
        release = self.ctx.Event()
        holder = self.ctx.Process(target=_hold_key_lock,
                                  args=(str(self.root), key, ready, release))
        holder.start()
        self.assertTrue(ready.wait(timeout=5))
        with self.assertRaises(artifact_reuse.AnalysisSingleFlightTimeout):
            with artifact_reuse.analysis_singleflight(self.root, key, timeout=0.05,
                                                       poll_interval=0.01):
                self.fail("contended lock must not be acquired")
        release.set()
        holder.join(5)
        self.assertEqual(0, holder.exitcode)
        with artifact_reuse.analysis_singleflight(self.root, key, timeout=0.5):
            pass

    def test_nonfinite_waits_and_nonregular_lock_targets_are_rejected(self):
        key = "b" * 64
        for value in (float("nan"), float("inf"), 0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                with artifact_reuse.analysis_singleflight(self.root, key, timeout=value):
                    pass
        if hasattr(os, "mkfifo"):
            cache = self.root / "research" / "artifact-cache"
            cache.mkdir()
            os.mkfifo(cache / f"{key}.lock")
            started = time.monotonic()
            with self.assertRaisesRegex(ValueError, "일반 파일"):
                with artifact_reuse.analysis_singleflight(self.root, key, timeout=0.1):
                    pass
            self.assertLess(time.monotonic() - started, 0.5)

    def test_concurrent_real_vault_rebuilds_are_serialized(self):
        notes = self.root / "research" / "notes"
        for index in range(3):
            vault.write_note(notes, f"S{index + 1}", {
                "url": f"https://example.test/{index}", "title": f"note {index}",
                "domain": "example.test", "text": f"shared evidence body {index}",
                "error": "",
            })
        barrier = self.ctx.Barrier(2)
        outcomes = self.ctx.Queue()
        workers = [self.ctx.Process(target=_sync_vault,
                                    args=(str(self.root), barrier, outcomes)) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(10)
            self.assertEqual(0, worker.exitcode)
        self.assertEqual([("ok", 3), ("ok", 3)],
                         sorted(outcomes.get(timeout=2) for _ in workers))
        self.assertEqual(3, len(vault.search(self.root, "shared")))


if __name__ == "__main__":
    unittest.main()
