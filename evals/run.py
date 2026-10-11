"""고정 질문을 실제 파이프라인(가짜 백엔드)으로 돌려 품질 점수 표를 낸다.

    HPR_BACKEND=mock python -m evals.run [--json out.json] [--case ID] [--min-total N]

모델 단계 응답은 evals/cases/*.json 의 "responses"(단계 이름 → 시도별 응답 목록)를
쓰고, 없는 단계는 hprc.mock 의 기계적 응답을 쓴다. 단계 응답을 바꾸면 점수 기준선이
바뀌므로 바꾼 이유를 docs/QUALITY-LOG.md 에 적는다.
"""
import argparse
import copy
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hprc import pipeline  # noqa: E402
from hprc.mock import mock_backend  # noqa: E402
from hprc.vault import note_body  # noqa: E402

from .score import LABELS, METRICS, score  # noqa: E402

CASES = Path(__file__).parent / "cases"
INPUT_KEYS = ("id", "lang", "prompt", "baseline_time", "sources")
# 비평·다듬기는 기록이 없으면 '지적 없음'으로 둔다. hprc.mock 의 비평은 시험용 장치라 품질 평가를 흐린다.
QUIET_STEPS = {"critic_": {"findings": []}, "polish": {"hunks": [], "skipped": []}}


def load_cases(only: str | None = None) -> list[dict]:
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(CASES.glob("*.json"))]
    return [c for c in cases if only in (None, c["id"])]


def fixture_backend(case: dict, calls: list[str]):
    seen: dict[str, int] = {}
    recorded = case.get("responses", {})

    def backend(step: str, prompt: str, inputs: dict) -> dict:
        calls.append(step)
        if step in recorded:
            attempts = recorded[step]
            i = seen.get(step, 0)
            seen[step] = i + 1
            return copy.deepcopy(attempts[min(i, len(attempts) - 1)])
        for prefix, response in QUIET_STEPS.items():
            if step.startswith(prefix):
                return copy.deepcopy(response)
        return mock_backend(step, prompt, inputs)
    return backend


def run_pipeline(case: dict, workdir: Path) -> tuple[str | None, str, dict, list[str]]:
    """case 하나를 파이프라인으로 돌려 (최종 보고서, 막힌 이유, 출처, 단계 호출)을 돌려준다."""
    proj = workdir / case["id"]
    (proj / "research").mkdir(parents=True)
    inputs = proj / "frozen_inputs.json"
    inputs.write_text(json.dumps({"benchmark_version": "evals-v1", "frozen_at": "2026-10-03T00:00:00Z",
                                  "cases": [{k: case[k] for k in INPUT_KEYS}]}, ensure_ascii=False), encoding="utf-8")
    calls: list[str] = []
    final, error = None, ""
    with mock.patch.object(pipeline, "mock_backend", fixture_backend(case, calls)):
        try:
            out = pipeline.run(proj, case["prompt"], "light", run_id="eval", replay_file=str(inputs), case_id=case["id"],
                               quiet=True, lang=case["lang"])
            final = out.read_text(encoding="utf-8")
        except pipeline.Blocked as exc:
            error = str(exc)[:200]
    sources = {}
    src_file = proj / "research/runs/eval/sources.json"
    if src_file.exists():
        for s in json.loads(src_file.read_text(encoding="utf-8"))["sources"]:
            sources[s["id"]] = {"text": note_body(Path(s["path"])), "cluster": s.get("cluster", s["id"])}
    return final, error, sources, calls


def run_case(case: dict, workdir: Path) -> dict:
    final, error, sources, calls = run_pipeline(case, workdir)
    result = score(final, case["lang"], case["prompt"], sources)
    result.update(id=case["id"], error=error, calls=calls)
    return result


def table(results: list[dict]) -> str:
    head = "| case | " + " | ".join(LABELS[m] for m in METRICS) + " |"
    lines = [head, "|---" * (len(METRICS) + 1) + "|"]
    for r in results:
        lines.append(f"| {r['id']}{' (실패)' if r['failed'] else ''} | " + " | ".join(f"{r[m]:.1f}" for m in METRICS) + " |")
    avg = {m: sum(r[m] for r in results) / len(results) for m in METRICS}
    lines.append("| **평균** | " + " | ".join(f"**{avg[m]:.1f}**" for m in METRICS) + " |")
    lines.append(f"\n종합 평균: {sum(avg.values()) / len(avg):.1f}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="hyperresearch-codex 오프라인 품질 평가")
    parser.add_argument("--case")
    parser.add_argument("--json", help="결과 JSON 저장 경로")
    parser.add_argument("--min-total", type=float, help="종합 평균이 이보다 낮으면 종료 코드 1")
    parser.add_argument("--verbose", action="store_true", help="항목별 감점 근거 출력")
    args = parser.parse_args(argv)
    os.environ["HPR_BACKEND"] = "mock"
    cases = load_cases(args.case)
    if not cases:
        parser.error("평가 case 없음")
    tmp = Path(tempfile.mkdtemp(prefix="hpr-evals-"))
    cwd = os.getcwd()
    try:
        results = [run_case(c, tmp) for c in cases]
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp, ignore_errors=True)
    print(table(results))
    if args.verbose:
        for r in results:
            print(f"\n## {r['id']}" + (f" — 실패: {r['error']}" if r["error"] else ""))
            for key, value in r["detail"].items():
                if value:
                    print(f"- {key}: {value}")
    if args.json:
        Path(args.json).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(sum(r[m] for r in results) / len(results) for m in METRICS) / len(METRICS)
    return 1 if args.min_total is not None and total < args.min_total else 0


if __name__ == "__main__":
    sys.exit(main())
