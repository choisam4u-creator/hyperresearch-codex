"""분석 산출물을 동일 입력에서만 재사용하는 작은 파일 캐시.

호출자는 ``context``에 질문, 언어, 기준일, 유효 설정, 모델, 프롬프트,
출력 스키마, 런타임과 출처 해시를 모두 넣어야 한다. 이 모듈은 그 의미를
추론하지 않고 전달받은 전체 값을 정확히 해시한다. 캐시 적중은 모델 호출이
아니며, 저장된 usage를 새 절감량으로 바꾸거나 추정하지 않는다.
"""
from __future__ import annotations

import copy
import errno
import hashlib
import json
import math
import os
import re
import socket
import stat
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None

try:
    import msvcrt
except ImportError:  # POSIX
    msvcrt = None


SCHEMA_VERSION = 1
_KEY = re.compile(r"^[0-9a-f]{64}$")


class AnalysisSingleFlightTimeout(ValueError):
    """동일 분석 키의 선행 생성이 제한 시간 안에 끝나지 않았을 때."""


class AnalysisSingleFlightUnsupported(ValueError):
    """현재 플랫폼에서 안전한 프로세스 간 잠금을 제공할 수 없을 때."""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def make_key(context: dict, inputs: dict[str, str]) -> str:
    """모든 context와 입력 원문이 정확히 같은 경우에만 같은 키를 만든다.

    결과 스키마의 실제 내용과 출처 해시를 포함시키는 일은 호출자의 책임이다.
    사전 순서와 무관하게 안정적이지만 값 하나라도 달라지면 다른 키가 된다.
    """
    if not isinstance(context, dict):
        raise TypeError("context는 dict여야 합니다")
    if not isinstance(inputs, dict) or not all(
        isinstance(name, str) and isinstance(text, str) for name, text in inputs.items()
    ):
        raise TypeError("inputs는 문자열 이름과 문자열 본문의 dict여야 합니다")
    payload = {
        "domain": "hyperresearch-codex.analysis-artifact",
        "schema_version": SCHEMA_VERSION,
        "context": context,
        "inputs": inputs,
    }
    return hashlib.sha256(_canonical(payload)).hexdigest()


_ANALYSIS_KEY_SCOPE = "analysis-delivery-insensitive-v1"


def make_analysis_key(context: dict, inputs: dict[str, str]) -> str:
    """후속 전달 옵션만 제외한 버전별 분석 캐시 키를 반환한다.

    ``analysis_runtime.config.efficiency.packet_inputs``와 ``inline_inputs``만
    분석가의 프롬프트·입력 파일에 영향을 주지 않는다. 나머지 맥락과 정확한
    입력 바이트는 모두 유지한다. 별도 범위 표식으로 기존 ``make_key``와 구분한다.
    """
    if not isinstance(context, dict):
        raise TypeError("context는 dict여야 합니다")
    normalized = copy.deepcopy(context)
    runtime = normalized.get("analysis_runtime")
    if isinstance(runtime, dict):
        config = runtime.get("config")
        if isinstance(config, dict):
            efficiency = config.get("efficiency")
            if isinstance(efficiency, dict):
                efficiency.pop("packet_inputs", None)
                efficiency.pop("inline_inputs", None)
    return make_key(
        {"analysis_key_scope": _ANALYSIS_KEY_SCOPE, "analysis_context": normalized},
        inputs,
    )


def _cache_directory(root: Path, *, create: bool) -> Path:
    supplied = Path(root)
    if supplied.is_symlink():
        raise ValueError("캐시 root는 심볼릭 링크일 수 없습니다")
    root_path = supplied.resolve()
    if not root_path.is_dir():
        raise ValueError("캐시 root가 디렉터리가 아닙니다")

    research = root_path / "research"
    if research.is_symlink():
        raise ValueError("research 경로가 심볼릭 링크입니다")
    if create:
        research.mkdir(exist_ok=True)
    if not research.is_dir():
        raise ValueError("research 경로가 디렉터리가 아닙니다")

    cache = research / "artifact-cache"
    if cache.is_symlink():
        raise ValueError("artifact-cache 경로가 심볼릭 링크입니다")
    if create:
        cache.mkdir(exist_ok=True)
    if not cache.is_dir():
        raise ValueError("artifact-cache 경로가 디렉터리가 아닙니다")
    resolved = cache.resolve()
    if not resolved.is_relative_to(root_path) or resolved != cache:
        raise ValueError("artifact-cache 경로가 프로젝트 밖을 가리킵니다")
    return cache


def _entry_path(root: Path, key: str, *, create: bool) -> Path:
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        raise ValueError("캐시 키는 64자리 소문자 sha256이어야 합니다")
    cache = _cache_directory(root, create=create)
    target = cache / f"{key}.json"
    if target.is_symlink() or target.parent != cache:
        raise ValueError("캐시 파일 경로가 안전하지 않습니다")
    return target


