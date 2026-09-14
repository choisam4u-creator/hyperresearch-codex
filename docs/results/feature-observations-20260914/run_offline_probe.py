#!/usr/bin/env python3
"""Phase 4 offline probe. Uses only HPR_BACKEND=mock and temporary workspaces.

This is an integration observation, not a token or quality benchmark. It runs the
normal replay pipeline with synthetic fixed inputs, then saves only compact,
deterministic artifact observations in this directory.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from copy import deepcopy
from pathlib import Path


REPO = next((parent for parent in Path(__file__).resolve().parents if (parent / "hpr.py").is_file()), None)
if REPO is None:
    raise RuntimeError("run this probe from within a hyperresearch-codex checkout")
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
FIXTURE = REPO / "tests" / "fixtures" / "benchmark_inputs.json"
OUTPUT = Path(__file__).with_name("offline-observations.json")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def make_fixture(path: Path, *, long_source: bool = False, change: bool = False, delete: bool = False) -> dict:
    data = read_json(FIXTURE)
    case = next(item for item in data["cases"] if item["id"] == "fact-ko-01")
    data["cases"] = [case]
    if long_source:
        case["sources"]["S1"] += (
            "\n\n측정 조건: Atlas는 읽기 전용 샌드박스에서 실행된다."
            + "\n\n무관한 부록 문장. " * 180
            + "\n\nCounter-evidence: this fixture does not establish production accuracy."
            + "\n\n무관한 끝 문장. " * 180
        )
    if change:
        case["sources"]["S1"] += "\n\n변경 기록: 새 조건이 추가됐다."
    if delete:
        case["sources"].pop("S2")
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return case


def call_steps(manifest: dict) -> list[str]:
    return [row.get("step") for row in manifest.get("usage", []) if isinstance(row, dict)]


def input_bytes(manifest: dict) -> dict:
    rows = manifest.get("input_profiles", [])
    return {
        row.get("step"): {
            "before_total_bytes": row.get("before", {}).get("total_bytes"),
            "prepared_total_bytes": row.get("prepared", {}).get("total_bytes"),
        }
        for row in rows if isinstance(row, dict)
    }


def run_case(root: Path, fixture: Path, run_id: str, *, efficiency: dict | None = None,
             update_from: str | None = None) -> tuple[Path, dict]:
    from hprc import pipeline
    case = read_json(fixture)["cases"][0]
    output = pipeline.run(root, case["prompt"], "light", run_id=run_id, quiet=True, lang=case["lang"],
                          replay_file=str(fixture), case_id=case["id"], efficiency=efficiency,
                          update_from=update_from)
    run_dir = output.parent
    return run_dir, read_json(run_dir / "manifest.json")


def artifact(run_dir: Path, manifest: dict) -> dict:
    report = (run_dir / "report.md").read_text(encoding="utf-8")
    result = {
        "steps": call_steps(manifest),
        "call_count": len(call_steps(manifest)),
        "input_profiles": input_bytes(manifest),
        "report_sha256": hashlib.sha256(report.encode("utf-8")).hexdigest(),
        "claims_sha256": hashlib.sha256((run_dir / "claims.json").read_bytes()).hexdigest(),
        "reuse_events": manifest.get("reuse_events", []),
    }
    for name in ("evidence_selections.json", "update_plan.json"):
        path = run_dir / name
        if path.is_file():
            result[name.removesuffix(".json")] = read_json(path)
    return result


def evidence_selection_probe() -> dict:
    with tempfile.TemporaryDirectory(prefix="hpr-offline-evidence-") as tmp:
        root = Path(tmp)
        (root / "research").mkdir()
        (root / "research" / "config.json").write_text(
            json.dumps({"note_max_chars": 850, "draft_note_chars": 850, "excerpt_chars": 850}), encoding="utf-8")
        fixture = root / "input.json"
        make_fixture(fixture, long_source=True)
        plain_dir, plain = run_case(root, fixture, "plain")
        selected_dir, selected = run_case(root, fixture, "selected", efficiency={"evidence_selection": True})
        return {
            "baseline": artifact(plain_dir, plain),
            "evidence_selection": artifact(selected_dir, selected),
            "observation_scope": "prepared input bytes and persisted selection artifacts only; mock usage is not real token usage",
        }


def exact_reuse_probe() -> dict:
    with tempfile.TemporaryDirectory(prefix="hpr-offline-reuse-") as tmp:
        root = Path(tmp); fixture = root / "input.json"; make_fixture(fixture)
        first_dir, first = run_case(root, fixture, "first", efficiency={"reuse_analysis": True})
        cache = root / "research" / "artifact-cache"
        first_cache = sorted(path.name for path in cache.glob("*.json")) if cache.is_dir() else []
        second_dir, second = run_case(root, fixture, "second", efficiency={"reuse_analysis": True})
        second_cache = sorted(path.name for path in cache.glob("*.json")) if cache.is_dir() else []
        return {
            "first_fill": artifact(first_dir, first), "second_exact": artifact(second_dir, second),
            "cache_entries_after_first": first_cache, "cache_entries_after_second": second_cache,
            "analyst_calls_first": call_steps(first).count("analyst"),
            "analyst_calls_second": call_steps(second).count("analyst"),
            "model_call_skip_observed": any(event.get("model_call_skipped") is True for event in second.get("reuse_events", [])),
            "observation_scope": "exact-key local cache behavior under mock; no real-model savings inferred",
        }


def update_probe(kind: str) -> dict:
    with tempfile.TemporaryDirectory(prefix=f"hpr-offline-update-{kind}-") as tmp:
        root = Path(tmp)
        before_fixture, after_fixture = root / "before.json", root / "after.json"
        make_fixture(before_fixture)
        make_fixture(after_fixture, change=kind == "changed", delete=kind == "deleted")
        before_dir, before = run_case(root, before_fixture, "before")
        after_dir, after = run_case(root, after_fixture, "after", update_from="before")
        update = read_json(after_dir / "update_plan.json")
        return {
            "before": artifact(before_dir, before), "after": artifact(after_dir, after),
            "update_mode": update.get("mode"), "requires_full_analysis": update.get("requires_full_analysis"),
            "source_change_counts": {name: len(update.get("changes", {}).get(name, []))
                                     for name in ("added", "removed", "changed_source", "unchanged", "unknown")},
            "analyst_update_calls": call_steps(after).count("analyst_update"),
            "analyst_calls": call_steps(after).count("analyst"),
            "observation_scope": "replay source snapshots and mock pipeline artifacts only",
        }


def main() -> None:
    os.environ["HPR_BACKEND"] = "mock"
    result = {
        "probe": "phase4_offline_feature_pilot_v1",
        "fixture": FIXTURE.relative_to(REPO).as_posix(),
        "fixture_sha256": hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),
        "backend": "mock",
        "network_or_real_model_calls": False,
        "evidence_selection": evidence_selection_probe(),
        "exact_analysis_reuse": exact_reuse_probe(),
        "updates": {kind: update_probe(kind) for kind in ("unchanged", "changed", "deleted")},
        "limits": [
            "Mock usage follows the fixture implementation and is not measured Codex token usage.",
            "The probe does not judge factual accuracy, report quality, or real elapsed time.",
            "Temporary workspaces are deleted after observation; this JSON is the retained evidence summary.",
        ],
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    main()
