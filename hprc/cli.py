"""hyperresearch-codex CLI 본체. `hpr` 명령(pip 설치)과 저장소의 hpr.py 가 같이 쓴다.
작업 폴더(ROOT)는 HPR_HOME 환경변수 → 현재 폴더에 research/ 또는 hprc/ 가 있으면 그 폴더 → 현재 폴더 순으로 정한다."""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import mcp_server, pipeline, vault

PKG = Path(__file__).resolve().parent
SKILL_SRC = PKG.parent / "skill/hyperresearch-codex/SKILL.md"


def find_root() -> Path:
    env = os.environ.get("HPR_HOME")
    if env:
        return Path(env).expanduser().resolve()
    cwd = Path.cwd()
    for cand in (cwd, *cwd.parents):
        if (cand / "research").is_dir() or (cand / "hprc").is_dir():
            return cand
    return cwd


ROOT = find_root()


def doctor() -> int:
    ok = True
    codex = shutil.which("codex")
    print("codex CLI:", codex or "없음 → https://developers.openai.com/codex 에서 설치"); ok &= bool(codex)
    if codex:
        print("  ", subprocess.run(["codex", "--version"], capture_output=True, text=True).stdout.strip())
        login = subprocess.run(["codex", "login", "status"], capture_output=True, text=True)
        print("   로그인:", (login.stdout or login.stderr).strip()[:80] or "확인 불가")
    print("작업 폴더(ROOT):", ROOT, "(HPR_HOME 으로 바꿀 수 있음)")
    try:
        import httpx; print("httpx:", httpx.__version__)
    except ImportError:
        print("httpx: 없음 (pip install httpx)"); ok = False
    import sqlite3
    try:
        sqlite3.connect(":memory:").execute("CREATE VIRTUAL TABLE t USING fts5(x)"); print("sqlite FTS5: OK")
    except sqlite3.OperationalError:
        print("sqlite FTS5: 없음"); ok = False
    try:
        import pypdf; print("pypdf:", pypdf.__version__, "(PDF 읽기 가능)")
    except ImportError:
        print("pypdf: 없음 → PDF 출처는 건너뜀 (선택: pip install pypdf)")
    print("research/:", (ROOT / "research").exists(), "(첫 실행 때 자동 생성)")
    return 0 if ok else 1


