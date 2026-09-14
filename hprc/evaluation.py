"""고정 합성 자료의 오프라인 평가 도구.

이 모듈은 제출자가 명시한 판정과 증거 식별자를 채점한다. 보고서 문장과
정답의 문자열 일치를 사실성 점수로 바꾸지 않으며, 실제 모델을 호출하지 않는다.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from .vault import note_body


_INPUT_CASE_FIELDS = ("id", "split", "category", "lang", "prompt", "sources", "baseline_time")
_FORBIDDEN_INPUT_FIELDS = {"answer", "answers", "expected", "expected_findings", "reference_report", "adjudication"}
_VERDICTS = {"supported", "contradicted", "insufficient", "unknown"}


def _stable(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def case_input_hash(case: dict) -> str:
    """비교 가능한 고정 입력만 해시한다. 정답이나 채점표는 여기에 넣지 않는다."""
    # 구형 fixture도 계속 읽을 수 있게 required_claims는 기존 case에만 포함한다.
    keys = ("id", "prompt", "sources", "required_claims") if "required_claims" in case else _INPUT_CASE_FIELDS
    inputs = {key: case.get(key) for key in keys if key in case}
    return hashlib.sha256(_stable(inputs).encode("utf-8")).hexdigest()


def report_sha256(report: str) -> str:
    """제출된 판정이 어느 보고서에 대한 것인지 고정하는 UTF-8 해시."""
    return hashlib.sha256(report.encode("utf-8")).hexdigest()


def _contains_forbidden_input_key(value: object) -> bool:
    if isinstance(value, dict):
        return any(key in _FORBIDDEN_INPUT_FIELDS or _contains_forbidden_input_key(item)
                   for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden_input_key(item) for item in value)
    return False


def frozen_input_export(benchmark: dict) -> dict:
    """모델에 줄 수 있는 고정 입력만 복사한다.

    이 함수의 반환값은 정답 fixture와 분리되어야 한다. 예상 결과·참조 보고서가
    섞인 입력은 거부해, 평가 자료가 모델 입력으로 새는 실수를 빠르게 찾는다.
    """
    if not isinstance(benchmark, dict) or not isinstance(benchmark.get("cases"), list):
        raise ValueError("benchmark inputs의 cases는 목록이어야 함")
    cases = []
    ids = set()
    for case in benchmark["cases"]:
        if not isinstance(case, dict) or _contains_forbidden_input_key(case):
            raise ValueError("고정 입력에 정답·기대 결과·판정이 포함됨")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id or case_id in ids:
            raise ValueError("benchmark case id가 비었거나 중복됨")
        ids.add(case_id)
        exported = {key: case[key] for key in _INPUT_CASE_FIELDS if key in case}
        if not isinstance(exported.get("prompt"), str) or not isinstance(exported.get("sources"), dict):
            raise ValueError(f"{case_id}: prompt와 sources가 필요함")
        cases.append(exported)
    return {"benchmark_version": benchmark.get("benchmark_version", "unknown"),
            "frozen_at": benchmark.get("frozen_at", "unknown"), "cases": cases}


def load_benchmark(inputs_path: Path, answers_path: Path) -> tuple[dict, dict]:
    """분리된 입력과 정답을 읽고 id 집합만 연결한다."""
    inputs = json.loads(inputs_path.read_text(encoding="utf-8"))
    answers = json.loads(answers_path.read_text(encoding="utf-8"))
    frozen = frozen_input_export(inputs)
    if not isinstance(answers, dict) or not isinstance(answers.get("cases"), list):
        raise ValueError("benchmark answers의 cases는 목록이어야 함")
    answer_by_id = {}
    for answer in answers["cases"]:
        if not isinstance(answer, dict) or not isinstance(answer.get("id"), str):
            raise ValueError("benchmark answer id가 필요함")
        if answer["id"] in answer_by_id:
            raise ValueError("benchmark answer id가 중복됨")
        answer_by_id[answer["id"]] = answer
    input_ids = {case["id"] for case in frozen["cases"]}
    if input_ids != set(answer_by_id):
        raise ValueError("benchmark inputs와 answers의 case id 집합이 다름")
    return frozen, answer_by_id


def _without_model_selection(value: object) -> object:
    """설정 비교에서 역할별 선택 모델만 뺀다. 나머지 실행 조건은 남긴다."""
    if isinstance(value, dict):
        return {key: _without_model_selection(item) for key, item in value.items()
                if key not in {"models", "model", "default_model", "escalation_model"}}
    if isinstance(value, list):
        return [_without_model_selection(item) for item in value]
    return value


def _runtime_consistency(manifest: dict, current: dict) -> bool | None:
    """시도별 runtime이 현재 manifest runtime과 같은지 보수적으로 판정한다."""
    usage = manifest.get("usage", [])
    if not isinstance(usage, list) or not usage:
        return None
    keys = ("code_hash", "prompt_hash", "config_hash")
    for row in usage:
        attempt_runtime = row.get("runtime") if isinstance(row, dict) else None
        if not isinstance(attempt_runtime, dict) or any(attempt_runtime.get(key) is None for key in keys):
            return None
        if any(attempt_runtime.get(key) != current.get(key) for key in keys):
            return False
    return True


def runtime_metadata_from_manifest(manifest: dict, frozen_inputs: dict) -> dict:
    """pipeline manifest의 재현 메타를 evaluator 비교 형식으로 고정한다.

    값은 검증하거나 보완하지 않는다. 비교 결과에 당시 설정 snapshot·기준시각·
    모델 역할·프롬프트/코드 해시가 그대로 남도록 하는 연결 함수다.
    """
    runtime = manifest.get("runtime", {}) if isinstance(manifest.get("runtime", {}), dict) else {}
    effective = manifest.get("effective_config_snapshot", manifest.get("config_snapshot"))
    return {"benchmark_version": frozen_inputs.get("benchmark_version"), "frozen_at": frozen_inputs.get("frozen_at"),
            "frozen_input_hash": hashlib.sha256(_stable(frozen_inputs).encode("utf-8")).hexdigest(),
            "as_of": manifest.get("as_of"), "config_snapshot": effective,
            "initial_config_snapshot": manifest.get("config_snapshot"),
            "non_model_config_snapshot": _without_model_selection(effective),
            "config_hash": runtime.get("config_hash"), "code_revision": runtime.get("code_hash"),
            "prompt_hashes": runtime.get("prompt_hash"), "role_assignments": runtime.get("models"),
            "manifest_runtime": runtime, "runtime_consistent": _runtime_consistency(manifest, runtime)}


def materialize_mutation_cases(inputs: dict, answers: dict) -> tuple[list[dict], dict]:
    """10개 의미 경계 × 10개 주제로 정상·오류 주장 각 100개를 고정 생성한다.

    입력 fixture에는 정답을 두지 않고, 정상/오류 verdict와 오류 종류는 answer
    fixture에만 둔다. 숫자만 바꾸는 반복이 되지 않도록 template의 semantic_tag와
    subject가 모두 결과에 보존된다.
    """
    subjects = inputs.get("subjects", [])
    templates = inputs.get("templates", [])
    answer_by_template = {row.get("template_id"): row for row in answers.get("templates", []) if isinstance(row, dict)}
    if len(subjects) != 10 or len(templates) != 20:
        raise ValueError("mutation fixture는 주제 10개와 template 20개여야 함")
    cases, expected = [], {}
    for template in templates:
        template_id = template.get("template_id")
        answer = answer_by_template.get(template_id)
        if not isinstance(template_id, str) or not answer or answer.get("expected_verdict") not in _VERDICTS:
            raise ValueError("mutation template의 분리된 answer가 필요함")
        for subject in subjects:
            subject_id = subject.get("subject_id")
            if not isinstance(subject_id, str):
                raise ValueError("mutation subject_id가 필요함")
            case_id = f"{template_id}-{subject_id}"
            values = {**subject, **template}
            cases.append({"id": case_id, "group": template.get("group"), "semantic_tag": template.get("semantic_tag"),
                          "source": str(template.get("source", "")).format(**values),
                          "claim": str(template.get("claim", "")).format(**values)})
            expected[case_id] = {"expected_verdict": answer["expected_verdict"],
                                 "fault_type": answer.get("fault_type", "none")}
    return cases, expected


def _usage_totals(usage: list[dict]) -> dict:
    input_tokens = cached_tokens = output_tokens = unknown_calls = 0
    failure_attempts = retry_attempts = 0
    for row in usage:
        known = row.get("usage_known")
        if known is None:
            known = bool(row.get("usage") or "in" in row)
        status = str(row.get("status", "ok"))
        if status != "ok":
            failure_attempts += 1
        if isinstance(row.get("attempt"), int) and row["attempt"] > 1:
            retry_attempts += 1
        if not known:
            unknown_calls += 1
            continue
        raw = row.get("usage") or {}
        input_tokens += raw.get("input_tokens", row.get("in", 0)) or 0
        cached_tokens += raw.get("cached_input_tokens", row.get("cached", 0)) or 0
        output_tokens += raw.get("output_tokens", row.get("out", 0)) or 0
    # input_tokens에는 cached_input_tokens가 포함되는 provider도 있어 둘을 다시 더하지 않는다.
    return {"input_tokens": input_tokens, "cache_tokens": cached_tokens, "output_tokens": output_tokens,
            "unknowncalls": unknown_calls, "attempt_count": len(usage), "retry_attempt_count": retry_attempts,
            "failure_attempt_count": failure_attempts, "reported_total_tokens": input_tokens + output_tokens,
            "token_accounting_note": "input, cached-input, output are reported separately; cached input is not added twice to total"}


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


def evaluate_adjudications(answer: dict, submitted: list[dict] | None) -> dict:
    """사전 등록한 항목을 명시 판정·증거 id로 채점한다.

    `unknown`은 false나 supported로 변환하지 않는다. 누락된 판정도 unknown이며
    모든 분모를 결과에 남겨 부분 제출을 완주처럼 보이지 않게 한다.
    """
    items = answer.get("items", [])
    if not isinstance(items, list):
        raise ValueError("answer items는 목록이어야 함")
    item_ids = [item.get("item_id") for item in items if isinstance(item, dict)]
    if len(item_ids) != len(items) or any(not isinstance(item_id, str) for item_id in item_ids) or len(set(item_ids)) != len(item_ids):
        raise ValueError("answer item_id가 비었거나 중복됨")
    if submitted is not None and not isinstance(submitted, list):
        raise ValueError("submitted adjudications는 목록이어야 함")
    submitted_by_id = {}
    for entry in submitted or []:
        if not isinstance(entry, dict) or not isinstance(entry.get("item_id"), str):
            raise ValueError("submitted adjudication item_id가 필요함")
        item_id = entry["item_id"]
        if item_id not in set(item_ids):
            raise ValueError(f"등록되지 않은 adjudication item_id: {item_id}")
        if item_id in submitted_by_id:
            raise ValueError(f"중복 adjudication item_id: {item_id}")
        submitted_by_id[item_id] = entry
    results = []
    required = [item for item in items if item.get("required", True)]
    evidence_required = evidence_complete = matched = incorrect = unknown = explicit = 0
    for item in items:
        item_id = item.get("item_id")
        required_item = item.get("required", True)
        entry = submitted_by_id.get(item_id)
        verdict = entry.get("verdict") if entry else "unknown"
        if verdict not in _VERDICTS:
            verdict = "unknown"
        evidence_ids = entry.get("evidence_ids", []) if entry else []
        evidence_ids = evidence_ids if isinstance(evidence_ids, list) and all(isinstance(v, str) for v in evidence_ids) else []
        expectation = item.get("evidence", {}) if isinstance(item.get("evidence", {}), dict) else {}
        all_of = set(expectation.get("all_of", []))
        any_of = set(expectation.get("any_of", []))
        needs_evidence = bool(all_of or any_of)
        complete = all_of.issubset(evidence_ids) and (not any_of or bool(any_of & set(evidence_ids)))
        accepted = set(item.get("accepted_verdicts", []))
        if entry and required_item:
            explicit += 1
        if required_item and needs_evidence:
            evidence_required += 1
            if complete:
                evidence_complete += 1
        if verdict == "unknown":
            outcome = "unknown" if not entry else ("unknown_acknowledged" if "unknown" in accepted and (not needs_evidence or complete) else "unknown")
            if required_item:
                unknown += 1
        elif verdict in accepted and (not needs_evidence or complete):
            outcome = "matched"
            if required_item:
                matched += 1
        else:
            outcome = "incorrect"
            if required_item:
                incorrect += 1
        results.append({"item_id": item_id, "required": required_item, "submitted": bool(entry), "verdict": verdict,
                        "evidence_ids": evidence_ids, "evidence_complete": complete if needs_evidence else None,
                        "outcome": outcome})
    denominator = len(required)
    return {"items": results, "required_item_count": denominator, "submitted_required_count": explicit,
            "missing_required_count": denominator - explicit, "explicit_adjudication_coverage": explicit / denominator if denominator else 1.0,
            "evidence_required_count": evidence_required, "evidence_complete_count": evidence_complete,
            "evidence_coverage": evidence_complete / evidence_required if evidence_required else None,
            "matched_required_count": matched, "incorrect_required_count": incorrect, "unknown_required_count": unknown,
            "matched_required_coverage": matched / denominator if denominator else 1.0,
            "semantic_validation": "not_performed",
            "adjudication_note": "explicit verdict/evidence-id scoring only; unknown remains unknown and no report substring is treated as semantic truth"}


def _quality_qualified(quality_status: str, adjudication: dict | None, report_bound: bool | None) -> bool | None:
    if adjudication is None or report_bound is not True:
        return None
    outcomes = [item["outcome"] for item in adjudication["items"] if item["required"]]
    return quality_status == "passed" and all(outcome in {"matched", "unknown_acknowledged"} for outcome in outcomes)


def evaluate(report: str, case: dict, usage: list[dict], elapsed_seconds: float | None, quality: dict | None,
             model_config: dict | None = None, *, benchmark_answer: dict | None = None,
             submitted_adjudications: list[dict] | None = None, adjudication_report_sha256: str | None = None,
             runtime_metadata: dict | None = None) -> dict:
    """한 보고서·제출 판정을 고정 case에 대조한다.

    기존 `required_text_coverage`는 호환을 위한 문자열 관찰값일 뿐, benchmark
    품질 판정에는 사용하지 않는다.
    """
    required = case.get("required_claims", [])
    matched = sum(1 for text in required if text in report)
    unsupported, missing, quality_status = _quality_counts(quality)
    actual_report_sha256 = report_sha256(report)
    if adjudication_report_sha256 is not None and adjudication_report_sha256 != actual_report_sha256:
        raise ValueError("adjudication report_sha256가 제출 보고서와 다름")
    report_bound = (adjudication_report_sha256 == actual_report_sha256) if benchmark_answer else None
    adjudication = evaluate_adjudications(benchmark_answer, submitted_adjudications) if benchmark_answer else None
    quality_qualified = _quality_qualified(quality_status, adjudication, report_bound)
    totals = _usage_totals(usage)
    return {"case_id": case["id"], "input_hash": case_input_hash(case),
            "required_text_coverage": (matched / len(required)) if required else None,
            "required_claim_count": len(required), "required_text_matched": matched,
            "coverage_note": "literal string observation only; not factual-accuracy validation",
            "unsupported_count": unsupported, "missing_judgment_count": missing,
            **totals, "elapsed_seconds": elapsed_seconds, "quality_status": quality_status,
            "model_config": model_config or {}, "model_config_note": "user-supplied comparison label; not verified runtime configuration",
            "usage_models": _usage_models(usage), "runtime_metadata": runtime_metadata or {},
            "report_sha256": actual_report_sha256, "adjudication_report_bound": report_bound,
            "adjudication": adjudication, "quality_qualified": quality_qualified,
            "quality_qualified_report_count": 1 if quality_qualified else 0,
            "known_total_tokens_per_quality_qualified_report": (None if not quality_qualified else totals["reported_total_tokens"]),
            "total_tokens_per_quality_qualified_report": (None if not quality_qualified or totals["unknowncalls"] else totals["reported_total_tokens"])}


def _routing_change(left: dict, right: dict) -> dict:
    left_roles = (left.get("runtime_metadata") or {}).get("role_assignments", {})
    right_roles = (right.get("runtime_metadata") or {}).get("role_assignments", {})
    return {role: {"left": left_roles.get(role), "right": right_roles.get(role)}
            for role in sorted(set(left_roles) | set(right_roles)) if left_roles.get(role) != right_roles.get(role)}


def summarize_reports(results: list[dict]) -> dict:
    """여러 실행의 비용을 품질 통과 보고서 수로 나눈다.

    실패·재시도·품질 미달 실행의 사용량도 분자에 포함한다. 따라서 성공한 한
    보고서만 골라 비용을 낮게 보이게 할 수 없고, 미측정 호출은 별도 수치로 남는다.
    """
    totals = {key: sum((result.get(key) or 0) for result in results)
              for key in ("input_tokens", "cache_tokens", "output_tokens", "unknowncalls", "attempt_count",
                          "retry_attempt_count", "failure_attempt_count", "reported_total_tokens")}
    qualified = sum(1 for result in results if result.get("quality_qualified") is True)
    return {"report_count": len(results), "quality_qualified_report_count": qualified, **totals,
            "known_total_tokens_per_quality_qualified_report": totals["reported_total_tokens"] / qualified if qualified else None,
            "total_tokens_per_quality_qualified_report": totals["reported_total_tokens"] / qualified if qualified and not totals["unknowncalls"] else None,
            "cost_denominator_note": "all submitted run attempts, including failed/retried and quality-unqualified runs, are included in the numerator"}


def compare(left: dict, right: dict, *, mode: str | None = None) -> dict:
    """동일 고정 입력의 코드 변경 또는 명시한 라우팅 변경만 비교한다."""
    for field in ("case_id", "input_hash"):
        if left.get(field) != right.get(field):
            raise ValueError(f"비교 불가: {field} 다름")
    if mode is None:
        # 구형 caller에는 이전의 보수적 모델 동일성 규칙을 유지한다.
        for field in ("model_config", "usage_models"):
            if left.get(field) != right.get(field):
                raise ValueError(f"비교 불가: {field} 다름")
        mode = "legacy_fixed_model"
    elif mode not in {"code_only", "model_routing"}:
        raise ValueError("비교 mode는 code_only 또는 model_routing이어야 함")
    left_runtime, right_runtime = left.get("runtime_metadata") or {}, right.get("runtime_metadata") or {}
    if mode in {"code_only", "model_routing"}:
        if left_runtime.get("runtime_consistent") is not True or right_runtime.get("runtime_consistent") is not True:
            raise ValueError("명시 비교는 모든 usage runtime이 현재 runtime과 일치해야 함")
        identity_keys = ("code_revision", "prompt_hashes", "config_hash", "benchmark_version", "frozen_at",
                         "frozen_input_hash", "as_of", "config_snapshot", "non_model_config_snapshot")
        for key in identity_keys:
            if left_runtime.get(key) in (None, "") or right_runtime.get(key) in (None, ""):
                raise ValueError(f"명시 비교에는 {key} 메타데이터가 필요함")
    if mode == "code_only":
        if not isinstance(left_runtime.get("role_assignments"), dict) or not left_runtime["role_assignments"]:
            raise ValueError("code_only 비교에는 비어 있지 않은 role_assignments가 필요함")
        if left_runtime.get("role_assignments") != right_runtime.get("role_assignments"):
            raise ValueError("code_only 비교는 role_assignments가 같아야 함")
        for key in ("prompt_hashes", "config_hash", "benchmark_version", "frozen_at", "frozen_input_hash", "as_of", "non_model_config_snapshot"):
            if left_runtime.get(key) != right_runtime.get(key):
                raise ValueError(f"code_only 비교는 {key}가 같아야 함")
    elif mode == "model_routing":
        for key in ("code_revision", "prompt_hashes", "benchmark_version", "frozen_at", "frozen_input_hash",
                    "as_of", "non_model_config_snapshot"):
            if left_runtime.get(key) != right_runtime.get(key):
                raise ValueError(f"model_routing 비교는 {key}가 같아야 함")
        for key in ("code_revision", "prompt_hashes"):
            if left_runtime.get(key) in (None, "") or right_runtime.get(key) in (None, ""):
                raise ValueError(f"model_routing 비교에는 {key} 메타데이터가 필요함")
        if not isinstance(left_runtime.get("role_assignments"), dict) or not left_runtime["role_assignments"]:
            raise ValueError("model_routing 비교에는 비어 있지 않은 baseline role_assignments가 필요함")
        if not isinstance(right_runtime.get("role_assignments"), dict) or not right_runtime["role_assignments"]:
            raise ValueError("model_routing 비교에는 비어 있지 않은 candidate role_assignments가 필요함")
        if not _routing_change(left, right):
            raise ValueError("model_routing 비교에 명시된 역할별 모델 변경이 없음")
    numeric = ("required_text_coverage", "unsupported_count", "missing_judgment_count", "input_tokens", "cache_tokens",
               "output_tokens", "unknowncalls", "elapsed_seconds", "reported_total_tokens")
    delta = {key: right.get(key, 0) - left.get(key, 0) for key in numeric if left.get(key) is not None and right.get(key) is not None}
    return {"case_id": left["case_id"], "input_hash": left["input_hash"], "comparison_mode": mode,
            "model_config": left["model_config"], "usage_models": left["usage_models"], "left": left, "right": right,
            "delta": delta, "routing_change": _routing_change(left, right) if mode == "model_routing" else {},
            "comparison_note": "synthetic fixed-input comparison; only quality-qualified reports have token-per-report values; does not establish real-world performance improvement"}


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


def _validate_frozen_replay_run(run_dir: Path, manifest: dict, case: dict) -> None:
    """재생 실행이 선택한 frozen case와 완전히 같은 입력을 썼는지 확인한다."""
    _validate_synthetic_run(run_dir, manifest, case)
    if manifest.get("lang") != case.get("lang"):
        raise ValueError("frozen case lang과 manifest.lang이 달라 평가 불가")
    if manifest.get("as_of") != case.get("baseline_time"):
        raise ValueError("frozen case baseline_time과 manifest.as_of가 달라 평가 불가")
    digest = case_input_hash(case)
    if manifest.get("frozen_input_hash") != digest:
        raise ValueError("frozen case input hash와 manifest.frozen_input_hash가 달라 평가 불가")
    saved = run_dir / "frozen_input.json"
    if not saved.is_file():
        raise ValueError("frozen replay 실행에 frozen_input.json이 없음")
    saved_case = json.loads(saved.read_text(encoding="utf-8"))
    if saved_case != case or case_input_hash(saved_case) != digest:
        raise ValueError("frozen_input.json이 선택한 case와 달라 평가 불가")


def _adjudication_envelope(path: Path) -> tuple[list[dict], str]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {"report_sha256", "items"}:
        raise ValueError("adjudications는 report_sha256와 items만 가진 envelope여야 함")
    if not isinstance(value["report_sha256"], str) or not isinstance(value["items"], list):
        raise ValueError("adjudications envelope 형식이 올바르지 않음")
    return value["items"], value["report_sha256"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="고정 합성 자료 오프라인 평가")
    parser.add_argument("--cases", required=True, type=Path)
    parser.add_argument("--case", required=True, dest="case_id")
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model-config", default="{}", help="사용자가 붙이는 비교 라벨 JSON. 실제 실행 설정을 검증하거나 모델을 호출하지 않는다.")
    parser.add_argument("--answers", type=Path, help="정답을 분리한 benchmark answers JSON. 지정하면 frozen replay 입력을 엄격히 확인한다.")
    parser.add_argument("--adjudications", type=Path, help="report_sha256와 items를 가진 독립 판정 envelope JSON")
    parser.add_argument("--compare", type=Path, help="이전에 저장한 evaluation JSON과 비교한다. 모델 호출은 하지 않는다.")
    parser.add_argument("--comparison-mode", choices=("code_only", "model_routing"), help="--compare에 필요한 엄격 비교 모드")
    args = parser.parse_args(argv)
    if bool(args.compare) != bool(args.comparison_mode):
        parser.error("--compare와 --comparison-mode는 함께 지정해야 합니다")
    frozen_inputs = answer_by_id = None
    if args.answers:
        frozen_inputs, answer_by_id = load_benchmark(args.cases, args.answers)
        case = next((item for item in frozen_inputs["cases"] if item["id"] == args.case_id), None)
        if case is None:
            raise ValueError(f"알 수 없는 benchmark case: {args.case_id}")
    else:
        case = _case(args.cases, args.case_id)
    run_dir = args.run_dir
    report_path = run_dir / "final_report.md"
    if not report_path.is_file():
        report_path = run_dir / "report.md"
    if not report_path.is_file():
        raise FileNotFoundError("final_report.md 또는 report.md 없음")
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    if frozen_inputs:
        _validate_frozen_replay_run(run_dir, manifest, case)
    else:
        _validate_synthetic_run(run_dir, manifest, case)
    quality_path = run_dir / "quality.json"
    quality = json.loads(quality_path.read_text(encoding="utf-8")) if quality_path.is_file() else None
    model_config = json.loads(args.model_config)
    report = report_path.read_text(encoding="utf-8")
    submitted = submitted_hash = None
    if args.adjudications:
        submitted, submitted_hash = _adjudication_envelope(args.adjudications)
    result = evaluate(report, case, manifest.get("usage", []), _elapsed(manifest), quality, model_config,
                      benchmark_answer=(answer_by_id or {}).get(case["id"]), submitted_adjudications=submitted,
                      adjudication_report_sha256=submitted_hash,
                      runtime_metadata=runtime_metadata_from_manifest(manifest, frozen_inputs) if frozen_inputs else None)
    if args.compare:
        prior = json.loads(args.compare.read_text(encoding="utf-8"))
        if not isinstance(prior, dict):
            raise ValueError("--compare evaluation JSON은 객체여야 함")
        # 비교 결과가 current result 자체를 right로 보존하므로, 순환 참조 없이 저장할 얕은 스냅샷을 건넨다.
        result["comparison"] = compare(prior, dict(result), mode=args.comparison_mode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