def _digest_payload(envelope: dict) -> str:
    unsigned = {name: envelope[name] for name in ("schema_version", "key", "result", "provenance")}
    return hashlib.sha256(_canonical(unsigned)).hexdigest()


def _lock_backend() -> str:
    if fcntl is not None:
        return "posix"
    if msvcrt is not None:
        return "windows"
    raise AnalysisSingleFlightUnsupported("이 플랫폼은 분석 캐시 single-flight 잠금을 지원하지 않습니다")


def _try_lock(stream, backend: str) -> bool:
    try:
        if backend == "posix":
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        return True
    except OSError as error:
        if isinstance(error, BlockingIOError) or error.errno in {
            errno.EACCES, errno.EAGAIN, errno.EDEADLK,
        }:
            return False
        raise


def _unlock(stream, backend: str) -> None:
    if backend == "posix":
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    else:
        stream.seek(0)
        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


@contextmanager
def analysis_singleflight(root: Path, key: str, *, timeout: float = 930.0,
                          poll_interval: float = 0.05) -> Iterator[None]:
    """동일 분석 키에서 한 프로세스만 miss를 생성하도록 제한 시간 동안 잠근다.

    잠금 파일은 캐시 항목과 같은 안전한 디렉터리에 영구 보존한다. 프로세스가
    실패하거나 예외가 나도 운영체제 잠금은 해제되므로 다음 대기자가 캐시를 다시
    확인한 뒤 생성할 수 있다.
    """
    if (not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0 or
            not isinstance(poll_interval, (int, float)) or
            not math.isfinite(poll_interval) or poll_interval <= 0):
        raise ValueError("single-flight 대기 시간은 양수여야 합니다")
    backend = _lock_backend()
    entry = _entry_path(root, key, create=True)
    lock_path = entry.with_suffix(".lock")
    if lock_path.is_symlink() or lock_path.parent != entry.parent:
        raise ValueError("분석 캐시 잠금 경로가 안전하지 않습니다")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NONBLOCK", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(lock_path, flags, 0o600)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError("분석 캐시 잠금 대상이 일반 파일이 아닙니다")
    stream = os.fdopen(descriptor, "r+b", buffering=0)
    acquired = False
    try:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b" ")
        deadline = time.monotonic() + timeout
        while not (acquired := _try_lock(stream, backend)):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AnalysisSingleFlightTimeout(
                    f"동일 분석 캐시 생성 대기 시간이 {timeout:g}초를 초과했습니다"
                )
            time.sleep(min(poll_interval, remaining))
        owner = (
            f" pid={os.getpid()} host={socket.gethostname()} "
            f"acquired={datetime.now(timezone.utc).isoformat()}\n"
        ).encode("utf-8")
        stream.seek(0)
        stream.write(owner)
        stream.truncate()
        stream.flush()
        os.fsync(stream.fileno())
        yield
    finally:
        try:
            if acquired:
                _unlock(stream, backend)
        finally:
            stream.close()


def load(root: Path, key: str) -> dict | None:
    """검증된 ``result``와 ``provenance``를 반환하고, 의심스러우면 ``None``.

    분석 결과 자체의 JSON schema 검증은 호출자가 수행한다.
    """
    try:
        path = _entry_path(root, key, create=False)
        if not path.is_file() or path.is_symlink():
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or set(value) != {
            "schema_version", "key", "result", "provenance", "digest"
        }:
            return None
        if value["schema_version"] != SCHEMA_VERSION or value["key"] != key:
            return None
        if not isinstance(value["result"], dict) or not isinstance(value["provenance"], dict):
            return None
        if not isinstance(value["digest"], str) or value["digest"] != _digest_payload(value):
            return None
        return {"result": value["result"], "provenance": value["provenance"]}
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        return None


def save(root: Path, key: str, result: dict, provenance: dict) -> None:
    """검증 가능한 envelope를 같은 파일시스템에서 원자적으로 저장한다."""
    if not isinstance(result, dict) or not isinstance(provenance, dict):
        raise TypeError("result와 provenance는 dict여야 합니다")
    path = _entry_path(root, key, create=True)
    if path.exists() and (not path.is_file() or path.is_symlink()):
        raise ValueError("기존 캐시 대상이 일반 파일이 아닙니다")
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "key": key,
        "result": result,
        "provenance": provenance,
    }
    envelope["digest"] = _digest_payload(envelope)
    fd, temporary = tempfile.mkstemp(prefix=".hpr-artifact-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(envelope, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink():
            raise ValueError("캐시 대상이 심볼릭 링크로 바뀌었습니다")
        os.replace(temporary, path)
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            # 일부 파일시스템은 디렉터리 fsync를 지원하지 않는다. 파일 fsync와
            # 원자 replace는 이미 끝났으므로 저장 실패로 오인하지 않는다.
            pass
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


__all__ = [
    "AnalysisSingleFlightTimeout", "AnalysisSingleFlightUnsupported", "SCHEMA_VERSION",
    "analysis_singleflight", "load", "make_analysis_key", "make_key", "save",
]