def status(run_id: str | None) -> None:
    runs = ROOT / "research" / "runs"
    ids = [run_id] if run_id else (sorted(p.name for p in runs.iterdir() if (p / "manifest.json").exists()) if runs.is_dir() else [])
    for rid in ids:
        m = json.loads((runs / rid / "manifest.json").read_text())
        tin = sum((u.get("usage") or {}).get("input_tokens", 0) for u in m["usage"])
        tout = sum((u.get("usage") or {}).get("output_tokens", 0) for u in m["usage"])
        secs = sum(u.get("seconds", 0) for u in m["usage"])
        from hprc.config import load
        from hprc.pipeline import estimate_cost
        cost = estimate_cost(m["usage"], load(ROOT)["budget"])
        print(f"{rid} | {m.get('tier','light')} | {m['prompt'][:45]} | 호출 {len(m['usage'])} · {secs:.0f}s · in {tin:,} (캐시 {cost['cached']:,}) / out {tout:,} · ≈${cost['usd_upper']}")
        print("   " + ", ".join(f"{s['name']}:{s['status']}" for s in m["steps"]))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("prompt"); r.add_argument("--tier", default="light", choices=["light", "full"])
    r.add_argument("--urls"); r.add_argument("--no-search", action="store_true"); r.add_argument("--scholar", action="store_true"); r.add_argument("--run-id")
    r.add_argument("--budget", type=int, help="누적 입력 토큰 상한. 넘으면 다음 단계 전에 멈춤"); r.add_argument("--quiet", action="store_true")
    r.add_argument("--dry-run", action="store_true", help="실행하지 않고 단계·예상 호출 수·예상 비용만 출력")
    r.add_argument("--lang", choices=["ko", "en"], help="프롬프트·보고서 언어 (기본 config lang=ko)")
    r.add_argument("--preset", choices=["standard", "lean"], help="lean: 구독 계정용 절약 프리셋(비평 2·초안 2·상한 축소)")
    u = sub.add_parser("usage"); u.add_argument("--days", type=int, default=30); u.add_argument("--json", action="store_true")
    u.add_argument("--backfill", action="store_true", help="장부 이전 실행들의 manifest 를 장부에 채움")
    s = sub.add_parser("resume"); s.add_argument("run_id"); s.add_argument("--budget", type=int); s.add_argument("--quiet", action="store_true")
    for parser in (r, s):
        parser.add_argument("--at", help="이 시각까지 기다렸다가 시작. 'HH:MM'(오늘/내일) 또는 'YYYY-MM-DD HH:MM'. 사용량 리셋 뒤 자동 재개용")
    ins = sub.add_parser("install-skill"); ins.add_argument("--yes", action="store_true", help="~/.codex/skills 에 실제로 복사")
    q = sub.add_parser("search"); q.add_argument("query"); q.add_argument("--limit", type=int, default=10)
    st = sub.add_parser("status"); st.add_argument("run_id", nargs="?")
    for name in ("sync", "doctor", "mcp", "mcp-config", "skill"):
        sub.add_parser(name)
    a = p.parse_args()
    if a.cmd == "doctor":
        return doctor()
    if a.cmd == "sync":
        print("색인한 노트:", vault.sync(ROOT)); return 0
    if a.cmd == "search":
        for row in vault.search(ROOT, a.query, a.limit):
            print(f"{row['id']:<4} {row['title'][:60]:<60} {row['snippet']}")
        return 0
    if a.cmd == "status":
        status(a.run_id); return 0
    if a.cmd == "usage":
        from hprc import ledger
        if a.backfill:
            print("장부에 추가:", ledger.backfill(ROOT), "건")
        summary = ledger.summarize(ROOT, a.days)
        if a.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2)); return 0
        t = summary["total"]
        print(f"최근 {a.days}일 실제 호출 {t['calls']}회 · 입력 {t['in']:,} (캐시 {t['cached']:,}) · 출력 {t['out']:,} · 모델 시간 {t['seconds']/60:.1f}분")
        print("--- 날짜별"); [print(f"  {d}: {v['calls']}회 · in {v['in']:,} · out {v['out']:,}") for d, v in summary["by_day"].items()]
        print("--- 실행별"); [print(f"  {r}: {v['tier']}/{v['lang']} · {v['calls']}회 · in {v['in']:,} · out {v['out']:,} · {v['seconds']/60:.1f}분") for r, v in summary["by_run"].items()]
        print("장부:", ledger.path(ROOT)); return 0
    if a.cmd == "mcp":
        mcp_server.serve(ROOT); return 0
    if a.cmd == "mcp-config":
        print(f'# ~/.codex/config.toml 에 추가 (사용자가 직접):\n[mcp_servers.hyperresearch]\ncommand = "python3"\nargs = ["{Path(sys.argv[0]).resolve()}", "mcp"]')
        return 0
    if a.cmd == "install-skill":
        src = SKILL_SRC; dst = Path.home() / ".codex/skills/hyperresearch-codex/SKILL.md"
        if not a.yes:
            print(f"복사 예정: {src} → {dst}\n실행하려면 --yes"); return 0
        dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy(src, dst); print("설치됨:", dst); return 0
    if a.cmd == "skill":
        print(f'# Codex 스킬 설치 (사용자가 직접):\nmkdir -p ~/.codex/skills/hyperresearch-codex && cp "{SKILL_SRC}" ~/.codex/skills/hyperresearch-codex/SKILL.md')
        return 0
    if a.cmd in ("run", "resume") and getattr(a, "at", None):
        import time as _t
        from datetime import datetime, timedelta
        now = datetime.now()
        try:
            target = datetime.strptime(a.at, "%Y-%m-%d %H:%M")
        except ValueError:
            target = datetime.combine(now.date(), datetime.strptime(a.at, "%H:%M").time())
            if target <= now:
                target += timedelta(days=1)
        wait = (target - now).total_seconds()
        print(f"{target:%Y-%m-%d %H:%M} 까지 {wait/60:.0f}분 대기 후 시작 (Ctrl+C 로 취소)", file=sys.stderr, flush=True)
        while wait > 0:
            _t.sleep(min(wait, 60)); wait -= 60
    if a.cmd == "run" and a.dry_run:
        from hprc.config import load
        cfg = load(ROOT, preset=a.preset, lang=a.lang); T = cfg[a.tier]
        if a.tier == "light":
            calls = 1 + 1 + 1 + len(T["critics"]) + 1 + 1                       # 정찰·분석·초안·비평·수정·인용검사
        else:
            calls = 1 + 1 + 1 + T["loci_max"] + T["drafts"] + 1 + len(T["critics"]) + 1 + 1 + 1  # + 지점·조사·종합·다듬기
        if a.no_search: calls -= 1
        est_in = {"light": 600_000, "full": 2_600_000}[a.tier]  # v0.3 실측 기준 대략값(정찰 포함)
        if cfg["preset"] == "lean":
            est_in = int(est_in * 0.6)
        print(f"tier {a.tier}: 단계 {pipeline.STEPS[a.tier]}\n예상 모델 호출 {calls}회, 출처 최대 {T['max_sources']}개\n"
              f"예상 입력 토큰(대략) {est_in:,} → 요금 상한 ≈${est_in/1e6*cfg['budget']['price_input_per_m']:.0f} (캐시 할인 미반영, 구독이면 사용량 한도 기준)\n"
              f"모델 {cfg['default_model']} · 언어 {cfg['lang']} · 프리셋 {cfg['preset']} · 예산 상한 {a.budget or cfg['budget']['max_input_tokens'] or cfg['budget']['default_by_tier'][a.tier]:,}")
        return 0
    try:
        if a.cmd == "run":
            out = pipeline.run(ROOT, a.prompt, a.tier, urls_file=a.urls, run_id=a.run_id, no_search=a.no_search, scholar=a.scholar,
                               quiet=a.quiet, budget=a.budget, lang=a.lang, preset=a.preset)
        else:
            mpath = ROOT / "research" / "runs" / a.run_id / "manifest.json"
            if not mpath.exists():
                print(f"BLOCKED: 실행 기록 없음: {a.run_id} (`hpr status` 로 목록 확인)", file=sys.stderr); return 2
            m = json.loads(mpath.read_text())
            out = pipeline.run(ROOT, m["prompt"], m.get("tier", "light"), run_id=a.run_id, quiet=a.quiet, budget=a.budget)
    except pipeline.Blocked as error:
        print("BLOCKED:", error, file=sys.stderr); return 2
    print("최종 보고서:", out)
    return 0


