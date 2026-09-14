"""Private, plan-only follow-up measurement support.

This file is deliberately outside ``hprc``.  It never invokes a real backend;
``mock_preflight`` is the only execution helper and requires ``HPR_BACKEND=mock``.
The future approved runner must write observed manifests into records and call
``validate_followup_results`` rather than treating plan metadata as observed data.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch


REPO = next(parent for parent in Path(__file__).resolve().parents
            if (parent / 'hpr.py').is_file() and (parent / 'hprc').is_dir())
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from hprc.efficiency_study import _arm_config, _runtime_template  # private planning helpers
from hprc.evaluation import _stable, case_input_hash, runtime_metadata_from_manifest
from hprc.pipeline import run as pipeline_run
from hprc.policy_experiment import compare_policy
from hprc.study_runner import observed_controls
from hprc.token_policy import fingerprint
from hprc import pipeline


STUDIES = {
    "phase3_holdout_packet": {
        "cases": ("real-ko-missing", "real-en-long"), "split": "holdout",
        "candidate_arm": "packet", "changed_path": "efficiency.packet_inputs",
        "repetitions": 3, "common_caps": {},
    },
    "phase4_dev_evidence": {
        "cases": ("real-ko-table", "real-en-boundary"), "split": "dev",
        "candidate_arm": "evidence_selection", "changed_path": "efficiency.evidence_selection",
        "repetitions": 1,
        # The preflight established that defaults are a no-op for both dev cases.
        # These are common controls, not an arm-specific optimization.
        "common_caps": {"note_max_chars": 400, "excerpt_chars": 200},
    },
}
RUNTIME_KEYS = ("code_revision", "prompt_hashes", "benchmark_version", "frozen_at",
                "frozen_input_hash", "as_of", "role_assignments", "config_snapshot",
                "config_hash", "study_code_sha")
USAGE_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens", "reported_total_tokens",
              "unknowncalls", "retry_attempt_count", "failure_attempt_count")


def _sha(value: bytes | str) -> str:
    return hashlib.sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def _case_orders(case_index: int, repetitions: int) -> list[tuple[str, str]]:
    """Alternate order; for odd counts, reverse the excess first arm by case."""
    first = ("baseline", "candidate") if case_index % 2 == 0 else ("candidate", "baseline")
    second = tuple(reversed(first))
    return [first if index % 2 == 0 else second for index in range(repetitions)]


def _config(inputs: Path, case: dict, spec: dict, candidate: bool) -> dict:
    config = _arm_config(inputs, case, False)
    config.update(copy.deepcopy(spec["common_caps"]))
    # config.load reapplies a named preset after reading research/config.json.
    # A frozen lean-effective snapshot with a non-default cap must therefore run
    # as standard; its explicit light/models/budget values remain the lean policy.
    if spec["common_caps"]:
        config["preset"] = "standard"
    config["efficiency"].update({"packet_inputs": False, "evidence_selection": False,
                                  "reuse_analysis": False, "strategy": "standard"})
    if spec["changed_path"] == "efficiency.packet_inputs":
        config["efficiency"]["packet_inputs"] = candidate
    elif spec["changed_path"] == "efficiency.evidence_selection":
        config["efficiency"]["evidence_selection"] = candidate
    else:  # Keeps new studies explicit instead of accepting arbitrary config mutation.
        raise ValueError("unregistered efficiency comparison")
    return config


def build_followup_plan(inputs_path: Path, revision: str, study: str) -> dict:
    """Create a frozen plan without reading or evaluating a holdout answer."""
    if study not in STUDIES or not isinstance(inputs_path, Path) or not isinstance(revision, str) or not revision:
        raise ValueError("valid study, input path, and revision are required")
    spec = STUDIES[study]
    raw = inputs_path.read_bytes()
    fixture = json.loads(raw.decode("utf-8"))
    available = {row.get("id"): row for row in fixture.get("cases", []) if row.get("split") == spec["split"]}
    if set(spec["cases"]) - set(available):
        raise ValueError("frozen fixture does not contain the declared study cases")
    cases, runs = {}, []
    for case_index, case_id in enumerate(spec["cases"]):
        case = available[case_id]
        arms = {}
        for arm, candidate in (("baseline", False), (spec["candidate_arm"], True)):
            config = _config(inputs_path, case, spec, candidate)
            runtime = _runtime_template(case, fixture, revision, config)
            arms[arm] = {"config_snapshot": config, "config_hash": fingerprint(config),
                         "runtime_metadata": runtime}
        cases[case_id] = {"input_hash": case_input_hash(case), "format": arms["baseline"]["config_snapshot"]["report_format"],
                          "arms": arms}
        for repetition, order in enumerate(_case_orders(case_index, spec["repetitions"]), 1):
            for sequence, position in enumerate(order, 1):
                arm = spec["candidate_arm"] if position == "candidate" else position
                runs.append({"run_id": f"{case_id}-r{repetition}-{arm}", "case_id": case_id,
                             "arm": arm, "repetition": repetition, "sequence": sequence,
                             "input_hash": cases[case_id]["input_hash"],
                             "runtime_metadata": copy.deepcopy(arms[arm]["runtime_metadata"])})
    policy = {"changed_paths": [spec["changed_path"]], "parallel": False,
              "max_calls_per_run": 8, "max_retries": 0, "per_run_total_token_stop": 500_000,
              "study_total_token_stop": 500_000 * len(runs), "total_stop_is_hard_cap": False,
              "quality": {"external_judgment_required": True, "default": "unknown", "automatic_calls": False},
              "common_caps": copy.deepcopy(spec["common_caps"])}
    plan = {"study": study, "scope": "fixed_input_pilot_not_general_performance_claim",
            "fixture_path": str(inputs_path), "fixture_sha256": _sha(raw),
            "frozen_fixture_sha256": _sha(_stable(fixture)), "code_sha": revision,
            "benchmark_version": fixture["benchmark_version"], "frozen_at": fixture["frozen_at"],
            "cases": cases, "runs": runs, "planned_run_count": len(runs), "policy": policy,
            "policy_sha256": fingerprint(policy)}
    plan["plan_sha256"] = fingerprint(plan)
    return plan


def _record_errors(record: dict, expected: dict) -> list[str]:
    errors = [key for key in ("case_id", "arm", "input_hash") if record.get(key) != expected[key]]
    runtime = record.get("runtime_metadata")
    if not isinstance(runtime, dict):
        return errors + ["runtime_metadata"]
    errors.extend(key for key in RUNTIME_KEYS if runtime.get(key) != expected["runtime_metadata"].get(key))
    if runtime.get("runtime_consistent") is not True:
        errors.append("runtime_consistent")
    if record.get("backend") != "codex":
        errors.append("backend_not_codex")
    errors.extend(key for key in USAGE_KEYS if type(record.get(key)) is not int or record[key] < 0)
    if type(record.get("attempt_count")) is not int or not 1 <= record["attempt_count"] <= 8:
        errors.append("attempt_count")
    if not isinstance(record.get("observed_control_errors"), list) or record.get("observed_control_errors"):
        errors.append("observed_control_errors")
    if type(record.get("cached_input_tokens")) is int and type(record.get("input_tokens")) is int and record["cached_input_tokens"] > record["input_tokens"]:
        errors.append("cached_input_exceeds_input")
    if all(type(record.get(key)) is int for key in ("input_tokens", "output_tokens", "reported_total_tokens")) and record["reported_total_tokens"] != record["input_tokens"] + record["output_tokens"]:
        errors.append("reported_total_tokens_mismatch")
    if record.get("retry_attempt_count") != 0:
        errors.append("retry_policy_violation")
    if record.get("failure_attempt_count") != 0:
        errors.append("failure_policy_violation")
    return errors


def validate_followup_results(plan: dict, records: list[dict]) -> dict:
    """Generic fail-closed aggregation; it never approves a performance claim."""
    plan_copy = copy.deepcopy(plan); supplied = plan_copy.pop("plan_sha256", None)
    if not isinstance(plan, dict) or not isinstance(records, list) or supplied != fingerprint(plan_copy):
        raise ValueError("unmodified plan and record list are required")
    if plan.get("policy_sha256") != fingerprint(plan.get("policy")):
        raise ValueError("policy hash mismatch")
    expected = {row.get("run_id"): row for row in plan.get("runs", [])}
    if not expected or len(expected) != plan.get("planned_run_count"):
        raise ValueError("invalid generic plan runs")
    seen = {}
    for row in records:
        if not isinstance(row, dict) or row.get("run_id") not in expected:
            raise ValueError("unexpected record")
        if row["run_id"] in seen:
            raise ValueError("duplicate run record")
        seen[row["run_id"]] = row
    errors = {run_id: _record_errors(row, expected[run_id]) for run_id, row in seen.items()}
    errors = {run_id: value for run_id, value in errors.items() if value}
    pairs = []
    candidate_arm = next(arm for arm in next(iter(plan["cases"].values()))["arms"] if arm != "baseline")
    for case_id in plan["cases"]:
        for repetition in sorted({row["repetition"] for row in plan["runs"] if row["case_id"] == case_id}):
            ids = (f"{case_id}-r{repetition}-baseline", f"{case_id}-r{repetition}-{candidate_arm}")
            left, right = (seen.get(item) for item in ids)
            pair = {"case_id": case_id, "repetition": repetition, "run_ids": ids, "complete": False,
                    "paired_token_percent": None, "reason": "missing_run"}
            if left is None or right is None or errors.get(ids[0]) or errors.get(ids[1]):
                pair["reason"] = "control_mismatch" if left and right else "missing_run"; pairs.append(pair); continue
            try:
                compare_policy(left, right, plan["policy"]["changed_paths"])
            except ValueError as error:
                pair["reason"] = "policy_compare_failed:" + str(error); pairs.append(pair); continue
            if left.get("status") != "ok" or right.get("status") != "ok" or left["unknowncalls"] != 0 or right["unknowncalls"] != 0 or left["reported_total_tokens"] <= 0:
                pair["reason"] = "incomplete_usage_or_status"; pairs.append(pair); continue
            pair.update(complete=True, reason="complete", paired_token_percent=(right["reported_total_tokens"] - left["reported_total_tokens"]) / left["reported_total_tokens"] * 100)
            pairs.append(pair)
    totals = {key: sum(row.get(key, 0) if type(row.get(key)) is int else 0 for row in records)
              for key in ("reported_total_tokens", "input_tokens", "output_tokens", "cached_input_tokens", "unknowncalls", "attempt_count", "retry_attempt_count", "failure_attempt_count")}
    return {"study": plan["study"], "missing_run_ids": sorted(set(expected) - set(seen)), "control_errors": errors,
            "totals": totals, "pairs": pairs, "report_claim_permitted": False,
            "manual_review_required": True, "general_performance_claim_permitted": False,
            "quality_default": "unknown_external_judgment_required"}


def mock_preflight(inputs_path: Path, plan: dict) -> dict:
    """Observe prepared input bytes with mock only; no token/cost conclusion is made."""
    if os.environ.get("HPR_BACKEND") != "mock":
        raise RuntimeError("mock preflight requires HPR_BACKEND=mock")
    fixture = json.loads(inputs_path.read_text(encoding="utf-8"))
    cases = {row["id"]: row for row in fixture["cases"]}
    observations = []
    with tempfile.TemporaryDirectory(prefix="hpr-followup-preflight-") as temporary:
        root = Path(temporary)
        for run in plan["runs"]:
            # One observation per arm/case is enough; do not duplicate repetitions.
            if run["repetition"] != 1:
                continue
            case = cases[run["case_id"]]
            workspace = root / run["run_id"]
            (workspace / "research").mkdir(parents=True)
            (workspace / "research" / "config.json").write_text(json.dumps(run["runtime_metadata"]["config_snapshot"], ensure_ascii=False), encoding="utf-8")
            seen = []
            original = pipeline.run_step
            def record(step, prompt, schema, inputs, *args, **kwargs):
                seen.append({"step": step, "prepared_input_bytes": sum(len(value.encode("utf-8")) for value in inputs.values()),
                             "input_names": sorted(inputs),
                             "input_sha256": {name: _sha(value) for name, value in sorted(inputs.items())}})
                return original(step, prompt, schema, inputs, *args, **kwargs)
            with patch.object(pipeline, "run_step", side_effect=record):
                pipeline_run(workspace, case["prompt"], "light", run_id="trial", quiet=True, lang=case["lang"], preset=run["runtime_metadata"]["config_snapshot"]["preset"], max_calls=8,
                             budget=500_000, total_budget=500_000, no_search=True, replay_file=str(inputs_path), case_id=case["id"],
                             report_format=run["runtime_metadata"]["config_snapshot"]["report_format"], efficiency=run["runtime_metadata"]["config_snapshot"]["efficiency"])
            artifact = workspace / "research/runs/trial/evidence_selections.json"
            selected = json.loads(artifact.read_text(encoding="utf-8")) if artifact.exists() else []
            folder = workspace / "research/runs/trial"
            manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            control_errors, frozen_case, observed_backend = observed_controls(
                manifest, folder, case, run["runtime_metadata"]["role_assignments"], "mock")
            observed_runtime = runtime_metadata_from_manifest(manifest, fixture)
            observed_runtime["study_code_sha"] = plan["code_sha"]
            runtime_errors = [key for key in RUNTIME_KEYS if observed_runtime.get(key) != run["runtime_metadata"].get(key)]
            observations.append({"run_id": run["run_id"], "case_id": run["case_id"], "arm": run["arm"], "steps": seen,
                                 "evidence_selection_records": [{key: item.get(key) for key in ("source_id", "source_chars", "omitted_chars", "exact_spans", "truncated")} for item in selected]})
            observations[-1].update(observed_backend=observed_backend, observed_control_errors=control_errors,
                                    frozen_case_hash=case_input_hash(frozen_case) if frozen_case else None,
                                    runtime_metadata_errors=runtime_errors)
    comparisons = []
    for case_id in plan["cases"]:
        arms = {row["arm"]: row for row in observations if row["case_id"] == case_id}
        candidate = next(arm for arm in plan["cases"][case_id]["arms"] if arm != "baseline")
        baseline_steps = {row["step"]: row["input_sha256"] for row in arms["baseline"]["steps"]}
        candidate_steps = {row["step"]: row["input_sha256"] for row in arms[candidate]["steps"]}
        comparisons.append({"case_id": case_id, "candidate_arm": candidate,
                            "identical_step_input_sha256": baseline_steps == candidate_steps})
    return {"scope": "mock_preflight_prepared_bytes_and_content_hashes_not_actual_tokens_or_quality", "plan_sha256": plan["plan_sha256"],
            "observations": observations, "comparisons": comparisons,
            "all_paired_step_inputs_identical": all(row["identical_step_input_sha256"] for row in comparisons)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=REPO / "tests/fixtures/realistic_inputs.json")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--study", choices=sorted(STUDIES), required=True)
    parser.add_argument("--mock-preflight", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    plan = build_followup_plan(args.inputs.resolve(), args.revision, args.study)
    value = mock_preflight(args.inputs.resolve(), plan) if args.mock_preflight else plan
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
