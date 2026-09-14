"""hyperresearch-codex CLI 본체. `hpr` 명령(pip 설치)과 저장소의 hpr.py 가 같이 쓴다.
작업 폴더(ROOT)는 HPR_HOME 환경변수 → 현재 폴더에 research/ 또는 hprc/ 가 있으면 그 폴더 → 현재 폴더 순으로 정한다."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from importlib import resources
from pathlib import Path

from . import mcp_server, pipeline, vault
from .run_paths import InvalidRunId, run_directory, runs_directory

PKG = Path(__file__).resolve().parent
SKILL_SRC = PKG.parent / "skill/hyperresearch-codex/SKILL.md"
SKILL_RESOURCE = resources.files("hprc").joinpath("_skill", "SKILL.md")
TESTED_CODEX_VERSION = "0.153.4"
CODEX_DOCTOR_TIMEOUT = 3
_LOGIN_SUCCESS = re.compile(r"(?im)^\s*(?:you are\s+)?(logged in|authenticated)\b")
_LOGIN_FAIL = re.compile(r"(?im)^\s*(?:you are\s+not\s+logged\s+in|not\s+logged\s+in|please\s+login|login\s+required|authentication\s+required|unauthenticated)")


def _run_codex_command(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=CODEX_DOCTOR_TIMEOUT)


def _extract_version(text: str) -> str:
    m = re.search(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?", text or "")
    return m.group(0) if m else ""


def _clean_output(cp: subprocess.CompletedProcess[str]) -> str:
    return ((cp.stdout or "").strip() or (cp.stderr or "").strip())


def _login_status(raw: str, return_code: int) -> tuple[bool, str]:
    """로그인 결과를 종료코드 + 메시지로 판정한다."""
    if return_code != 0:
        return False, f"종료코드 {return_code}"
    text = (raw or "").lower()
    if not text:
        return False, "출력 없음"
    if _LOGIN_FAIL.search(text):
        return False, "로그인 필요"
    if _LOGIN_SUCCESS.search(text):
        return True, "로그인됨"
    return False, f"판독불가: {raw[:80] if raw else '(빈 출력)'}"


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


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("양의 정수여야 합니다") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("0보다 커야 합니다")
    return parsed


def _skill_source():
    """소스 checkout 또는 설치된 package resource에서 스킬을 읽는다."""
    return SKILL_SRC if SKILL_SRC.is_file() else SKILL_RESOURCE


def _copy_skill(src, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(src, Path):
        shutil.copyfile(src, dst)
    else:
        with src.open("rb") as stream, dst.open("wb") as target:
            shutil.copyfileobj(stream, target)


def doctor() -> int:
    ok = True
    codex = shutil.which("codex")
    print("codex CLI:", codex or "없음 → https://developers.openai.com/codex 에서 설치"); ok &= bool(codex)
    if codex:
        try:
            version = _run_codex_command(["codex", "--version"])
            version_output = _clean_output(version)
            print("  codex --version:", version_output or "(빈 출력)")
            if version.returncode != 0:
                print("  경고: codex --version 종료코드", version.returncode)
                ok = False
            else:
                parsed = _extract_version(version_output)
                if not parsed:
                    print("  경고: codex 버전 문자열을 읽지 못했습니다.")
                    ok = False
                elif parsed == TESTED_CODEX_VERSION:
                    print(f"  테스트 기준 버전 {TESTED_CODEX_VERSION}과 일치")
                else:
                    print(f"  경고: 테스트 기준 버전({TESTED_CODEX_VERSION})과 다름 → 실제: {parsed}")
        except subprocess.TimeoutExpired:
            print(f"  경고: codex --version 호출 타임아웃 (>{CODEX_DOCTOR_TIMEOUT}s)")
            ok = False
        except OSError as error:
            print(f"  경고: codex --version 실행 오류: {error}")
            ok = False
        try:
            login = _run_codex_command(["codex", "login", "status"])
            login_output = _clean_output(login)
            logged_in, status_msg = _login_status(login_output, login.returncode)
            print("   로그인:", status_msg, "-", login_output[:80] or "(출력 없음)")
            if not logged_in:
                ok = False
        except subprocess.TimeoutExpired:
            print("   로그인: codex login status 호출 타임아웃")
            ok = False
        except OSError as error:
            print(f"   로그인: codex login status 실행 오류: {error}")
            ok = False
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
    runs = runs_directory(ROOT)
    run_dirs: list[tuple[str, Path]] = []
    if run_id is not None:
        run_dirs.append((run_id, run_directory(ROOT, run_id)))
    elif runs.is_dir():
        for entry in sorted(runs.iterdir(), key=lambda path: path.name):
            try:
                safe_dir = run_directory(ROOT, entry.name)
            except InvalidRunId as error:
                print(f"건너뜀: 안전하지 않은 실행 경로 {entry.name}: {error}", file=sys.stderr)
                continue
            if (safe_dir / "manifest.json").is_file():
                run_dirs.append((entry.name, safe_dir))
    for rid, run_dir in run_dirs:
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"실행 기록 없음: {rid} (`hpr status` 로 목록 확인)")
        m = json.loads(manifest_path.read_text(encoding="utf-8"))
        secs = sum(u.get("seconds", 0) for u in m["usage"])
        from hprc.config import load
        from hprc.pipeline import estimate_cost
        snapshot = m.get("effective_config_snapshot")
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("budget"), dict):
            snapshot = m.get("config_snapshot")
        if isinstance(snapshot, dict) and isinstance(snapshot.get("budget"), dict):
            pricing = snapshot["budget"]
            pricing_note = "실행에 저장된 설정 단가"
        else:
            pricing = load(ROOT)["budget"]
            pricing_note = "과거 단가 기록 없음·현재 설정으로 추정"
        cost = estimate_cost(m["usage"], pricing)
        unknown = (f" · 미측정 {cost['unknown_calls']}회 · 설정 단가 추정 미확정 (측정분 ≈${cost['usd_upper']})"
                   if cost["unknown_calls"] else f" · 설정 단가 추정 ≈${cost['usd_upper']}")
        print(f"{rid} | {m.get('tier','light')} | {m['prompt'][:45]} | 호출 {len(m['usage'])} · {secs:.0f}s · in {cost['input']:,} (캐시 {cost['cached']:,}) / out {cost['output']:,}{unknown}")
        print("   " + pricing_note + " · 실제 청구액이나 계정 잔량이 아닙니다")
        guidance_path = run_dir / "cost_guidance.json"
        if guidance_path.is_file():
            from hprc.cost_guidance import render_cost_guidance
            print(render_cost_guidance(json.loads(guidance_path.read_text(encoding="utf-8")), m.get("lang", "ko")))
        print("   " + ", ".join(f"{s['name']}:{s['status']}" for s in m["steps"]))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("prompt"); r.add_argument("--tier", default="light", choices=["light", "full"])
    r.add_argument("--urls"); r.add_argument("--no-search", action="store_true"); r.add_argument("--scholar", action="store_true"); r.add_argument("--run-id")
    r.add_argument("--budget", type=_positive_int, help="누적 입력 토큰 상한. 넘으면 다음 단계 전에 멈춤"); r.add_argument("--quiet", action="store_true")
    r.add_argument("--replay", help="정답이 분리된 고정 입력 JSON 파일")
    r.add_argument("--case", dest="case_id", help="고정 입력의 case ID")
    r.add_argument("--plan-json", action="store_true", help="호출하지 않고 실행 계획을 JSON으로 출력")
    r.add_argument("--dry-run", action="store_true", help="실행하지 않고 단계·예상 호출 수·예상 비용만 출력")
    r.add_argument("--lang", choices=["ko", "en"], help="프롬프트·보고서 언어 (기본 config lang=ko)")
    r.add_argument("--format", dest="report_format", choices=["brief", "facts", "comparison", "analysis"], help="같은 분량 범위 안에서 보고서 형식 선택")
    r.add_argument("--preset", choices=["standard", "lean", "economy"], help="lean: 구독 계정용 절약 프리셋(비평 2·초안 2·상한 축소)")
    r.add_argument('--packet-inputs', action='store_true', help='선택 실험: 중복 주장 제거 및 파일 입력 묶음')
    r.add_argument('--inline-inputs', action='store_true', help='선택 실험: writer·비평 입력을 프롬프트 stdin으로 전달')
    r.add_argument('--evidence-selection', action='store_true', help='선택 실험: 조건을 보존하는 근거 선택')
    r.add_argument('--reuse-analysis', action='store_true', help='동일 조건의 분석 산출물 재사용')
    r.add_argument('--strategy', choices=['standard', 'adaptive'], help='facts Full에서 단일 초안 경로 선택')
    r.add_argument('--update-from', help='이전 실행과 변경 출처를 비교하여 분석 갱신')
    changes = sub.add_parser('changes'); changes.add_argument('before'); changes.add_argument('after')
    profile = sub.add_parser('profile'); profile.add_argument('run_id')
    evidence = sub.add_parser('evidence'); evidence.add_argument('run_id')
    calc = sub.add_parser('calculate'); calc.add_argument('run_id'); calc.add_argument('spec')
    u = sub.add_parser("usage"); u.add_argument("--days", type=int, default=30); u.add_argument("--json", action="store_true")
    u.add_argument("--backfill", action="store_true", help="장부 이전 실행들의 manifest 를 장부에 채움")
    s = sub.add_parser("resume"); s.add_argument("run_id"); s.add_argument("--budget", type=_positive_int); s.add_argument("--quiet", action="store_true")
    for parser in (r, s):
        parser.add_argument("--total-budget", type=_positive_int, help="입력+출력 전체 토큰 중단 기준, 미측정 호출 뒤 중단")
        parser.add_argument("--max-calls", type=_positive_int, help="실패·재시도를 포함한 실행 전체 모델 호출 상한")
        parser.add_argument("--at", help="이 시각까지 기다렸다가 시작. 'HH:MM'(오늘/내일) 또는 'YYYY-MM-DD HH:MM'. 사용량 리셋 뒤 자동 재개용")
    ins = sub.add_parser("install-skill"); ins.add_argument("--yes", action="store_true", help="~/.codex/skills 에 실제로 복사")
    q = sub.add_parser("search"); q.add_argument("query"); q.add_argument("--limit", type=int, default=10)
    st = sub.add_parser("status"); st.add_argument("run_id", nargs="?")
    for name in ("sync", "doctor", "mcp", "mcp-config", "skill"):
        sub.add_parser(name)
    a = p.parse_args()
    if a.cmd in {'changes', 'evidence', 'calculate', 'profile'}:
        try:
            if a.cmd == 'changes':
                from .research_updates import compare_runs
                result = compare_runs(run_directory(ROOT, a.before), run_directory(ROOT, a.after))
            elif a.cmd == 'profile':
                from .research_review import input_diagnostics
                result = input_diagnostics(json.loads((run_directory(ROOT, a.run_id) / 'manifest.json').read_text(encoding='utf-8')))
            elif a.cmd == 'evidence':
                print((run_directory(ROOT, a.run_id) / 'evidence_matrix.md').read_text(encoding='utf-8'))
                return 0
            else:
                from .research_review import check_calculation
                from .research_updates import verified_source_texts
                texts = verified_source_texts(run_directory(ROOT, a.run_id))
                result = check_calculation(json.loads(Path(a.spec).read_text(encoding='utf-8')), texts)
            print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
        except (ValueError, OSError, KeyError, TypeError) as error:
            print('BLOCKED:', error, file=sys.stderr); return 2
    efficiency = {}
    if a.cmd == 'run':
        if a.packet_inputs and a.inline_inputs:
            p.error('--packet-inputs와 --inline-inputs는 함께 사용할 수 없습니다')
        for arg, key in [('packet_inputs', 'packet_inputs'), ('inline_inputs', 'inline_inputs'), ('evidence_selection', 'evidence_selection'), ('reuse_analysis', 'reuse_analysis')]:
            if getattr(a, arg): efficiency[key] = True
        if a.strategy: efficiency['strategy'] = a.strategy
    if a.cmd == "run" and bool(a.replay) != bool(a.case_id):
        p.error("--replay와 --case는 함께 지정해야 합니다")
    validated_run_dir = None
    try:
        if a.cmd == "run":
            validated_run_dir = run_directory(ROOT, a.run_id) if a.run_id is not None else None
            if validated_run_dir is None:
                runs_directory(ROOT)
        elif a.cmd in ("resume", "status"):
            validated_run_dir = run_directory(ROOT, a.run_id) if a.run_id is not None else None
            if validated_run_dir is None:
                runs_directory(ROOT)
    except InvalidRunId as error:
        print("BLOCKED:", error, file=sys.stderr); return 2
    if a.cmd == "doctor":
        return doctor()
    if a.cmd == "sync":
        print("색인한 노트:", vault.sync(ROOT)); return 0
    if a.cmd == "search":
        for row in vault.search(ROOT, a.query, a.limit):
            print(f"{row['id']:<4} {row['title'][:60]:<60} {row['snippet']}")
        return 0
    if a.cmd == "status":
        try:
            status(a.run_id)
        except (InvalidRunId, FileNotFoundError) as error:
            print("BLOCKED:", error, file=sys.stderr); return 2
        return 0
    if a.cmd == "usage":
        from hprc import ledger
        if a.backfill:
            print("장부에 추가:", ledger.backfill(ROOT), "건")
        summary = ledger.summarize(ROOT, a.days)
        if a.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2)); return 0
        t = summary["total"]
        unknown = t.get("unknown_calls", 0)
        print(f"최근 {a.days}일 실제 호출 {t['calls']}회 · 입력 {t['in']:,} (캐시 {t['cached']:,}, 미측정 {unknown}회) · 출력 {t['out']:,} · 모델 시간 {t['seconds']/60:.1f}분")
        print("--- 날짜별"); [print(f"  {d}: {v['calls']}회 · in {v['in']:,} · out {v['out']:,}") for d, v in summary["by_day"].items()]
        print("--- 실행별"); [print(f"  {r}: {v['tier']}/{v['lang']} · {v['calls']}회 · in {v['in']:,} · out {v['out']:,} · {v['seconds']/60:.1f}분") for r, v in summary["by_run"].items()]
        print("장부:", ledger.path(ROOT)); return 0
    if a.cmd == "mcp":
        mcp_server.serve(ROOT); return 0
    if a.cmd == "mcp-config":
        print(f'# ~/.codex/config.toml 에 추가 (사용자가 직접):\n[mcp_servers.hyperresearch]\ncommand = "python3"\nargs = ["{Path(sys.argv[0]).resolve()}", "mcp"]')
        return 0
    if a.cmd == "install-skill":
        src = _skill_source(); dst = Path.home() / ".codex/skills/hyperresearch-codex/SKILL.md"
        if not a.yes:
            print(f"복사 예정: {src} → {dst}\n실행하려면 --yes"); return 0
        _copy_skill(src, dst); print("설치됨:", dst); return 0
    if a.cmd == "skill":
        src = _skill_source()
        print(f'# Codex 스킬 설치 (사용자가 직접):\nmkdir -p ~/.codex/skills/hyperresearch-codex && cp "{src}" ~/.codex/skills/hyperresearch-codex/SKILL.md')
        return 0
    if a.cmd in ("run", "resume") and getattr(a, "at", None) and not (getattr(a, "dry_run", False) or getattr(a, "plan_json", False)):
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
    if a.cmd == "run" and (a.dry_run or a.plan_json):
        from hprc.config import load
        from hprc.token_policy import plan_run
        cfg = load(ROOT, preset=a.preset, lang=a.lang)
        if a.budget:
            cfg["budget"]["max_input_tokens"] = a.budget
        if a.max_calls:
            cfg["budget"]["max_model_calls"] = a.max_calls
        if a.total_budget:
            cfg["budget"]["max_total_tokens"] = a.total_budget
        cfg["efficiency"].update(efficiency)
        if a.report_format:
            cfg["report_format"] = a.report_format
        plan = plan_run(cfg, a.tier, a.no_search, replay=bool(a.replay))
        if a.plan_json:
            print(json.dumps(plan, ensure_ascii=False, indent=2))
        else:
            print(f"프리셋 {plan['preset']} · 예상 단계 호출 최대 {plan['planned_calls_max']} · 재시도 포함 호출 상한 {plan['attempts_max']}\n"
                  f"과거 참고 입력 범위 {plan['input_estimate_range'][0]:,}–{plan['input_estimate_range'][1]:,} (현재 모델의 보장값 아님)\n"
                  f"입력 중단 기준 {plan['input_stop_threshold']:,} · 입력 예약 검사 {plan['reservation_enabled']} · 미측정 중단 {plan['stop_on_unknown']}\n"
                  f"총 토큰 중단 기준 {plan['total_token_stop_threshold']} · 호출당 출력 예약 {plan['output_reservation']} · 형식 {plan['report_format']}\n"
                  f"진행 중 호출은 예상치를 초과할 수 있으며 구독 잔량을 나타내지 않습니다.\n"
                  + "\n".join(f"{role}: {value['model']} / {value['effort']}" for role, value in plan['models'].items()))
        return 0
    try:
        if a.cmd == "run":
            out = pipeline.run(ROOT, a.prompt, a.tier, urls_file=a.urls, run_id=a.run_id, no_search=a.no_search, scholar=a.scholar,
                               quiet=a.quiet, budget=a.budget, lang=a.lang, preset=a.preset, max_calls=a.max_calls, replay_file=a.replay, case_id=a.case_id, total_budget=a.total_budget, report_format=a.report_format, efficiency=efficiency, update_from=a.update_from)
        else:
            mpath = validated_run_dir / "manifest.json"
            if not mpath.exists():
                print(f"BLOCKED: 실행 기록 없음: {a.run_id} (`hpr status` 로 목록 확인)", file=sys.stderr); return 2
            m = json.loads(mpath.read_text(encoding="utf-8"))
            out = pipeline.run(ROOT, m["prompt"], m.get("tier", "light"), run_id=a.run_id, quiet=a.quiet, budget=a.budget, max_calls=a.max_calls, total_budget=a.total_budget)
    except pipeline.Blocked as error:
        print("BLOCKED:", error, file=sys.stderr); return 2
    print("최종 보고서:", out)
    quality_path = out.parent / "quality.json"
    if not quality_path.exists() or json.loads(quality_path.read_text(encoding="utf-8")).get("status") != "passed":
        print("검토 필요: 보고서는 생성됐지만 자동 검증을 통과하지 않았습니다. quality.json 확인", file=sys.stderr)
        return 3
    return 0
