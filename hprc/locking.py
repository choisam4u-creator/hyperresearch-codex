"""같은 research run의 중복 실행을 막는 프로세스 간 파일 잠금."""
from __future__ import annotations

import errno
import os
import socket
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None

try:
    import msvcrt
except ImportError:  # POSIX
    msvcrt = None


class LockError(ValueError):
    """run 잠금을 시작할 수 없을 때의 공통 오류."""


class RunLocked(LockError):
    """다른 프로세스가 같은 run 잠금을 소유하고 있을 때."""


class UnsupportedLock(LockError):
    """현재 플랫폼에 지원하는 파일 잠금 API가 없을 때."""


def _backend() -> str:
    if fcntl is not None:
        return "posix"
    if msvcrt is not None:
        return "windows"
    raise UnsupportedLock("이 플랫폼은 동일 run 중복 실행 잠금을 지원하지 않습니다")


def _ensure_lock_byte(stream) -> None:
    stream.seek(0, os.SEEK_END)
    if stream.tell() == 0:
        stream.write(b" ")
        stream.flush()
    stream.seek(0)


def _read_owner(stream) -> str:
    try:
        # Windows byte-range 잠금은 강제 잠금이므로 잠근 첫 바이트를 건너뛴다.
        stream.seek(1)
        raw = stream.read()
    except OSError:
        return "소유자 정보 없음"
    return raw.decode("utf-8", errors="replace").strip() or "소유자 정보 없음"


def _acquire(stream, backend: str) -> None:
    try:
        if backend == "posix":
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError as error:
        if isinstance(error, BlockingIOError) or error.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
            raise RunLocked from error
        raise


def _release(stream, backend: str) -> None:
    if backend == "posix":
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    else:
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def _write_owner(stream) -> str:
    owner = f"pid={os.getpid()} host={socket.gethostname()} acquired={datetime.now(timezone.utc).isoformat()}"
    stream.seek(0)
    stream.write(b" " + owner.encode("utf-8") + b"\n")
    stream.truncate()
    stream.flush()
    os.fsync(stream.fileno())
    return owner


@contextmanager
def run_lock(run_dir: Path) -> Iterator[None]:
    """run 디렉터리의 영구 ``.run.lock`` 파일을 비차단 방식으로 잠근다."""
    backend = _backend()
    run_path = Path(run_dir)
    run_path.mkdir(parents=True, exist_ok=True)
    lock_path = run_path / ".run.lock"
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    stream = os.fdopen(descriptor, "r+b", buffering=0)
    acquired = False
    try:
        _ensure_lock_byte(stream)
        try:
            _acquire(stream, backend)
            acquired = True
        except RunLocked as error:
            owner = _read_owner(stream)
            raise RunLocked(f"같은 실행이 이미 실행 중: {run_path.name} ({owner})") from error
        _write_owner(stream)
        yield
    finally:
        try:
            if acquired:
                _release(stream, backend)
        finally:
            stream.close()


__all__ = ["LockError", "RunLocked", "UnsupportedLock", "run_lock"]
