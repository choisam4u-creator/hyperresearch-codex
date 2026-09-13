"""사용량 장부: 모든 모델 호출을 research/usage-ledger.jsonl 에 한 줄씩 남긴다. 실행이 지워져도 장부는 남는다.
구독 계정은 달러가 아니라 '사용량 창'이 기준이므로, 날짜별·실행별 합계를 언제든 볼 수 있게 한다."""
import json
import time
from collections import defaultdict
from pathlib import Path


def path(root: Path) -> Path:
    return root / "research" / "usage-ledger.jsonl"


def append(root: Path, record: dict) -> None:
    p = path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"ts": time.time(), "date": time.strftime("%Y-%m-%d"), **record}, ensure_ascii=False) + "\n")


def rows(root: Path) -> list[dict]:
    p = path(root)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def summarize(root: Path, days: int = 30, include_mock: bool = False) -> dict:
    cutoff = time.time() - days * 86400
    by_day, by_run = defaultdict(lambda: {"calls": 0, "in": 0, "cached": 0, "out": 0, "seconds": 0.0}), defaultdict(lambda: {"calls": 0, "in": 0, "cached": 0, "out": 0, "seconds": 0.0, "tier": "", "lang": "", "date": ""})
    total = {"calls": 0, "in": 0, "cached": 0, "out": 0, "seconds": 0.0}
    for r in rows(root):
        if r.get("ts", 0) < cutoff or (r.get("backend") == "mock" and not include_mock):
            continue
        for bucket in (by_day[r.get("date", "?")], by_run[r.get("run_id", "?")], total):
            bucket["calls"] += 1; bucket["in"] += r.get("in", 0); bucket["cached"] += r.get("cached", 0)
            bucket["out"] += r.get("out", 0); bucket["seconds"] += r.get("seconds", 0)
        by_run[r.get("run_id", "?")].update(tier=r.get("tier", ""), lang=r.get("lang", ""), date=r.get("date", ""))
    return {"days": days, "total": total, "by_day": dict(sorted(by_day.items())), "by_run": dict(by_run)}


def backfill(root: Path) -> int:
    """장부가 생기기 전 실행들의 manifest 를 읽어 장부에 채운다. 이미 있는 (run_id, step, at) 은 건너뛴다."""
    seen = {(r.get("run_id"), r.get("step"), round(r.get("ts", 0), 3)) for r in rows(root)}
    added = 0
    runs = root / "research" / "runs"
    for d in sorted(runs.iterdir()) if runs.is_dir() else []:
        mf = d / "manifest.json"
        if not mf.exists():
            continue
        m = json.loads(mf.read_text())
        for u in m.get("usage", []):
            key = (d.name, u.get("step"), round(u.get("at", 0), 3))
            if key in seen or not u.get("at"):
                continue
            usage = u.get("usage") or {}
            p = path(root); p.parent.mkdir(parents=True, exist_ok=True)
            with p.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"ts": u["at"], "date": time.strftime("%Y-%m-%d", time.localtime(u["at"])), "run_id": d.name,
                                         "step": u.get("step"), "tier": m.get("tier", ""), "lang": m.get("lang", "ko"), "preset": m.get("preset", "standard"),
                                         "backend": u.get("backend"), "model": u.get("model"), "effort": u.get("effort"),
                                         "in": usage.get("input_tokens", 0), "cached": usage.get("cached_input_tokens", 0), "out": usage.get("output_tokens", 0),
                                         "seconds": u.get("seconds", 0), "attempt": u.get("attempt", 1), "backfilled": True}, ensure_ascii=False) + "\n")
            seen.add(key); added += 1
    return added
