"""사람 라벨 대조 평가: 문장마다 단 정답(맞음/출처 불일치/미검증)과 보고서 표시를 비교한다.

    HPR_BACKEND=mock python -m evals.labeled [--case ID] [--verbose] [--json out.json]

evals/score.py 는 코드와 같은 발상(낱말·수치 대조)으로 채점해 천장 100에 닿았다. 이 평가는
점수기 규칙을 쓰지 않는다. evals/labeled/*.json 의 "labels"(문장 열쇠 → 정답)를 사람이 정하고,
최종 보고서에서 그 문장에 붙은 표시만 읽어 precision·recall 을 낸다.

- 정답 ok: 출처가 지지함(바꿔 말함·반올림·단위 환산 포함). 표시가 붙으면 오표시.
- 정답 mismatch: 인용했지만 원문과 뜻이 다름. unverified: 어느 출처에도 없음(인용 없음·판단 표시만).
- 예측: (출처 불일치)·(원문 추정치) → mismatch, (출처 없음) → unverified, 둘 다 없으면 ok.
라벨·case 를 고쳐 점수를 올리지 않는다. 고칠 때는 docs/QUALITY-LOG.md 에 이유를 적는다.
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

from .run import run_pipeline

CASES = Path(__file__).parent / "labeled"
MARKS = {"mismatch": ("(출처 불일치)", "(원문 추정치)", "(source mismatch)", "(source estimate)"),
         "unverified": ("(출처 없음)", "(no source)")}
_END = re.compile(r"[.!?。](?=\s|$)")
_TRAIL = re.compile(r"(?:\s*\((?:판단|출처 없음|출처 불일치|원문 추정치|judgment|no source|source mismatch|source estimate)\))+")


def load_cases(only: str | None = None) -> list[dict]:
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(CASES.glob("*.json"))]
    return [c for c in cases if only in (None, c["id"])]


def body(final: str) -> str:
    """사람이 읽는 보고서 본문만 남긴다(주장 표·출처 절 앞까지)."""
    for stop in ("\n## 출처", "\n## Sources"):
        if stop in final:
            final = final.split(stop, 1)[0]
    return final


def sentence_at(report: str, key: str) -> str | None:
    i = report.find(key)
    if i < 0:
        return None
    m = _END.search(report, i + len(key) - 1)
    end = m.end() if m else len(report)
    line_end = report.find("\n", i)
    if line_end >= 0 and line_end < end:
        end = line_end
    t = _TRAIL.match(report, end)
    return report[i:t.end() if t else end]


def predict(sentence: str) -> str:
    for label, marks in MARKS.items():
        if any(m in sentence for m in marks):
            return label
    return "ok"


def judge(case: dict, final: str | None) -> list[dict]:
    report = body(final or "")
    rows = []
    for lab in case["labels"]:
        sent = sentence_at(report, lab["key"])
        rows.append({**lab, "case": case["id"], "found": sent is not None,
                     "pred": predict(sent) if sent is not None else "missing", "sentence": sent})
    return rows


def metrics(rows: list[dict]) -> dict:
    pos = [r for r in rows if r["label"] != "ok"]
    neg = [r for r in rows if r["label"] == "ok"]
    flagged = [r for r in rows if r["pred"] not in ("ok", "missing")]
    tp = sum(1 for r in flagged if r["label"] != "ok")
    precision = tp / len(flagged) if flagged else 1.0
    recall = tp / len(pos) if pos else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    false_flag = sum(1 for r in neg if r["pred"] not in ("ok", "missing")) / len(neg) if neg else 0.0
    exact = sum(1 for r in rows if r["pred"] == r["label"]) / len(rows) if rows else 0.0
    return {"n": len(rows), "positives": len(pos), "precision": precision * 100, "recall": recall * 100,
            "f1": f1 * 100, "false_flag_rate": false_flag * 100, "exact_label": exact * 100,
            "missing": sum(1 for r in rows if r["pred"] == "missing")}


def by_tag(rows: list[dict]) -> list[tuple[str, str, int, int]]:
    """(유형, 정답, 문장 수, 맞게 판정한 수) — 결함 유형은 잡은 수, ok 유형은 표시 없이 둔 수."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["tag"], "ok" if r["label"] == "ok" else "flag")].append(r)
    out = []
    for (tag, kind), rs in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        good = sum(1 for r in rs if (r["pred"] == "ok") == (kind == "ok") and r["pred"] != "missing")
        out.append((tag, kind, len(rs), good))
    return out


def report_table(rows: list[dict]) -> str:
    m = metrics(rows)
    lines = ["| 지표 | 값 |", "|---|---|",
             f"| 결함 문장 recall(잡은 비율) | {m['recall']:.1f} |",
             f"| 표시 precision(표시 중 정답 결함) | {m['precision']:.1f} |",
             f"| F1 | **{m['f1']:.1f}** |",
             f"| 맞는 문장 오표시율(낮을수록 좋음) | {m['false_flag_rate']:.1f} |",
             f"| 라벨 정확 일치(ok/불일치/미검증) | {m['exact_label']:.1f} |",
             f"| 문장 수(결함) | {m['n']}({m['positives']}) |"]
    if m["missing"]:
        lines.append(f"| 보고서에서 못 찾은 문장 | {m['missing']} |")
    lines += ["", "| 유형 | 정답 | 문장 | 맞게 판정 |", "|---|---|---|---|"]
    lines += [f"| {t} | {'결함' if k == 'flag' else '맞음'} | {n} | {g} |" for t, k, n, g in by_tag(rows)]
    return "\n".join(lines)


def run_all(cases: list[dict]) -> list[dict]:
    tmp = Path(tempfile.mkdtemp(prefix="hpr-labeled-"))
    cwd = os.getcwd()
    rows: list[dict] = []
    try:
        for c in cases:
            final, _error, _sources, _calls = run_pipeline(c, tmp)
            rows += judge(c, final)
    finally:
        os.chdir(cwd)
        shutil.rmtree(tmp, ignore_errors=True)
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="사람 라벨 대조 품질 평가")
    parser.add_argument("--case")
    parser.add_argument("--json")
    parser.add_argument("--verbose", action="store_true", help="틀린 판정 문장 출력")
    args = parser.parse_args(argv)
    os.environ["HPR_BACKEND"] = "mock"
    cases = load_cases(args.case)
    if not cases:
        parser.error("라벨 case 없음")
    rows = run_all(cases)
    print(report_table(rows))
    if args.verbose:
        for r in rows:
            if r["pred"] != r["label"]:
                print(f"- [{r['case']}] 정답 {r['label']}·예측 {r['pred']} ({r['tag']}): {r['sentence'] or r['key']}")
    if args.json:
        Path(args.json).write_text(json.dumps({"metrics": metrics(rows), "rows": rows}, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
    return 1 if metrics(rows)["missing"] else 0


if __name__ == "__main__":
    sys.exit(main())
