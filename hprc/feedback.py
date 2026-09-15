"""기존 실행에서 개인정보 없는 수치/열거형 피드백 묶음을 만든다.

출력은 로컬 stdout으로만 전달한다. 프롬프트, 출처, 로그, 경로와 오류 문자열은
읽거나 복사하지 않으며 이 모듈은 어떤 전송 기능도 갖지 않는다.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
RUN_STATUSES = frozenset({"running", "ok", "warn", "blocked", "budget_stop", "usage_limit", "auth_required", "codex_missing", "failed"})
TIERS = frozenset({"light", "full"})
PRESETS = frozenset({"standard", "lean", "economy"})
LANGUAGES = frozenset({"ko", "en"})
REPORT_FORMATS = frozenset({"brief", "facts", "comparison", "analysis"})
QUALITY_STATUSES = frozenset({"passed", "review_required", "failed"})
BACKENDS = frozenset({"mock", "codex"})
TOKEN_MEASUREMENTS = frozenset({"estimated", "recorded", "unknown"})
STEP_STATUSES = frozenset({"ok", "warn", "failed", "blocked", "running", "pending", "skipped"})


class FeedbackError(ValueError):
    """피드백 원본 실행을 안전하게 해석할 수 없을 때."""


def _object(path: Path, *, required: bool) -> dict[str, Any] | None:
    if path.is_symlink():
        raise FeedbackError("심볼릭 링크 메타데이터는 읽지 않습니다")
    if not path.is_file():
        if required:
            raise FeedbackError("필수 실행 메타데이터가 없습니다")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise FeedbackError("실행 메타데이터를 읽을 수 없습니다") from error
    if not isinstance(value, dict):
        raise FeedbackError("실행 메타데이터 형식이 올바르지 않습니다")
    return value


def _enum(value: Any, allowed: frozenset[str]) -> str | None:
    return value if isinstance(value, str) and value in allowed else None


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _usage(manifest: dict[str, Any]) -> tuple[int | None, int | None, int | None, int | None, int | None, int | None, int | float | None, str | None, str]:
    rows = manifest.get("usage")
    if not isinstance(rows, list):
        raise FeedbackError("실행 사용량 메타데이터 형식이 올바르지 않습니다")
    totals = [0, 0, 0]
    unknown = 0
    duration: int | float = 0
    duration_known = True
    backends: set[str] = set()
    backend_known = True
    measurement_kinds: set[str] = set()
    valid_rows = 0
    for row in rows:
        if not isinstance(row, dict):
            raise FeedbackError("실행 사용량 항목 형식이 올바르지 않습니다")
        valid_rows += 1
        backend = _enum(row.get("backend"), BACKENDS)
        if backend:
            backends.add(backend)
        else:
            backend_known = False
        seconds = _number(row.get("seconds"))
        if seconds is not None and seconds <= sys.float_info.max:
            try:
                duration += seconds
                if isinstance(duration, float) and not math.isfinite(duration):
                    duration_known = False
            except OverflowError:
                duration_known = False
        else:
            duration_known = False
        values = row.get("usage")
        if row.get("usage_known") is False or not isinstance(values, dict):
            unknown += 1
            measurement_kinds.add("unknown")
            continue
        parsed = [_number(values.get(key)) for key in ("input_tokens", "cached_input_tokens", "output_tokens")]
        if any(value is None or not isinstance(value, int) for value in parsed) or parsed[1] > parsed[0]:
            unknown += 1
            measurement_kinds.add("unknown")
            continue
        for index, value in enumerate(parsed):
            totals[index] += value
        measurement_kinds.add("estimated" if backend == "mock" else ("recorded" if backend == "codex" else "unknown"))
    backend_kind = next(iter(backends)) if backend_known and len(backends) == 1 else None
    measurement = next(iter(measurement_kinds)) if len(measurement_kinds) == 1 else "unknown"
    known = valid_rows - unknown
    return valid_rows, known, totals[0], totals[1], totals[2], unknown, (round(duration, 3) if duration_known else None), backend_kind, measurement


def build_feedback(run_dir: Path) -> dict[str, Any]:
    """검증된 기존 실행 디렉터리에서 고정 allowlist JSON을 만든다."""
    manifest = _object(run_dir / "manifest.json", required=True)
    assert manifest is not None
    state = _object(run_dir / "state.json", required=False) or {}
    quality = _object(run_dir / "quality.json", required=False) or {}
    steps = manifest.get("steps")
    step_counts: dict[str, int] | None = None
    if steps is not None and not isinstance(steps, list):
        raise FeedbackError("실행 단계 메타데이터 형식이 올바르지 않습니다")
    if isinstance(steps, list):
        step_counts = {name: 0 for name in sorted(STEP_STATUSES)}
        for row in steps:
            if not isinstance(row, dict):
                raise FeedbackError("실행 단계 항목 형식이 올바르지 않습니다")
            status = _enum(row.get("status"), STEP_STATUSES) if isinstance(row, dict) else None
            if status:
                step_counts[status] += 1
    calls, known_calls, input_tokens, cached_tokens, output_tokens, unknown_calls, seconds, backend, token_measurement = _usage(manifest)
    snapshot = manifest.get("effective_config_snapshot")
    if not isinstance(snapshot, dict):
        snapshot = manifest.get("config_snapshot")
    preset = snapshot.get("preset") if isinstance(snapshot, dict) else None
    report_format = snapshot.get("report_format") if isinstance(snapshot, dict) else manifest.get("report_format")
    return {
        "schema_version": SCHEMA_VERSION,
        "run_status": _enum(state.get("status"), RUN_STATUSES),
        "backend": backend,
        "token_measurement": _enum(token_measurement, TOKEN_MEASUREMENTS),
        "tier": _enum(manifest.get("tier"), TIERS),
        "preset": _enum(preset, PRESETS),
        "language": _enum(manifest.get("lang"), LANGUAGES),
        "report_format": _enum(report_format, REPORT_FORMATS),
        "quality_status": _enum(quality.get("status"), QUALITY_STATUSES),
        "model_calls": calls,
        "known_usage_calls": known_calls,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_tokens,
        "output_tokens": output_tokens,
        "unknown_usage_calls": unknown_calls,
        "model_seconds": seconds,
        "step_counts": step_counts,
    }


def render_feedback(run_dir: Path) -> str:
    return json.dumps(build_feedback(run_dir), ensure_ascii=False, sort_keys=True, indent=2)
