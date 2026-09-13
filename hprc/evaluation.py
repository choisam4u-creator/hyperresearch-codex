"""고정 합성 자료의 오프라인 평가 harness. 실제 리서치 품질이나 모델 성능을 증명하지 않는다."""
import argparse
import hashlib
import json
from pathlib import Path
import re

from .vault import note_body


def _stable(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def case_input_hash(case: dict) -> str:
    """비교 가능한 고정 입력만 해시한다. 기대 결과와 보고서는 입력에 넣지 않는다."""
    inputs = {key: case.get(key) for key in ("id", "prompt", "sources", "required_claims")}
    return hashlib.sha256(_stable(inputs).encode("utf-8")).hexdigest()


def _usage_totals(usage: list[dict]) -> dict:
    input_tokens = cached_tokens = output_tokens = unknown_calls = 0
    for row in usage:
        known = row.get("usage_known")
        if known is None:
            known = bool(row.get("usage") or "in" in row)
        if not known:
            unknown_calls += 1
            continue
        raw = row.get("usage") or {}
        input_tokens += raw.get("input_tokens", row.get("in", 0)) or 0
        cached_tokens += raw.get("cached_input_tokens", row.get("cached", 0)) or 0
        output_tokens += raw.get("output_tokens", row.get("out", 0)) or 0
    return {"input_tokens": input_tokens, "cache_tokens": cached_tokens, "output_tokens": output_tokens,
            "unknowncalls": unknown_calls}


def _usage_models(usage: list[dict]) -> list[dict]:
    models = {(row.get("backend") or "unknown", row.get("model") or "unknown", row.get("effort") or "unknown") for row in usage}
    return [{"backend": backend, "model": model, "effort": effort} for backend, model, effort in sorted(models)]


def _elapsed(manifest: dict) -> float | None:
    created = manifest.get("created_at")
    finished = [step.get("finished_at") for step in manifest.get("steps", []) if isinstance(step.get("finished_at"), (int, float))]
    if not isinstance(created, (int, float)) or not finished:
        return None
    return max(finished) - created


def _quality_counts(quality: dict | None) -> tuple[int, int | None, str]:
    quality = quality or {}
    issues = quality.get("issues", [])
    unsupported = sum(1 for issue in issues if issue.get("kind") == "citation_unsupported")
    scope = quality.get("scope")
    selected, checked = (scope or {}).get("selected_count"), (scope or {}).get("checked_count")
    missing = max(selected - checked, 0) if isinstance(selected, int) and isinstance(checked, int) else None
    return unsupported, missing, quality.get("status", "not_checked")


def evaluate(report: str, case: dict, usage: list[dict], elapsed_seconds: float, quality: dict | None,
             model_config: dict | None = None) -> dict:
    """한 보고서를 합성 case에 대조한다. required_text_coverage는 문자열 관찰값이다."""
    required = case.get("required_claims", [])
    matched = sum(1 for text in required if text in report)
    unsupported, missing, quality_status = _quality_counts(quality)
    return {"case_id": case["id"], "input_hash": case_input_hash(case),
            "required_text_coverage": (matched / len(required)) if required else 1.0,
            "required_claim_count": len(required), "required_text_matched": matched,
            "coverage_note": "literal string observation only; not factual-accuracy validation",
            "unsupported_count": unsupported, "missing_judgment_count": missing,
            **_usage_totals(usage), "elapsed_seconds": elapsed_seconds, "quality_status": quality_status,
            "model_config": model_config or {}, "model_config_note": "user-supplied comparison label; not verified runtime configuration",
            "usage_models": _usage_models(usage)}


def compare(left: dict, right: dict) -> dict:
    """동일 case·입력·모델 설정에서만 수치를 비교한다."""
    for field in ("case_id", "input_hash", "model_config", "usage_models"):
        if left.get(field) != right.get(field):
            raise ValueError(f"비교 불가: {field} 다름")
    numeric = ("required_text_coverage", "unsupported_count", "missing_judgment_count", "input_tokens", "cache_tokens",
               "output_tokens", "unknowncalls", "elapsed_seconds")
    delta = {key: right.get(key, 0) - left.get(key, 0) for key in numeric if left.get(key) is not None and right.get(key) is not None}
    return {"case_id": left["case_id"], "input_hash": left["input_hash"], "model_config": left["model_config"],
            "usage_models": left["usage_models"], "left": left, "right": right, "delta": delta,
            "comparison_note": "synthetic fixed-input comparison; does not establish real-world performance improvement"}


def _case(cases_path: Path, case_id: str) -> dict:
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    for case in cases["cases"]:
        if case.get("id") == case_id:
            return case
    raise ValueError(f"알 수 없는 case: {case_id}")


def _source_text(path: Path) -> str:
    body = note_body(path)
    return re.sub(r"^\n?# [^\n]*\n\n", "", body, count=1).rstrip("\n")


def _validate_synthetic_run(run_dir: Path, manifest: dict, case: dict) -> None:
    if manifest.get("prompt") != case["prompt"]:
        raise ValueError("case prompt와 manifest.prompt가 달라 평가 불가")
    sources = json.loads((run_dir / "sources.json").read_text(encoding="utf-8")).get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("sources.json sources 형식이 목록이 아님")
    source_ids = [source.get("id") for source in sources if isinstance(source, dict)]
    expected_ids = set(case["sources"])
    if len(source_ids) != len(sources) or len(source_ids) != len(set(source_ids)):
        raise ValueError("sources.json에 유효하지 않거나 중복된 source id가 있어 평가 불가")
    if set(source_ids) != expected_ids:
        raise ValueError("case sources와 sources.json source id 집합이 달라 평가 불가")
    observed = {}
    for source in sources:
        path = Path(source.get("path", ""))
        if not path.is_absolute():
            path = run_dir / path
        if source.get("id") in case["sources"]:
            observed[source["id"]] = _source_text(path)
    if observed != case["sources"]:
        raise ValueError("case sources와 sources.json 노트 원문이 달라 평가 불가")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="고정 합성 자료 오프라인 평가")
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--case", required=True, dest="case_id")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model-config", default="{}", help="사용자가 붙이는 비교 라벨 JSON. 실제 실행 설정을 검증하거나 모델을 호출하지 않는다.")
    args = parser.parse_args(argv)
    case = _case(args.cases, args.case_id)
    run_dir = args.run_dir
    report_path = run_dir / "final_report.md"
    if not report_path.is_file():
        report_path = run_dir / "report.md"
    if not report_path.is_file():
        raise FileNotFoundError("final_report.md 또는 report.md 없음")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    _validate_synthetic_run(run_dir, manifest, case)
    quality_path = run_dir / "quality.json"
    quality = json.loads(quality_path.read_text(encoding="utf-8")) if quality_path.is_file() else None
    model_config = json.loads(args.model_config)
    result = evaluate(report_path.read_text(encoding="utf-8"), case, manifest.get("usage", []), _elapsed(manifest), quality, model_config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
