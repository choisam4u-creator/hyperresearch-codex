"""분석 산출물을 동일 입력에서만 재사용하는 작은 파일 캐시.

호출자는 ``context``에 질문, 언어, 기준일, 유효 설정, 모델, 프롬프트,
출력 스키마, 런타임과 출처 해시를 모두 넣어야 한다. 이 모듈은 그 의미를
추론하지 않고 전달받은 전체 값을 정확히 해시한다. 캐시 적중은 모델 호출이
아니며, 저장된 usage를 새 절감량으로 바꾸거나 추정하지 않는다.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
_KEY = re.compile(r"^[0-9a-f]{64}$")


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


__all__ = ["SCHEMA_VERSION", "load", "make_key", "save"]
