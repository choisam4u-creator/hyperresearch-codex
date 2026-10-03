"""고정 평가 case 하나를 돌려 단계별 산출물 예시를 만든다(가짜 응답, 모델·네트워크 없음).

    HPR_BACKEND=mock python -m evals.walkthrough examples/pipeline-walkthrough [--case ko-bike-lanes]
"""
import argparse
import os
import re
import shutil
import tempfile
from pathlib import Path

from .run import load_cases, run_case

# 단계 순서대로 보여 줄 산출물
ARTIFACTS = ("frozen_input.json", "sources.json", "claims.json", "draft.md", "draft_gate.json", "findings.json",
             "citecheck.json", "report.md", "quality.json", "final_report.md")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out")
    parser.add_argument("--case", default="ko-bike-lanes")
    args = parser.parse_args(argv)
    os.environ["HPR_BACKEND"] = "mock"
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="hpr-walk-"))
    try:
        run_case(load_cases(args.case)[0], tmp)
        run_dir = tmp / args.case / "research/runs/eval"
        for name in ARTIFACTS:
            text = (run_dir / name).read_text(encoding="utf-8")
            # 임시 디렉터리 절대 경로를 저장소 상대 경로로 바꾼다(개인·임시 경로를 남기지 않는다).
            text = re.sub(re.escape(str(tmp / args.case)) + r"/?", "", text)
            (out / name).write_text(text, encoding="utf-8")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
