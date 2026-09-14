"""고정 benchmark 입력을 네트워크 없이 fetch 단계용 페이지로 바꾼다."""
import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path

from .evaluation import frozen_input_export


_SOURCE_ID = re.compile(r"S([1-9][0-9]*)$")
_BASELINE_TIME = re.compile(r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}Z)?$")


def _valid_baseline_time(value: str) -> bool:
    if not _BASELINE_TIME.fullmatch(value):
        return False
    try:
        if "T" in value:
            datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
        else:
            date.fromisoformat(value)
    except ValueError:
        return False
    return True


def load_case(path: Path, case_id: str) -> dict:
    """동결 입력에서 하나의 재생 case를 엄격히 읽는다.

    정답은 이 모듈의 입력이 아니며, 이 함수는 nested answer/expected 키도
    `frozen_input_export`에서 거부한다.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    frozen = frozen_input_export(data)
    matches = [case for case in frozen["cases"] if case.get("id") == case_id]
    if not matches:
        raise ValueError(f"알 수 없는 replay case: {case_id}")
    case = matches[0]
    if not isinstance(case.get("prompt"), str) or not case["prompt"].strip():
        raise ValueError("replay case prompt는 비어 있지 않은 문자열이어야 함")
    if case.get("lang") not in {"ko", "en"}:
        raise ValueError("replay case lang은 ko 또는 en이어야 함")
    baseline_time = case.get("baseline_time")
    if not isinstance(baseline_time, str) or not _valid_baseline_time(baseline_time):
        raise ValueError("replay case baseline_time은 ISO 날짜 또는 UTC 시각이어야 함")
    sources = case.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("replay case sources는 비어 있지 않은 객체여야 함")
    ids = []
    for source_id, text in sources.items():
        match = _SOURCE_ID.fullmatch(source_id) if isinstance(source_id, str) else None
        if not match or not isinstance(text, str) or not text:
            raise ValueError("replay source는 S1..Sn 연속 id와 비어 있지 않은 문자열 본문이어야 함")
        ids.append(int(match.group(1)))
    if sorted(ids) != list(range(1, len(ids) + 1)):
        raise ValueError("replay source id는 S1..Sn으로 연속되어야 함")
    return case


def pages_for_case(case: dict) -> list[dict]:
    """재생 case의 원문을 fetch-compatible 페이지로 반환한다.

    body는 변환하지 않으며, sha256은 원문 UTF-8 바이트의 해시다. 같은 본문이
    있어도 source 위치별 URL이 달라 후속 source id 할당에서 충돌하지 않는다.
    """
    sources = case["sources"]
    pages = []
    for source_id in sorted(sources, key=lambda value: int(value[1:])):
        text = sources[source_id]
        url = f"https://fixture.invalid/replay/{case['id']}/{source_id}"
        pages.append({"url": url, "final_url": url, "title": f"replay {case['id']} {source_id}",
                      "domain": "fixture.invalid", "via": "benchmark_replay", "official": False,
                      "published": "", "published_source": "", "modified": "", "modified_source": "",
                      "canonical": url, "status": "200", "text": text, "error": "",
                      "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                      "fetched_at": case["baseline_time"]})
    return pages
