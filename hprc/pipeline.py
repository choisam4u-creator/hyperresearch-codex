"""파이프라인(Light/Full) v0.3.
Light: 검색 → 가져오기 → 분석 → 초안 → 비평 3 → 부분 수정 → 인용 검사 → 린트.
Full : 검색 → 가져오기 → 분석 → 깊이 지점 → 지점 조사(병렬) → 초안 3개(병렬) → 종합 → 비평 4(병렬) → 부분 수정 → 인용 검사 → 다듬기 → 린트.
v0.3 토큰 다이어트: 단계마다 필요한 출처만(분석가가 인용한 출처), 비평·수정에는 발췌본, 종합에는 초안·요약만.
예산 상한(budget.max_input_tokens)을 넘으면 다음 단계 전에 멈춘다. 진행 상황은 stderr 로 바로 보인다."""
import json
import os
import re
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Lock

from . import schemas, scholar as scholarmod, search as searchmod
from .cluster import cluster
from .codex_runner import AuthRequired, CodexError, CodexMissing, UsageLimit, run_step
from .config import load
from .fetch import fetch_all
from . import ledger
from .citation_sampling import enrich_checks, render_summary, select_samples
from .gates import LANG, GateError, apply_hunks, clean_internal_cites, critic_quotes_exist, judgment_sentences, report_lint
from .manifest import Manifest, atomic_write
from .run_paths import run_directory
from .text_select import select
from .mock import mock_backend
from .vault import note_body, read_front, sync, write_note

try:
    import fcntl
except ImportError:  # Windows에서는 CLI import/help/doctor를 유지하고 실제 run만 읽을 수 있게 차단한다.
    fcntl = None

PROMPTS = Path(__file__).parent / "prompts"
ANGLES = ["실무자 관점(어떻게 쓰나)", "반대 근거 우선(무엇이 틀릴 수 있나)", "맥락과 시간순(왜 지금 이렇게 됐나)"]
STEPS = {"light": ["search", "fetch", "analyst", "draft", "critics", "patch", "citecheck", "final"],
         "full": ["search", "fetch", "analyst", "depth", "draft", "critics", "patch", "citecheck", "polish", "final"]}


def _has_valid_candidate(rows: list[dict]) -> bool:
    """검색 보조 경로 전에 실제로 가져올 수 있는 HTTP URL이 있는지 확인한다."""
    for row in rows:
        try:
            parts = urllib.parse.urlsplit(row.get("url", ""))
            if parts.scheme in ("http", "https") and parts.hostname:
                return True
        except ValueError:
            continue
    return False


class Blocked(RuntimeError):
    pass


class HardStop(Blocked):
    """사용량 한도·로그인 만료·codex 없음: 재시도하거나 다른 단계로 넘어가지 않고 그 자리에서 멈춘다."""


@contextmanager
def _run_lock(run_dir: Path):
    """같은 run_id를 한 프로세스만 실행하게 하는 비차단 파일 잠금."""
    if fcntl is None:
        raise Blocked("이 플랫폼은 동일 run 중복 실행 잠금을 지원하지 않음")
    run_dir.mkdir(parents=True, exist_ok=True)
    lock_path = run_dir / ".run.lock"
    stream = lock_path.open("a+", encoding="utf-8")
    locked = False
    try:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except BlockingIOError as error:
            stream.seek(0)
            owner = stream.read().strip() or "소유자 정보 없음"
            raise Blocked(f"같은 실행이 이미 실행 중: {run_dir.name} ({owner})") from error
        stream.seek(0)
        stream.truncate()
        stream.write(f"pid={os.getpid()} at={time.time():.6f}\n")
        stream.flush()
        yield
    finally:
        try:
            if locked:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        finally:
            stream.close()


UI = {"ko": {"provenance": "## 출처 상세(자동 생성)", "cols": "| id | 제목 | 도메인 | 게시일 | 조회일 | 독립 묶음 | 경로 | 인용됨 |",
             "yes": "예", "no": "아니오", "primary": " (1차)", "unknown": "미표기", "lm_note": "\\* 게시일이 서버 Last-Modified 헤더에서 온 값(원문 게시일이 아닐 수 있음)",
             "failed": "## 인용 검사에서 걸린 문장"},
      "en": {"provenance": "## Source details (auto-generated)", "cols": "| id | title | domain | published | fetched | cluster | route | cited |",
             "yes": "yes", "no": "no", "primary": " (primary)", "unknown": "n/a", "lm_note": "\\* published date taken from the server's Last-Modified header (may not be the original publication date)",
             "failed": "## Sentences flagged by the citation check"}}


def _prompt(name: str, lang: str = "ko", **kw) -> str:
    folder = PROMPTS / lang if (PROMPTS / lang).is_dir() else PROMPTS / "ko"
    text = (folder / f"{name}.md").read_text(encoding="utf-8")
    for key, value in kw.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def _clip(body: str, cap: int, query: str = "") -> tuple[str, bool]:
    """cap 을 넘으면 query(질문·초안)와 관련 있는 문단을 골라 넣는다. query 가 없으면 앞부분."""
    if len(body) <= cap:
        return body, False
    if query:
        return select(body, query, cap)
    return body[:cap] + f"\n\n[… {len(body) - cap}자 생략: 이 노트는 잘렸다 …]\n", True


