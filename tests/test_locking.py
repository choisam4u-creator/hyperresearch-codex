"""플랫폼 독립 run 잠금의 프로세스 간 배타성과 정리 동작."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hprc import locking
from hprc.locking import RunLocked, UnsupportedLock, run_lock


class RunLockTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.tmp.name) / "research" / "runs" / "같은-실행"

    def tearDown(self):
        self.tmp.cleanup()

    def test_cross_process_exclusive_and_release(self):
        repo = Path(__file__).resolve().parents[1]
        script = ("import sys\n"
                  "from pathlib import Path\n"
                  "from hprc.locking import run_lock\n"
                  "with run_lock(Path(sys.argv[1])):\n"
                  " print('LOCKED', flush=True)\n"
                  " sys.stdin.readline()\n")
        child = subprocess.Popen([sys.executable, "-c", script, str(self.run_dir)], cwd=repo,
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        child_error = ""
        try:
            ready = child.stdout.readline()
            self.assertEqual("LOCKED\n", ready, child.stderr.read() if child.poll() is not None else "")
            with self.assertRaises(RunLocked) as caught:
                with run_lock(self.run_dir):
                    pass
            self.assertIn("pid=", str(caught.exception))
            self.assertTrue((self.run_dir / ".run.lock").is_file())
        finally:
            if child.stdin and child.poll() is None:
                try:
                    child.stdin.write("release\n")
                    child.stdin.flush()
                except BrokenPipeError:
                    pass
            if child.stdin:
                child.stdin.close()
            child.wait(timeout=5)
            if child.stdout:
                child.stdout.close()
            if child.stderr:
                child_error = child.stderr.read()
                child.stderr.close()
        self.assertEqual(0, child.returncode, child_error)
        with run_lock(self.run_dir):
            self.assertTrue((self.run_dir / ".run.lock").is_file())

    def test_unlock_runs_only_after_successful_acquire(self):
        class FakeWindowsLock:
            LK_NBLCK = 1
            LK_UNLCK = 2

            def __init__(self):
                self.calls = []

            def locking(self, _fd, mode, size):
                self.calls.append((mode, size))

        backend = FakeWindowsLock()
        with mock.patch.object(locking, "fcntl", None), mock.patch.object(locking, "msvcrt", backend):
            with run_lock(self.run_dir):
                pass
        self.assertEqual([(backend.LK_NBLCK, 1), (backend.LK_UNLCK, 1)], backend.calls)

    def test_unsupported_platform_stops_before_creating_lock_file(self):
        with mock.patch.object(locking, "fcntl", None), mock.patch.object(locking, "msvcrt", None):
            with self.assertRaises(UnsupportedLock):
                with run_lock(self.run_dir):
                    pass
        self.assertFalse(self.run_dir.exists())


if __name__ == "__main__":
    unittest.main()
