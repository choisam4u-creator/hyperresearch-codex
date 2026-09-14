"""고정 입력 효율 실험의 계획과 결과 집계.

이 모듈은 실행기나 품질 심판을 호출하지 않는다. 계획의 토큰 상한은 다음 호출을
멈추기 위한 정책값이며, 구독 사용량 또는 실제 청구의 hard cap이 아니다.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any

from .config import load
from .evaluation import _stable, case_input_hash
from .pipeline import runtime_hashes
from .policy_experiment import compare_policy
from .token_policy import fingerprint
from .workflow_policy import workflow_config


_CASES = ("real-ko-table", "real-en-boundary")
_ROLES = {
    "scout": {"model": "gpt-5.6-luna", "effort": "low"},
    "analyst": {"model": "gpt-5.6-terra", "effort": "low"},
    "loci": {"model": "gpt-5.6-sol", "effort": "medium"},
    "investigator": {"model": "gpt-5.6-sol", "effort": "medium"},
    "writer": {"model": "gpt-5.6-sol", "effort": "medium"},
    "synth": {"model": "gpt-5.6-sol", "effort": "medium"},
    "critic": {"model": "gpt-5.6-terra", "effort": "low"},
    "patcher": {"model": "gpt-5.6-terra", "effort": "low"},
    "citecheck": {"model": "gpt-6-astra", "effort": "low"},
    "polish": {"model": "gpt-5.6-luna", "effort": "low"},
}


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _arm_config(inputs_path: Path, case: dict, packet_inputs: bool) -> dict:
    """두 arm 사이에는 packet 입력 flag 하나만 다르게 둔다."""
    report_format = "facts" if case["id"] == "real-ko-table" else "comparison"
    # 실제 실행은 lean 단계 구성에 이전 economy 역할 배정만 고정해 쓴다. 매번 새
    # 임시 root를 쓰므로 호출자의 research/config.json은 계획에 섞이지 않는다.
    with tempfile.TemporaryDirectory(prefix="hpr-efficiency-study-") as root:
        config = load(Path(root), preset="lean", lang=case["lang"])
    config["models"] = copy.deepcopy(_ROLES)
    config["routing"]["enabled"] = False
    config["verification"].update({"semantic": False, "recheck_changed": False})
    config["reuse"]["enabled"] = False
    config["gap_fetch"]["enabled"] = False
    config["report_format"] = report_format
    config["light"]["target_words"] = 700
    config["budget"].update({"max_total_tokens": 500_000, "max_input_tokens": 500_000,
                             "max_model_calls": 8, "max_retries": 0, "reserve_input": True,
                             "stop_on_unknown": True})
    config["efficiency"].update({"packet_inputs": packet_inputs, "evidence_selection": False,
                                 "reuse_analysis": False, "strategy": "standard"})
    config, _ = workflow_config(config, "light")
    return config


def _runtime_template(case: dict, fixture: dict, revision: str, config: dict) -> dict:
    runtime = runtime_hashes(case["lang"])
    return {
        "runtime_consistent": True,
        # runtime_metadata_from_manifest과 같은 코드·프롬프트·전체 frozen fixture
        # 결속 형식이다. revision은 runner가 HEAD와 대조할 study_code_sha로 남긴다.
        "code_revision": runtime["code_hash"],
        "prompt_hashes": runtime["prompt_hash"],
        "benchmark_version": fixture["benchmark_version"],
        "frozen_at": fixture["frozen_at"], "frozen_input_hash": _sha256_text(_stable(fixture)),
        "as_of": case.get("baseline_time"),
        "role_assignments": copy.deepcopy(_ROLES),
        "config_snapshot": copy.deepcopy(config),
        "config_hash": fingerprint(config),
        "study_code_sha": revision,
    }


def build_plan(inputs_path: Path, revision: str, repetitions: int = 2) -> dict:
    """두 dev case의 packet-inputs 단독 대조 8회 계획을 만든다.

    입력 fixture와 revision은 계획 시점에 해시로 결속한다. 이 함수는 모델·심판을
    호출하지 않으며, 작성한 plan은 실행 허가나 품질 통과를 뜻하지 않는다.
    """
    if not isinstance(inputs_path, Path):
        raise TypeError("inputs_path는 Path여야 합니다")
    if not isinstance(revision, str) or not revision.strip():
        raise ValueError("code revision이 필요합니다")
    if type(repetitions) is not int or repetitions not in {1, 2}:
        raise ValueError("repetitions는 승인된 1회 또는 기본 2회여야 합니다")
    raw = inputs_path.read_bytes()
    fixture = json.loads(raw.decode("utf-8"))
    cases = {case.get("id"): case for case in fixture.get("cases", []) if case.get("split") == "dev"}
    if set(_CASES) - set(cases):
        raise ValueError("필요한 dev 고정 입력 case가 없습니다")
    selected = [cases[case_id] for case_id in _CASES]
    plan_cases = {}
    runs = []
    orders = (("baseline", "packet"), ("packet", "baseline"))
    for case_index, case in enumerate(selected):
        arms = {}
        for arm, enabled in (("baseline", False), ("packet", True)):
            config = _arm_config(inputs_path, case, enabled)
            arms[arm] = {"config_snapshot": config, "config_hash": fingerprint(config),
                         "runtime_metadata": _runtime_template(case, fixture, revision, config)}
        plan_cases[case["id"]] = {
            "input_hash": case_input_hash(case),
            "prompt_sha256": _sha256_text(case["prompt"]),
            "format": arms["baseline"]["config_snapshot"]["report_format"],
            "arms": arms,
        }
        # 1회 소규모 계획도 두 case가 서로 반대 순서를 가져 순서 효과를 한쪽
        # arm에만 몰지 않는다. 기본 2회는 각 case 내부에서 두 순서를 모두 쓴다.
        case_orders = orders if repetitions == 2 else (orders[case_index % 2],)
        for repetition, arm_order in enumerate(case_orders, 1):
            for sequence, arm in enumerate(arm_order, 1):
                runs.append({
                    "run_id": f"{case['id']}-r{repetition}-{arm}", "case_id": case["id"],
                    "arm": arm, "repetition": repetition, "sequence": sequence,
                    "input_hash": plan_cases[case["id"]]["input_hash"],
                    "runtime_metadata": copy.deepcopy(arms[arm]["runtime_metadata"]),
                })
    policy = {
        "comparison": "baseline_vs_packet_inputs_only", "changed_paths": ["efficiency.packet_inputs"],
        "parallel": False, "repetitions_per_case": repetitions,
        "counterbalance": (["baseline_then_packet", "packet_then_baseline"] if repetitions == 2
                           else ["real-ko-table:baseline_then_packet", "real-en-boundary:packet_then_baseline"]),
        "max_calls_per_run": 8, "max_retries": 0, "per_run_total_token_stop": 500_000,
        "study_total_token_stop": 500_000 * len(runs), "total_stop_is_hard_cap": False,
        "quality": {"external_judgment_required": True, "default": "unknown", "automatic_calls": False},
    }
    plan = {
        "study": "efficiency_packet_inputs_pilot_v1", "scope": "fixed_input_dev_pilot_not_general_performance_claim",
        "fixture_path": str(inputs_path), "fixture_sha256": _sha256_bytes(raw),
        "frozen_fixture_sha256": _sha256_text(_stable(fixture)), "code_sha": revision,
        "benchmark_version": fixture["benchmark_version"], "frozen_at": fixture["frozen_at"],
        "role_assignment_policy": "frozen_previous_lean_economy_assignment", "role_assignments": copy.deepcopy(_ROLES),
        "policy": policy, "policy_sha256": fingerprint(policy), "cases": plan_cases, "runs": runs,
        "planned_run_count": len(runs),
    }
    plan["plan_sha256"] = fingerprint(plan)
    return plan


def _external_quality(record: dict) -> bool | None:
    """외부 품질 판정은 보고서 해시와 결속된 strict bool만 통과시킨다."""
    value = record.get("externally_judged_quality")
    if value is False:
        return False
    if value is not True:
        return None
    report_hash, adjudication_hash = record.get("report_sha256"), record.get("adjudication_report_sha256")
    if (isinstance(report_hash, str) and report_hash and report_hash == adjudication_hash
            and record.get("adjudication_report_bound") is True):
        return True
    return None


def _usage_complete(record: dict) -> bool:
    return type(record.get("unknowncalls")) is int and record["unknowncalls"] == 0


def _record_control_errors(record: dict, expected: dict, plan: dict) -> list[str]:
    errors = []
    if record.get("case_id") != expected["case_id"]:
        errors.append("case_id")
    if record.get("arm") != expected["arm"]:
        errors.append("arm")
    if record.get("input_hash") != expected["input_hash"]:
        errors.append("input_hash")
    runtime = record.get("runtime_metadata")
    planned = expected["runtime_metadata"]
    if not isinstance(runtime, dict):
        return errors + ["runtime_metadata"]
    for key in ("code_revision", "prompt_hashes", "benchmark_version", "frozen_at", "frozen_input_hash", "as_of", "role_assignments", "config_snapshot", "config_hash", "study_code_sha"):
        if runtime.get(key) != planned.get(key):
            errors.append(key)
    if runtime.get("runtime_consistent") is not True:
        errors.append("runtime_consistent")
    if record.get("backend") != "codex":
        errors.append("backend_not_codex")
    for key in ("input_tokens", "cached_input_tokens", "output_tokens", "reported_total_tokens",
                "unknowncalls", "retry_attempt_count", "failure_attempt_count"):
        if type(record.get(key)) is not int or record[key] < 0:
            errors.append(key)
    attempt_count = record.get("attempt_count")
    if type(attempt_count) is not int or not 1 <= attempt_count <= 8:
        errors.append("attempt_count")
    observed = record.get("observed_control_errors")
    if not isinstance(observed, list) or observed:
        errors.append("observed_control_errors")
    if type(record.get("input_tokens")) is int and type(record.get("cached_input_tokens")) is int:
        if record["cached_input_tokens"] > record["input_tokens"]:
            errors.append("cached_input_exceeds_input")
    if all(type(record.get(key)) is int for key in ("input_tokens", "output_tokens", "reported_total_tokens")):
        if record["reported_total_tokens"] != record["input_tokens"] + record["output_tokens"]:
            errors.append("reported_total_tokens_mismatch")
    if record.get("retry_attempt_count") != 0:
        errors.append("retry_policy_violation")
    if record.get("failure_attempt_count") != 0:
        errors.append("failure_policy_violation")
    return errors


def _comparison_record(record: dict) -> dict:
    """정책 비교에는 외부 판정만 품질 flag로 전달해 자동 통과를 막는다."""
    value = copy.deepcopy(record)
    value["quality_qualified"] = _external_quality(record)
    return value


def validate_results(plan: dict, records: list[dict]) -> dict:
    """실행 기록을 합산한다. 누락·미측정·품질 미확정은 성과 주장으로 바꾸지 않는다."""
    if not isinstance(plan, dict) or not isinstance(records, list):
        raise TypeError("plan과 records 형식이 맞지 않습니다")
    supplied_plan_hash = plan.get("plan_sha256")
    plan_without_hash = copy.deepcopy(plan)
    plan_without_hash.pop("plan_sha256", None)
    if not isinstance(supplied_plan_hash, str) or supplied_plan_hash != fingerprint(plan_without_hash):
        raise ValueError("계획 해시가 없거나 변경되었습니다")
    if plan.get("policy_sha256") != fingerprint(plan.get("policy")):
        raise ValueError("정책 해시가 없거나 변경되었습니다")
    expected = {run["run_id"]: run for run in plan.get("runs", [])}
    repetitions = (plan.get("policy") or {}).get("repetitions_per_case")
    expected_count = len(_CASES) * 2 * repetitions if type(repetitions) is int else 0
    if repetitions not in {1, 2} or len(expected) != expected_count or plan.get("planned_run_count") != expected_count:
        raise ValueError("승인된 4회 또는 8회 고정 계획이 필요합니다")
    by_id: dict[str, dict] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("run_id"), str):
            raise ValueError("run_id가 있는 기록만 집계할 수 있습니다")
        run_id = record["run_id"]
        if run_id not in expected:
            raise ValueError(f"계획 밖 실행: {run_id}")
        if run_id in by_id:
            raise ValueError(f"중복 실행 기록: {run_id}")
        by_id[run_id] = record
    missing = sorted(set(expected) - set(by_id))
    controls = {run_id: _record_control_errors(record, expected[run_id], plan) for run_id, record in by_id.items()}
    control_errors = {run_id: errors for run_id, errors in controls.items() if errors}
    totals = {key: sum((record.get(key) if isinstance(record.get(key), int) else 0) for record in records)
              for key in ("reported_total_tokens", "unknowncalls", "attempt_count", "retry_attempt_count", "failure_attempt_count")}
    pairs = []
    for case_id in _CASES:
        for repetition in range(1, repetitions + 1):
            baseline_id = f"{case_id}-r{repetition}-baseline"
            packet_id = f"{case_id}-r{repetition}-packet"
            baseline, packet = by_id.get(baseline_id), by_id.get(packet_id)
            item: dict[str, Any] = {"case_id": case_id, "repetition": repetition,
                                    "baseline_run_id": baseline_id, "packet_run_id": packet_id,
                                    "complete": False, "paired_token_percent": None, "quality_preserved": None}
            if baseline is None or packet is None:
                item["reason"] = "missing_run"; pairs.append(item); continue
            if controls.get(baseline_id) or controls.get(packet_id):
                item["reason"] = "control_mismatch"; pairs.append(item); continue
            try:
                comparison = compare_policy(_comparison_record(baseline), _comparison_record(packet),
                                            ["efficiency.packet_inputs"])
            except ValueError as error:
                item["reason"] = f"policy_compare_failed:{error}"; pairs.append(item); continue
            item["quality_preserved"] = comparison["quality_preserved"]
            if not (_usage_complete(baseline) and _usage_complete(packet)):
                item["reason"] = "unknown_usage"; pairs.append(item); continue
            if baseline.get("status") != "ok" or packet.get("status") != "ok":
                item["reason"] = "failed_run"; pairs.append(item); continue
            baseline_tokens, packet_tokens = baseline.get("reported_total_tokens"), packet.get("reported_total_tokens")
            if not isinstance(baseline_tokens, int) or baseline_tokens <= 0 or not isinstance(packet_tokens, int):
                item["reason"] = "token_total_missing"; pairs.append(item); continue
            item["complete"] = True
            item["paired_token_percent"] = (packet_tokens - baseline_tokens) / baseline_tokens * 100
            item["reason"] = "complete"
            pairs.append(item)
    all_pairs_qualify = len(pairs) == len(_CASES) * repetitions and all(pair["complete"] and pair["quality_preserved"] is True for pair in pairs)
    complete = not missing and not control_errors and len(records) == expected_count
    unknown_usage = totals["unknowncalls"] > 0 or any(not _usage_complete(record) for record in records)
    failed = any(record.get("status") != "ok" for record in records)
    non_codex = any("backend_not_codex" in errors for errors in control_errors.values())
    # 외부 판정 envelope가 있어도 이 순수 집계기는 판정자를 인증하거나 사람이
    # 검토한 사실을 증명하지 못한다. 자동 성과 선언은 항상 별도 수동 검토로 남긴다.
    automatic_eligibility = bool(complete and all_pairs_qualify and not unknown_usage and not failed and not non_codex)
    report_claim_permitted = False
    return {
        "study": plan.get("study"), "scope": "fixed_input_dev_pilot_not_general_performance_claim",
        "planned_run_count": expected_count, "submitted_run_count": len(records), "missing_run_ids": missing,
        "control_errors": control_errors, "totals": totals, "pairs": pairs,
        "all_pairs_qualify": all_pairs_qualify, "unknown_usage": unknown_usage,
        "report_claim_permitted": report_claim_permitted,
        "automatic_eligibility": automatic_eligibility,
        "manual_review_required": True,
        "general_performance_claim_permitted": False,
        "quality_default": "unknown_external_judgment_required",
        "claim_note": "Pilot-only result. No general performance claim is permitted.",
    }


__all__ = ["build_plan", "validate_results"]