def estimate_cost(usage: list[dict], budget: dict) -> dict:
    def is_known(row: dict) -> bool:
        if row.get("usage_known") is not None:
            return bool(row.get("usage_known"))
        return bool(row.get("usage"))

    known = [u for u in usage if is_known(u)]
    unknown_calls = len(usage) - len(known)
    tin = sum((u.get("usage") or {}).get("input_tokens", 0) for u in known)
    tc = sum((u.get("usage") or {}).get("cached_input_tokens", 0) for u in known)
    tout = sum((u.get("usage") or {}).get("output_tokens", 0) for u in known)
    pin, pout, pc = budget.get("price_input_per_m", 0), budget.get("price_output_per_m", 0), budget.get("price_cached_per_m")
    if pc is None:
        cost = tin / 1e6 * pin + tout / 1e6 * pout
    else:
        cost = (tin - tc) / 1e6 * pin + tc / 1e6 * pc + tout / 1e6 * pout
    return {"input": tin, "cached": tc, "output": tout, "usd_upper": round(cost, 2),
            "known_calls": len(known), "unknown_calls": unknown_calls}


class Run:
    def __init__(self, root: Path, prompt: str, tier: str, run_id: str | None, quiet: bool = False, budget: int | None = None,
                 lang: str | None = None, preset: str | None = None):
        if budget is not None and budget <= 0:
            raise Blocked("예산 상한은 0보다 큰 정수여야 한다")
        self.root, self.quiet = root, quiet
        self.run_id = run_id if run_id is not None else time.strftime("%Y%m%d-%H%M%S")
        try:
            self.dir = run_directory(root, self.run_id)
        except ValueError as error:
            raise Blocked(str(error)) from error
        self.notes_dir = root / "research" / "notes"
        self.logs = self.dir / "logs"
        self.m = Manifest(self.dir, prompt=prompt, tier=tier)
        self.prompt = self.m.data["prompt"]
        self.tier = self.m.data.get("tier", tier)
        # 언어·프리셋은 첫 실행 때 manifest 에 고정된다(resume 시 동일)
        self.lang = self.m.data.setdefault("lang", lang or load(root)["lang"])
        self.preset = self.m.data.setdefault("preset", preset or load(root)["preset"])
        self.cfg = load(root, preset=self.preset, lang=self.lang)
        self.m.save()
        if budget:
            self.cfg["budget"]["max_input_tokens"] = budget
        elif not self.cfg["budget"].get("max_input_tokens"):
            self.cfg["budget"]["max_input_tokens"] = self.cfg["budget"].get("default_by_tier", {}).get(self.tier)
        self.T, self.G = self.cfg[self.tier], self.cfg["gates"]
        self.L, self.U = LANG.get(self.lang, LANG["ko"]), UI.get(self.lang, UI["ko"])
        self.sources, self.known, self.relevant = [], set(), set()
        self._usage_lock = Lock()

    # ---- 진행 표시·상태 파일 ----
    def log(self, msg: str) -> None:
        if not self.quiet:
            print(f"[hpr {time.strftime('%H:%M:%S')}] {msg}", file=sys.stderr, flush=True)

    def state(self, step: str, status: str) -> None:
        atomic_write(self.dir / "state.json", json.dumps({"step": step, "status": status, "at": time.time(), "pid": os.getpid(),
                                                          "cost": estimate_cost(self.m.data["usage"], self.cfg["budget"])}, ensure_ascii=False, indent=2))

    def tag(self, step: str) -> str:
        steps = STEPS[self.tier]
        k = steps.index(step) + 1 if step in steps else 0
        return f"[{k}/{len(steps)}] {step}"

    def begin(self, step: str) -> bool:
        if self.m.done(step):
            self.log(f"{self.tag(step)}: 이미 완료, 건너뜀")
            return False
        self.check_budget(step)
        self.m.start(step); self.state(step, "running")
        self.log(f"{self.tag(step)}: 시작")
        return True

    def end(self, step: str, status: str = "ok", note: str = "") -> None:
        self.m.finish(step, status, note); self.state(step, status)
        cost = estimate_cost(self.m.data["usage"], self.cfg["budget"])
        elapsed = time.time() - self.m.data["created_at"]
        unknown = f" · 미측정 {cost['unknown_calls']}회 · 요금 상한 미확정" if cost["unknown_calls"] else ""
        self.log(f"{self.tag(step)}: {status} · {note} · 누적 in {cost['input']:,} / out {cost['output']:,} (측정분 ≈${cost['usd_upper']}){unknown} · 경과 {elapsed/60:.1f}분")

    def check_budget(self, step: str) -> None:
        limit = self.cfg["budget"].get("max_input_tokens")
        if limit:
            used = estimate_cost(self.m.data["usage"], self.cfg["budget"])["input"]
            if used >= limit:
                self.state(step, "budget_stop")
                raise Blocked(f"예산 상한 도달: 입력 {used:,} ≥ {limit:,}. `hpr resume {self.run_id} --budget <더 큰 값>` 으로 이어 갈 수 있다")

    def _next_attempt(self, name: str) -> int:
        attempts = {u.get("attempt") for u in self.m.data.get("usage", []) if u.get("step") == name and isinstance(u.get("attempt"), int)}
        for log in self.logs.glob(f"{name}.attempt-*.stderr.log"):
            m = re.match(rf"^{re.escape(name)}\.attempt-(\d+)(?:\.[^.]+)?\.stderr\.log$", log.name)
            if m:
                attempts.add(int(m.group(1)))
        return max(attempts or {0}) + 1

    def _record_attempt(self, name: str, size: int, usage: dict, attempt: int, status: str) -> tuple[dict, dict]:
        used = usage.get("usage") or {}
        usage_known = usage.get("usage_known")
        if usage_known is None:
            usage_known = bool(used)
        else:
            usage_known = bool(usage_known)
        at = usage.get("at", time.time())
        record_id = f"{self.run_id}:{name}:{attempt}:{at:.6f}"
        record = {
            "step": name,
            "status": status,
            "attempt": attempt,
            "at": at,
            "input_chars": size,
            "record_id": record_id,
            "backend": usage.get("backend"),
            "model": usage.get("model"),
            "effort": usage.get("effort"),
            "web_search": usage.get("web_search"),
            "seconds": usage.get("seconds", 0),
            "usage": used if usage_known else {},
            "items": usage.get("items", {}),
            "usage_known": usage_known,
            "in": used.get("input_tokens", 0) if usage_known else 0,
            "cached": used.get("cached_input_tokens", 0) if usage_known else 0,
            "out": used.get("output_tokens", 0) if usage_known else 0,
            "usage_unknown": not usage_known
        }
        ledger_record = dict(record)
        ledger_record.update({"run_id": self.run_id, "tier": self.tier, "lang": self.lang, "preset": self.preset})
        with self._usage_lock:
            self.m.usage(record)
            ledger.append(self.root, ledger_record)
        u = used if usage_known else {}
        measured = (f"in {u.get('input_tokens', 0):,} / out {u.get('output_tokens', 0):,}"
                    if usage_known else "사용량 미측정")
        self.log(f"  ← {name} {status} {usage.get('seconds', 0)}s · {measured}")
        return record, ledger_record

    # ---- 모델 호출(재시도 1회) ----
    def call(self, name: str, prompt: str, schema: dict, inputs: dict, role: str, web_search: bool = False) -> dict:
        next_attempt, last = self._next_attempt(name), None
        size = sum(len(v) for v in inputs.values())
        self.log(f"  → {name} (입력 {size:,}자, 파일 {len(inputs)}개)")
        retry = 0
        model_info = self.cfg["models"][role]

        def failure_meta(error) -> dict:
            return {
                "usage": getattr(error, "usage", {}) or {},
                "usage_known": getattr(error, "usage_known", None),
                "at": time.time(),
                "backend": getattr(error, "backend", None) or os.environ.get("HPR_BACKEND", "codex"),
                "seconds": getattr(error, "seconds", None) or 0,
                "model": getattr(error, "model", None) or model_info.get("model"),
                "effort": getattr(error, "effort", None) or model_info.get("effort"),
                "web_search": web_search if getattr(error, "web_search", None) is None else error.web_search,
            }

        while retry <= 1:
            self.check_budget(name)
            attempt = next_attempt + retry
            try:
                result, usage = run_step(name, prompt, schema, inputs, self.cfg["models"][role], self.cfg["codex"], self.logs,
                                         mock=mock_backend, web_search=web_search,
                                         heartbeat=lambda msg: self.log(f"    … {name} {msg}"),
                                         attempt=attempt)
                usage["attempt"] = attempt
                self._record_attempt(name, size, usage, attempt, "ok")
                return result
            except UsageLimit as error:
                self._record_attempt(name, size, failure_meta(error), attempt, "usage_limit")
                atomic_write(self.dir / "state.json", json.dumps({"step": name, "status": "usage_limit", "resets_at": error.resets_at,
                                                                  "at": time.time(), "pid": os.getpid()}, ensure_ascii=False, indent=2))
                self.log(f"  ! {name}: 사용량 한도. 리셋 뒤 `hpr resume {self.run_id}` (예: --at '09:00')")
                raise HardStop(str(error) + f" → 리셋 뒤 `hpr resume {self.run_id}` 로 이어 간다. 이번 단계까지의 결과는 보존됨")
            except (AuthRequired, CodexMissing) as error:
                self._record_attempt(name, size, failure_meta(error), attempt, "blocked")
                status = "auth_required" if isinstance(error, AuthRequired) else "codex_missing"
                atomic_write(self.dir / "state.json", json.dumps({"step": name, "status": status, "at": time.time(), "pid": os.getpid()},
                                                                  ensure_ascii=False, indent=2))
                self.log(f"  ! {name}: {error}")
                raise HardStop(str(error) + f" → 고친 뒤 `hpr resume {self.run_id}`. 이번 단계까지의 결과는 보존됨")
            except (CodexError, ValueError) as error:
                last = error
                self._record_attempt(name, size, failure_meta(error), attempt, "error")
                if retry >= 1:
                    break
                prompt += f"\n\n[재시도 안내] 이전 답이 거부됨: {type(error).__name__}: {str(error)[:200]}. 스키마를 정확히 지켜 다시 답하라."
                self.log(f"  ! {name} 실패({type(error).__name__}), 재시도")
                retry += 1
        self.state(name, "failed")
        raise Blocked(f"{name}: 2회 실패 → {last}. 로그 {self.logs}/*.attempt-*.stderr.log 확인 뒤 `hpr resume {self.run_id}`")

    def parallel(self, jobs: list[tuple]) -> list:
        with ThreadPoolExecutor(max_workers=max(1, self.T.get("parallel", 2))) as pool:
            return list(pool.map(lambda job: job[1](), jobs))

    # ---- 입력 구성(토큰 다이어트) ----
    def notes(self, ids=None, cap=None, query=None) -> dict[str, str]:
        """지정한 출처 id 의 노트만, cap 자까지. 넘치면 query(기본: 질문)와 관련 있는 문단을 고른다. 잘리면 truncated 표시."""
        cap = cap or self.cfg["note_max_chars"]
        query = self.prompt if query is None else query
        out = {}
        for s in self.sources:
            if ids is not None and s["id"] not in ids:
                continue
            front = read_front(Path(s["path"]))
            body, truncated = _clip(note_body(Path(s["path"])), cap, query)
            # 구형 노트에 빠진 날짜는 실행별 출처 메타에서 복구한다.
            published = front.get('published') or s.get('published') or '미표기'
            modified = front.get('modified') or s.get('modified') or '미표기'
            out[f"{s['id']}-note.md"] = (f"---\nid: {s['id']}\ntitle: {front.get('title','')}\nurl: {front.get('url','')}\n"
                                        f"published: {published}\npublished_source: {front.get('published_source') or s.get('published_source', '')}\n"
                                        f"modified: {modified}\nmodified_source: {front.get('modified_source') or s.get('modified_source', '')}\n"
                                        f"domain: {front.get('domain','')}\n"
                                        f"truncated: {'true' if truncated else 'false'}\n---\n{body}")
        return out

    def excerpts(self, ids=None, query=None) -> dict[str, str]:
        """비평·수정용 발췌: query(보통 초안 본문)와 관련 있는 문단 위주."""
        return {k.replace("-note.md", "-excerpt.md"): v for k, v in self.notes(ids, self.cfg["excerpt_chars"], query).items()}

    def digest(self) -> str:
        """분석가 결과를 짧은 요약으로: 주장·출처·모순·빈틈. 비평·수정·종합 단계의 기본 근거."""
        claims = json.loads((self.dir / "claims.json").read_text())
        lines = ["# 주장 요약(분석가)", ""]
        for c in claims["claims"]:
            lines.append(f"- {c['id']} [{c['confidence']}] {c['text']} " + "".join(f"[{s}]" for s in c["sources"]))
        if claims.get("contradictions"):
            lines += ["", "## 모순"] + [f"- {x['note']} ({', '.join(x['claim_ids'])})" for x in claims["contradictions"]]
        if claims.get("gaps"):
            lines += ["", "## 빈틈"] + [f"- {g}" for g in claims["gaps"]]
        lines += ["", "## 출처 목록"] + [f"- {s['id']}: {s['title'][:80]} — {s['domain']} ({s.get('published') or '날짜 미표기'})" for s in self.sources]
        return "\n".join(lines) + "\n"

    def independence_md(self) -> str:
        groups = {}
        for s in self.sources:
            groups.setdefault(s.get("cluster", s["id"]), []).append(s["id"])
        top, share = searchmod.domain_skew(self.sources)
        lines = ["# 출처 독립성", "", f"독립 근거 묶음 {len(groups)}개 / 출처 {len(self.sources)}개. 같은 묶음은 근거 하나로 센다."]
        if share >= self.cfg["domain_skew_warn"]:
            lines.append(f"경고: 출처의 {share:.0%}가 {top} 한 곳이다. 다른 관점의 출처가 부족할 수 있다.")
        lines.append("")
        for cid, ids in groups.items():
            lines.append(f"- 묶음 {cid}: {', '.join(ids)}" + ("" if len(ids) == 1 else "  ← 같은 원문/복사본"))
        return "\n".join(lines) + "\n"

    def load_sources(self):
        data = json.loads((self.dir / "sources.json").read_text())
        self.sources = data["sources"]
        self.known = {s["id"] for s in self.sources}
        rel = self.dir / "relevant.json"
        self.relevant = set(json.loads(rel.read_text())["ids"]) if rel.exists() else set(self.known)

    # ---- 단계 ----
    def step_search(self, urls_file, no_search, scholar):
        if not self.begin("search"):
            return
        if urls_file and not Path(urls_file).exists():
            self.state("search", "blocked")
            raise Blocked(f"URL 파일 없음: {urls_file}")
        rows = searchmod.from_file(urls_file) if urls_file else []
        stats = {"user": len(rows)}
        if not no_search:
            for provider in self.cfg["search"]["providers"]:
                if provider == "codex_scout":
                    try:
                        result = self.call("scout", _prompt("scout", self.lang, limit=self.T["search_results"], max_searches=self.cfg["scout_max_searches"]),
                                           schemas.SCOUT, {"question.txt": self.prompt}, "scout", web_search=True)
                        found = [{**r, "via": "codex_scout"} for r in result["results"] if r.get("url", "").startswith("http")]
                    except HardStop:
                        raise                      # 한도·인증·설치 문제는 다른 검색으로 덮지 않는다
                    except Blocked as error:
                        found, stats["scout_error"] = [], str(error)[:120]
                    rows += found; stats["codex_scout"] = len(found)
                elif provider == "duckduckgo":
                    queries = searchmod.query_variants(self.prompt) if self.cfg["search"]["query_variants"] else [self.prompt]
                    found = []
                    for q in queries:
                        result = searchmod.duckduckgo(q, self.T["search_results"], self.cfg["fetch"]["user_agent"])
                        stats.setdefault("errors", []).extend(r for r in result if "error" in r)
                        found += [r for r in result if "error" not in r]
                    rows += found; stats["duckduckgo"] = len(found)
                    # SearXNG는 명시한 endpoint가 있고 DuckDuckGo가 유효 후보를
                    # 전혀 주지 못했을 때만 쓰는 보조 경로다.
                    endpoint = self.cfg["search"].get("searxng_endpoint")
                    if endpoint and not _has_valid_candidate(found) and not _has_valid_candidate(rows):
                        fallback = []
                        for q in queries:
                            result = searchmod.searxng(q, self.T["search_results"], endpoint, self.cfg["fetch"]["user_agent"])
                            stats.setdefault("errors", []).extend(r for r in result if "error" in r)
                            fallback += [r for r in result if "error" not in r]
                        rows += fallback; stats["searxng"] = len(fallback)
        if scholar and not no_search:
            found = scholarmod.arxiv(self.prompt[:120], 5) + scholarmod.openalex(self.prompt[:120], 5)
            rows += found; stats["scholar"] = len(found)
        cands = searchmod.prioritize(rows, self.cfg["search"]["preferred_domains"])
        atomic_write(self.dir / "candidates.json", json.dumps({"stats": stats, "candidates": cands}, ensure_ascii=False, indent=2))
        self.end("search", "ok" if cands else "blocked", json.dumps(stats, ensure_ascii=False))
        if not cands:
            raise Blocked("검색 결과도 URL 목록도 없음. --urls 로 출처를 주거나 나중에 다시 시도")

    def step_fetch(self):
        if not self.begin("fetch"):
            return
        cands = json.loads((self.dir / "candidates.json").read_text())["candidates"][: self.T["search_results"]]
        pages = fetch_all(cands, self.cfg["fetch"])
        kept, log, texts = [], [], {}
        for page in pages:
            reason = page["error"] or ("too_short" if len(page["text"]) < self.G["min_note_chars"] else "")
            if reason:
                log.append({"url": page["url"], "skipped": reason}); continue
            if len(kept) >= self.T["max_sources"]:
                log.append({"url": page["url"], "skipped": "max_sources"}); continue
            sid = f"S{len(kept) + 1}"
            path = write_note(self.notes_dir, sid, page)
            texts[sid] = page["text"]
            kept.append({"id": sid, "note_id": read_front(path).get("id", sid), "path": str(path), "url": page["url"], "title": page["title"], "domain": page["domain"],
                         "published": page.get("published", ""), "published_source": page.get("published_source", "meta" if page.get("published") else ""),
                         "modified": page.get("modified", ""), "modified_source": page.get("modified_source", ""),
                         "canonical": page.get("canonical", ""), "via": page.get("via", ""), "official": page.get("official", False),
                         "chars": len(page["text"]), "fetched_at": time.strftime("%Y-%m-%d")})
        assign = cluster(kept, texts, self.G["dup_jaccard"])
        for s in kept:
            s["cluster"] = assign[s["id"]]
        top, share = searchmod.domain_skew(kept)
        warn = [f"domain_skew:{top}:{share:.0%}"] if kept and share >= self.cfg["domain_skew_warn"] else []
        atomic_write(self.dir / "sources.json", json.dumps({"sources": kept, "skipped": log, "independent_groups": len(set(assign.values())),
                                                           "warnings": warn}, ensure_ascii=False, indent=2))
        sync(self.root)
        self.end("fetch", "ok" if kept else "blocked", f"{len(kept)}개 노트({len(set(assign.values()))} 독립 묶음), {len(log)}개 건너뜀" + (f", {warn[0]}" if warn else ""))
        if not kept:
            raise Blocked("읽을 수 있는 출처가 0개. sources.json 의 skipped 확인")

    def step_analyst(self):
        if not self.begin("analyst"):
            return
        inputs = {"question.txt": self.prompt, "_independence.md": self.independence_md(), **self.notes()}
        result = self.call("analyst", _prompt("analyst", self.lang), schemas.ANALYST, inputs, "analyst")
        bad = [c for c in result["claims"] if not set(c["sources"]) <= self.known]
        if bad:
            raise Blocked(f"분석가가 없는 출처를 인용함: {[c['id'] for c in bad]}")
        atomic_write(self.dir / "claims.json", json.dumps(result, ensure_ascii=False, indent=2))
        used = sorted({s for c in result["claims"] for s in c["sources"]}, key=lambda x: int(x[1:]))
        self.relevant = set(used) if used else set(self.known)
        atomic_write(self.dir / "relevant.json", json.dumps({"ids": sorted(self.relevant, key=lambda x: int(x[1:]))}))
        self.end("analyst", "ok", f"주장 {len(result['claims'])}개, 모순 {len(result['contradictions'])}개, 실제 인용 출처 {len(self.relevant)}/{len(self.known)}")

    def step_depth(self):
        if not self.begin("depth"):
            return
        inputs = {"question.txt": self.prompt, "claims.json": (self.dir / "claims.json").read_text(),
                  "_independence.md": self.independence_md(), **self.excerpts(self.relevant)}
        loci = self.call("loci", _prompt("loci", self.lang, loci_max=self.T["loci_max"]), schemas.LOCI, inputs, "loci")["loci"][: self.T["loci_max"]]
        interim = self.dir / "interim"; interim.mkdir(exist_ok=True)

        def investigate(locus):
            def job():
                out = interim / f"{locus['id']}.md"
                if out.exists():
                    return locus["id"]
                ids = set(locus.get("source_ids") or []) & self.known or self.relevant
                res = self.call(f"investigator_{locus['id']}", _prompt("investigator", self.lang), schemas.INVESTIGATOR,
                                {"question.txt": self.prompt, "locus.json": json.dumps(locus, ensure_ascii=False), **self.notes(ids)}, "investigator")
                text = [f"# {locus['id']}: {locus['question']}", "", "## 입장", res["position"], "", "## 근거"]
                text += [f"- {e['claim']} " + "".join(f"[{s}]" for s in e["source_ids"]) for e in res["evidence"] if set(e["source_ids"]) <= self.known]
                text += ["", "## 열린 질문"] + [f"- {q}" for q in res["open_questions"]]
                atomic_write(out, "\n".join(text) + "\n")
                return locus["id"]
            return job
        done = self.parallel([(l["id"], investigate(l)) for l in loci])
        atomic_write(self.dir / "loci.json", json.dumps({"loci": loci}, ensure_ascii=False, indent=2))
        self.end("depth", "ok", f"지점 {len(done)}개 조사")

    def _interim(self) -> dict:
        d = self.dir / "interim"
        return {f"interim/{p.name}": p.read_text(encoding="utf-8") for p in sorted(d.glob("*.md"))} if d.is_dir() else {}

    def step_draft(self):
        if not self.begin("draft"):
            return
        digest = self.digest()
        base = {"question.txt": self.prompt, "claims.json": (self.dir / "claims.json").read_text(), "_digest.md": digest,
                "_independence.md": self.independence_md(), **self.notes(self.relevant, self.cfg["draft_note_chars"])}
        if self.tier == "light":
            draft = self.call("writer", _prompt("writer", self.lang, target_words=self.T["target_words"]), schemas.WRITER, base, "writer")["markdown"]
        else:
            drafts_dir = self.dir / "drafts"; drafts_dir.mkdir(exist_ok=True)
            inputs = {**base, **self._interim()}

            def make(k, angle):
                def job():
                    out = drafts_dir / f"draft_{k}.md"
                    if not out.exists():
                        res = self.call(f"draft_{k}", _prompt("draft", self.lang, angle=angle, target_words=self.T["target_words"]), schemas.WRITER, inputs, "writer")
                        atomic_write(out, res["markdown"])
                return job
            self.parallel([(f"draft_{k}", make(k, a)) for k, a in enumerate(ANGLES[: self.T["drafts"]], 1)])
            drafts_in = {f"drafts/{p.name}": p.read_text(encoding="utf-8") for p in sorted(drafts_dir.glob("draft_*.md"))}
            # 종합에는 노트 원문 없이 초안·interim·요약·발췌만 (토큰 다이어트)
            draft = self.call("synth", _prompt("synth", self.lang, target_words=self.T["target_words"]), schemas.WRITER,
                              {"question.txt": self.prompt, "_digest.md": digest, "_independence.md": self.independence_md(),
                               **drafts_in, **self._interim(), **self.excerpts(self.relevant, self.prompt + "\n" + "\n".join(drafts_in.values())[:20000])}, "synth")["markdown"]
        draft, fixed = clean_internal_cites(draft, self.lang)
        problems = report_lint(draft, self.prompt, self.known, self.lang)
        if fixed:
            problems.append(f"internal_cites_cleaned:{fixed}")
        hard = [p for p in problems if p.startswith(("verbatim", "unknown_cites", "no_citations"))]
        if hard:
            raise Blocked(f"초안 게이트 실패: {hard}")
        atomic_write(self.dir / "draft.md", draft)
        self.end("draft", "ok", f"{len(draft)}자, 판단 표시 {judgment_sentences(draft, self.lang)}개, 경고 {problems}")

    def step_critics(self):
        if not self.begin("critics"):
            return
        draft = (self.dir / "draft.md").read_text(encoding="utf-8")
        inputs = {"question.txt": self.prompt, "draft.md": draft, "_digest.md": self.digest(), "_independence.md": self.independence_md(),
                  **self.excerpts(self.relevant, self.prompt + "\n" + draft)}
        partials = self.dir / "critics"
        partials.mkdir(exist_ok=True)

        def critic(kind):
            def job():
                partial = partials / f"{kind}.json"
                if partial.exists():
                    res = json.loads(partial.read_text(encoding="utf-8"))
                else:
                    res = self.call(f"critic_{kind}", _prompt(f"critic_{kind}", self.lang), schemas.CRITIC, inputs, "critic")
                    atomic_write(partial, json.dumps(res, ensure_ascii=False, indent=2))
                kept, dropped = critic_quotes_exist(res["findings"], draft)
                return [{**f, "critic": kind} for f in kept], [{**d, "critic": kind} for d in dropped]
            return job
        results = self.parallel([(k, critic(k)) for k in self.T["critics"]])
        findings = [f for kept, _ in results for f in kept]
        dropped = [d for _, dr in results for d in dr]
        for i, f in enumerate(findings, 1):
            f["id"] = f"F{i}"
        atomic_write(self.dir / "findings.json", json.dumps({"findings": findings, "dropped": dropped}, ensure_ascii=False, indent=2))
        self.end("critics", "ok", f"지적 {len(findings)}개, 인용 불일치로 버림 {len(dropped)}개")

    def _apply_hunk_step(self, name, prompt_name, src_file, dst_file, role, ratio, extra):
        text = (self.dir / src_file).read_text(encoding="utf-8")
        res = self.call(name, _prompt(prompt_name, hunk_max=self.G["hunk_max_chars"]), schemas.PATCHER, {src_file: text, **extra}, role)
        try:
            new, rejected = apply_hunks(text, res["hunks"], ratio, self.G["hunk_max_chars"])
            unknown = [c for c in re.findall(r"\[(S\d+)\]", new) if c not in self.known]
            if unknown:
                raise GateError(f"수정본이 없는 출처를 인용: {unknown}")
            if name == "polish" and len(re.findall(r"\[S\d+\]", new)) < len(re.findall(r"\[S\d+\]", text)):
                raise GateError("다듬기가 인용 표시를 지움")
            if judgment_sentences(new, self.lang) < judgment_sentences(text, self.lang):
                raise GateError(f"{name} 이 판단 표시를 지움")
            new, _ = clean_internal_cites(new, self.lang)
            atomic_write(self.dir / dst_file, new)
            return f"적용 {len(res['hunks']) - len(rejected)}, 거부 {len(rejected)}, 건너뜀 {len(res.get('skipped', []))}"
        except GateError as error:
            atomic_write(self.dir / dst_file, text)
            return f"게이트 거부 → 원문 유지: {error}"

    def step_patch(self):
        if not self.begin("patch"):
            return
        findings = json.loads((self.dir / "findings.json").read_text())["findings"]
        if not findings:
            atomic_write(self.dir / "report.md", (self.dir / "draft.md").read_text(encoding="utf-8"))
            self.end("patch", "ok", "지적 없음, 초안 유지"); return
        ids = {s for f in findings for s in f.get("source_ids", [])} & self.known or self.relevant
        note = self._apply_hunk_step("patcher", "patcher", "draft.md", "report.md", "patcher", self.G["patch_max_ratio"],
                                     {"findings.json": json.dumps({"findings": findings}, ensure_ascii=False), "_digest.md": self.digest(),
                                      **self.excerpts(ids, "\n".join(f["problem"] + " " + f.get("suggested_fix", "") for f in findings))})
        self.end("patch", "ok", note)

    def step_citecheck(self):
        if not self.begin("citecheck"):
            return
        report = (self.dir / "report.md").read_text(encoding="utf-8")
        # Full tier의 polish가 뒤에서 report.md를 바꾸므로, 표본·행 번호는 이
        # 시점의 별도 스냅샷을 기준으로 고정한다.
        snapshot = self.dir / "citecheck_report.md"
        atomic_write(snapshot, report)
        sampling = select_samples(report, self.T["cite_sample"], self.L["judgment"])
        sampling["line_reference"] = snapshot.name
        samples = sampling["samples"]
        raw_checks = {"checks": []}
        if samples:
            ids = {c for s in samples for c in s["cites"]} & self.known
            # 출처마다 "그 출처를 인용한 문장"만 질의로 써서 관련 문단을 고른다.
            # (한 질의로 모든 노트를 자르면 검사 문장의 근거 문단이 빠져 '본문 생략' 오탐이 난다 — tp-light-ko-1b 실측)
            inputs = {"samples.json": json.dumps(samples, ensure_ascii=False)}
            for sid in sorted(ids):
                query = "\n".join(s["sentence"] for s in samples if sid in s["cites"])
                inputs.update(self.notes({sid}, self.cfg["cite_note_chars"], query))
            raw_checks = self.call("citecheck", _prompt("citecheck", self.lang), schemas.CITECHECK, inputs, "citecheck")
        checks = enrich_checks(raw_checks["checks"], sampling)
        atomic_write(self.dir / "citecheck.json", json.dumps({"checks": checks, "sampling": sampling}, ensure_ascii=False, indent=2))
        bad = [c for c in checks if not c["supported"]]
        self.end("citecheck", "ok", f"표본 {sampling['selected_count']}개 중 판정 {sampling['checked_count']}개, 미지지 {len(bad)}개")

    def step_polish(self):
        if self.tier != "full" or not self.T.get("polish"):
            return
        if not self.begin("polish"):
            return
        self.end("polish", "ok", self._apply_hunk_step("polish", "polish", "report.md", "report.md", "polish", self.G["polish_max_ratio"], {}))

    def step_final(self) -> Path:
        out = self.dir / "final_report.md"
        if not self.begin("final"):
            return out
        report = (self.dir / "report.md").read_text(encoding="utf-8")
        problems = report_lint(report, self.prompt, self.known, self.lang)
        citecheck = json.loads((self.dir / "citecheck.json").read_text())
        checks = citecheck.get("checks", [])
        sampling = citecheck.get("sampling")
        bad = [c for c in checks if not c["supported"]]
        sample_count = sampling.get("selected_count", len(checks)) if sampling else len(checks)
        findings = json.loads((self.dir / "findings.json").read_text())["findings"]
        cost = estimate_cost(self.m.data["usage"], self.cfg["budget"])
        groups = len({s.get("cluster", s["id"]) for s in self.sources})
        warns = json.loads((self.dir / "sources.json").read_text()).get("warnings", [])
        price = (f"요금 상한 미확정 (측정분 ≈${cost['usd_upper']}) · 미측정 {cost['unknown_calls']}회"
                 if cost["unknown_calls"] else f"요금 상한 ≈${cost['usd_upper']}")
        header = ["<!-- hyperresearch-codex " + self.tier + " -->",
                  f"<!-- run: {self.run_id} · 출처 {len(self.sources)}개(독립 묶음 {groups}, 실제 인용 {len(self.relevant)}) · 지적 {len(findings)}개 · 인용표본 {sample_count}개 중 미지지 {len(bad)}개 · 판단 표시 {judgment_sentences(report, self.lang)}개 · 린트 {problems or 'OK'} · 모델 호출 {len(self.m.data['usage'])}회 · 토큰 in {cost['input']:,} (캐시 {cost['cached']:,}) / out {cost['output']:,} · {price}" + (f" · 경고 {warns}" if warns else "") + " -->", ""]
        U = self.U
        prov = ["", U["provenance"], "", U["cols"], "|---|---|---|---|---|---|---|---|"]
        for s in self.sources:
            pub = (s.get("published") or U["unknown"]) + ("*" if s.get("published_source") == "last-modified" else "")
            prov.append(f"| {s['id']} | {s['title'][:60].replace('|', ' ')} | {s['domain']} | {pub} | {s.get('fetched_at','')} | {s.get('cluster', s['id'])} | {s.get('via','')}{U['primary'] if s.get('official') else ''} | {U['yes'] if s['id'] in self.relevant else U['no']} |")
        prov.append("\n" + U["lm_note"])
        citation_summary = render_summary(checks, sampling, self.lang)
        final = "\n".join(header) + report + "\n" + citation_summary + "\n".join(prov) + "\n"
        atomic_write(out, final)
        self.m.artifact("final_report", out)
        unreturned = sampling and sampling.get("checked_count", 0) < sampling.get("selected_count", 0)
        uncertain = bool(sampling and sampling.get("unmatched_count", 0))
        self.end("final", "warn" if problems or bad or unreturned or uncertain else "ok", str(problems))
        return out


