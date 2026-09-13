"""사용량 장부: 모든 모델 호출을 research/usage-ledger.jsonl 에 한 줄씩 남긴다. 실행이 지워져도 장부는 남는다.
구독 계정은 달러가 아니라 '사용량 창'이 기준이므로, 날짜별·실행별 합계를 언제든 볼 수 있게 한다."""
import json
import threading
import time
from collections import defaultdict
from pathlib import Path


def path(root: Path) -> Path:
    return root / "research" / "usage-ledger.jsonl"


_LEDGER_LOCK = threading.Lock()


def _record_keys(row: dict) -> tuple[tuple, ...]:
    keys = []
    at = round(float(row.get("at") or row.get("ts", 0)), 3)
    keys.append(("legacy", row.get("run_id"), row.get("step"), row.get("attempt", 1), at))
    if row.get("record_id"):
        keys.append(("record_id", row.get("record_id")))
    return tuple(keys)


def _usage_known(row: dict) -> bool:
    if row.get("usage_known") is not None:
        return bool(row.get("usage_known"))
    return bool(row.get("usage")) or any(key in row for key in ("in", "cached", "out"))


def _prepare_record(record: dict) -> dict:
    out = dict(record)
    if out.get("ts") is None:
        out["ts"] = out.get("at") or time.time()
    out["date"] = time.strftime("%Y-%m-%d", time.localtime(out["ts"]))
    if not out.get("record_id"):
        out["record_id"] = f"{out.get('run_id', '')}:{out.get('step', '')}:{out.get('attempt', 1)}:{out['ts']:.6f}"
    return out


def append(root: Path, record: dict) -> None:
    p = path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    prepared = _prepare_record(record)
    with _LEDGER_LOCK:
        with p.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(prepared, ensure_ascii=False) + "\n")


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
    by_day, by_run = defaultdict(lambda: {"calls": 0, "in": 0, "cached": 0, "out": 0, "seconds": 0.0, "known_calls": 0, "unknown_calls": 0}), defaultdict(lambda: {"calls": 0, "in": 0, "cached": 0, "out": 0, "seconds": 0.0, "known_calls": 0, "unknown_calls": 0, "tier": "", "lang": "", "date": ""})
    total = {"calls": 0, "in": 0, "cached": 0, "out": 0, "seconds": 0.0, "known_calls": 0, "unknown_calls": 0}
    for r in rows(root):
        if r.get("ts", 0) < cutoff or (r.get("backend") == "mock" and not include_mock):
            continue
        known = _usage_known(r)
        for bucket in (by_day[r.get("date", "?")], by_run[r.get("run_id", "?")], total):
            bucket["calls"] += 1
            bucket["seconds"] += r.get("seconds", 0)
            if known:
                bucket["known_calls"] += 1
                bucket["in"] += r.get("in", 0); bucket["cached"] += r.get("cached", 0); bucket["out"] += r.get("out", 0)
            else:
                bucket["unknown_calls"] += 1
        by_run[r.get("run_id", "?")].update(tier=r.get("tier", ""), lang=r.get("lang", ""), date=r.get("date", ""))
    return {"days": days, "total": total, "by_day": dict(sorted(by_day.items())), "by_run": dict(by_run)}


def backfill(root: Path) -> int:
    """장부가 생기기 전 실행들의 manifest 를 읽어 장부에 채운다. 이미 있는 (run_id, step, at) 은 건너뛴다."""
    seen = set()
    for existing in rows(root):
        seen.update(_record_keys(existing))
    added = 0
    runs = root / "research" / "runs"
    for d in sorted(runs.iterdir()) if runs.is_dir() else []:
        mf = d / "manifest.json"
        if not mf.exists():
            continue
        m = json.loads(mf.read_text())
        for u in m.get("usage", []):
            at = u.get("at") or u.get("ts")
            if not at:
                continue
            run_id = d.name if u.get("run_id") is None else u.get("run_id")
            row_key = _record_keys({"run_id": run_id, "step": u.get("step"), "attempt": u.get("attempt", 1),
                                    "at": at, "usage": u.get("usage", {}), "record_id": u.get("record_id")})
            if set(row_key) & seen:
                continue
            usage = u.get("usage") or {}
            usage_known = _usage_known({"usage": usage, "usage_known": u.get("usage_known")})
            append(root, {"ts": at, "run_id": run_id, "step": u.get("step"), "tier": m.get("tier", ""), "lang": m.get("lang", "ko"),
                          "preset": m.get("preset", "standard"), "backend": u.get("backend"), "model": u.get("model"), "effort": u.get("effort"),
                          "in": usage.get("input_tokens", 0) if usage_known else 0, "cached": usage.get("cached_input_tokens", 0) if usage_known else 0,
                          "out": usage.get("output_tokens", 0) if usage_known else 0, "seconds": u.get("seconds", 0), "attempt": u.get("attempt", 1),
                          "record_id": u.get("record_id"), "usage_known": usage_known, "usage_unknown": not usage_known, "usage": usage if usage_known else {}, "backfilled": True})
            seen.update(row_key)
            added += 1
    return added
