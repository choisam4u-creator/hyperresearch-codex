#!/usr/bin/env python3
"""저장소 안에서 바로 쓰는 진입점. pip install . 뒤에는 어디서나 `hpr` 명령으로 같은 CLI 를 쓴다."""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("HPR_HOME", str(HERE))
from hprc.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