def run(root: Path, prompt: str, tier: str = "light", urls_file: str | None = None, run_id: str | None = None,
        no_search: bool = False, scholar: bool = False, quiet: bool = False, budget: int | None = None,
        lang: str | None = None, preset: str | None = None) -> Path:
    if tier not in STEPS:
        raise Blocked(f"모르는 tier: {tier}")
    if budget is not None and budget <= 0:
        raise Blocked("예산 상한은 0보다 큰 정수여야 한다")
    actual_run_id = run_id if run_id is not None else time.strftime("%Y%m%d-%H%M%S")
    try:
        run_dir = run_directory(root, actual_run_id)
    except ValueError as error:
        raise Blocked(str(error)) from error
    with _run_lock(run_dir):
        r = Run(root, prompt, tier, actual_run_id, quiet, budget, lang, preset)
        r.log(f"run {r.run_id} · {r.tier} · {r.lang} · {r.preset} · 예산 {r.cfg['budget']['max_input_tokens']:,} · {r.prompt[:60]}")
        r.step_search(urls_file, no_search, scholar)
        r.step_fetch()
        r.load_sources()
        r.step_analyst()
        if r.tier == "full":
            r.step_depth()
        r.step_draft()
        r.step_critics()
        r.step_patch()
        r.step_citecheck()
        r.step_polish()
        out = r.step_final()
        r.log("완료 → " + str(out))
        r.log(out.read_text(encoding="utf-8").splitlines()[1].strip("<!- >"))
        return out


def run_light(root, prompt, urls_file=None, run_id=None, no_search=False):
    return run(root, prompt, "light", urls_file, run_id, no_search)
