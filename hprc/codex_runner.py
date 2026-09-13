"""codex exec 호출부.
원칙: 읽기전용 샌드박스, 입력 파일만 든 임시 작업폴더, --output-schema 로 최종 답 JSON 강제, 파일 쓰기는 파이썬만.
--json 이벤트를 받아 토큰 사용량(turn.completed.usage)을 기록한다. web_search=True 면 `codex --search` 로 Codex 자체 웹 검색을 켠다.
HPR_BACKEND=mock 이면 Codex 를 부르지 않는다."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
import time
from pathlib import Path


class CodexError(RuntimeError):
    def __init__(self, message: str, *, usage: dict | None = None, usage_known: bool | None = None,
                 backend: str = "", model: str | None = None, effort: str | None = None,
                 web_search: bool | None = None, seconds: float | None = None, stderr: str = ""):
        super().__init__(message)
        self.usage = usage or {}
        self.usage_known = usage_known
        self.backend = backend
        self.model = model
        self.effort = effort
        self.web_search = web_search
        self.seconds = seconds
        self.stderr = stderr


class UsageLimit(CodexError):
    """구독 사용량 한도·요청 제한. 재시도하지 않고 멈춘 뒤 리셋 후 resume 한다."""
    def __init__(self, message: str, resets_at: str = "", *, usage: dict | None = None,
                 usage_known: bool | None = None, backend: str = "", model: str | None = None,
                 effort: str | None = None, web_search: bool | None = None,
                 seconds: float | None = None, stderr: str = ""):
        super().__init__(message, usage=usage, usage_known=usage_known, backend=backend,
                         model=model, effort=effort, web_search=web_search,
                         seconds=seconds, stderr=stderr)
        self.resets_at = resets_at


class AuthRequired(CodexError):
    """로그인 만료·인증 실패. 재시도해도 같으니 멈추고 `codex login` 을 안내한다."""


class CodexMissing(CodexError):
    """codex 실행 파일이 PATH 에 없음."""


_AUTH_PATTERNS = re.compile(r"not logged in|codex login|\b401\b|unauthori[sz]ed|invalid api key|authentication (?:failed|required)|token (?:expired|invalid)|refresh token", re.I)


def detect_auth_error(text: str) -> bool:
    return bool(text and _AUTH_PATTERNS.search(text))


_LIMIT_PATTERNS = re.compile(r"usage limit|rate limit|too many requests|\b429\b|quota|exceeded your|limit reached|plan limit|try again (?:at|in|later)", re.I)
_RESET_PATTERNS = re.compile(r"(?:reset|resets|try again|available)[^\n]{0,40}?(\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?(?:\s*[A-Z]{2,4})?|\d+\s*(?:minutes?|hours?|min|h)\b)", re.I)


def detect_usage_limit(text: str) -> tuple[bool, str]:
    """stderr/이벤트 텍스트에서 한도 메시지와 리셋 시각(있으면)을 찾는다."""
    if not text or not _LIMIT_PATTERNS.search(text):
        return False, ""
    m = _RESET_PATTERNS.search(text)
    return True, (m.group(1).strip() if m else "")


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S) or re.search(r"(\{.*\})", text, re.S)
    if match:
        try:
            return json.loads(match.group(1))
        except ValueError as error:
            raise CodexError("모델 답이 JSON 이 아님") from error
    raise CodexError("모델 답이 JSON 이 아님")


def parse_events(path: Path) -> dict:
    """--json 이벤트 파일에서 사용량과 도구 사용 횟수를 뽑는다."""
    usage, kinds = {}, {}
    usage_known = False
    if not path.exists():
        return {"usage": usage, "items": kinds, "usage_known": usage_known}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = event["usage"]
            usage_known = True
        item = event.get("item") or {}
        if event.get("type") == "item.completed" and item.get("type"):
            kinds[item["type"]] = kinds.get(item["type"], 0) + 1
    return {"usage": usage, "items": kinds, "usage_known": usage_known}


def write_inputs(work: Path, inputs: dict[str, str]) -> None:
    """입력 파일을 임시 작업폴더에 쓴다. 'interim/L1.md' 처럼 하위 폴더가 있으면 먼저 만든다."""
    for filename, content in inputs.items():
        target = work / filename
        if not target.resolve().is_relative_to(work.resolve()):
            raise CodexError(f"작업폴더 밖 입력 경로: {filename}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def build_cmd(work: Path, schema_path: Path, out_file: Path, role_cfg: dict, codex_cfg: dict, web_search: bool) -> list[str]:
    cmd = ["codex"]
    if web_search:
        cmd.append("--search")
    cmd += ["exec", "-C", str(work), "-s", "read-only", "--output-schema", str(schema_path), "-o", str(out_file),
            "--color", "never", "--json"]
    if codex_cfg.get("ignore_user_config", True):
        cmd.append("--ignore-user-config")
    cmd += list(codex_cfg.get("extra_args", []))
    if role_cfg.get("model"):
        cmd += ["-m", role_cfg["model"]]
    if role_cfg.get("effort"):
        cmd += ["-c", f"model_reasoning_effort=\"{role_cfg['effort']}\""]
    return cmd


def _wait_with_heartbeat(proc, events: Path, timeout: int, heartbeat, every: int = 30) -> None:
    """codex 가 도는 동안 every 초마다 경과 시간과 지금까지의 도구 사용을 알린다."""
    started = time.time()
    while True:
        remaining = timeout - (time.time() - started)
        try:
            proc.wait(timeout=max(0.1, min(every, remaining)))
            return
        except subprocess.TimeoutExpired:
            elapsed = time.time() - started
            if elapsed >= timeout:
                proc.kill(); proc.wait()
                raise
            if heartbeat:
                items = parse_events(events)["items"]
                summary = ", ".join(f"{k} {v}회" for k, v in items.items()) or "응답 생성 중"
                heartbeat(f"{int(elapsed)//60}분 {int(elapsed)%60:02d}초 경과 · {summary}")


def _attempt_log_paths(log_dir: Path, name: str, attempt: int) -> tuple[Path, Path]:
    """충돌하지 않는 시도별 로그 경로를 고른다. 기존 로그는 절대 재사용하지 않는다."""
    for _ in range(100):
        event_id = uuid.uuid4().hex[:10]
        events = log_dir / f"{name}.attempt-{attempt}.{event_id}.events.jsonl"
        stderr = log_dir / f"{name}.attempt-{attempt}.{event_id}.stderr.log"
        if not events.exists() and not stderr.exists():
            return events, stderr
    raise CodexError(f"{name}: 고유한 로그 파일 이름을 만들 수 없음")


def run_step(name: str, prompt: str, schema: dict, inputs: dict[str, str], role_cfg: dict, codex_cfg: dict,
             log_dir: Path, mock=None, web_search: bool = False, heartbeat=None, attempt: int = 1) -> tuple[dict, dict]:
    backend = os.environ.get("HPR_BACKEND", "codex")
    started = time.time()
    if backend == "mock":
        if mock is None:
            raise CodexError("mock 응답 생성기가 없음")
        # mock 도 입력 크기에 비례한 토큰을 보고해 예산·비용 로직을 테스트할 수 있게 한다(4자 ≈ 1토큰 가정)
        approx_in = (sum(len(v) for v in inputs.values()) + len(prompt)) // 4
        usage = {"input_tokens": approx_in, "cached_input_tokens": 0, "output_tokens": 200}
        return mock(name, prompt, inputs), {"step": name, "backend": backend, "model": role_cfg.get("model"), "effort": role_cfg.get("effort"),
                                            "web_search": web_search, "seconds": round(time.time() - started, 2), "attempt": attempt,
                                            "usage": usage, "usage_known": True, "items": {}}
    work = Path(tempfile.mkdtemp(prefix=f"hpr-{name}-"))
    events = stderr = None
    try:
        write_inputs(work, inputs)
        schema_path = work / "_schema.json"
        schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
        out_file = work / "_last_message.txt"
        cmd = build_cmd(work, schema_path, out_file, role_cfg, codex_cfg, web_search) + [prompt]
        log_dir.mkdir(parents=True, exist_ok=True)
        events, stderr = _attempt_log_paths(log_dir, name, attempt)
        elapsed = lambda: round(time.time() - started, 1)
        extra_meta = {
            "backend": backend,
            "model": role_cfg.get("model"),
            "effort": role_cfg.get("effort"),
            "web_search": web_search
        }
        with open(events, "x", encoding="utf-8") as out, open(stderr, "x", encoding="utf-8") as err:
            err.write("$ " + " ".join(cmd[:-1]) + " <prompt>\n\n")
            err.flush()
            try:
                proc = subprocess.Popen(cmd, cwd=work, stdin=subprocess.DEVNULL, stdout=out, stderr=err, text=True,
                                        env={**os.environ, "NO_COLOR": "1"})
            except FileNotFoundError as error:
                raise CodexMissing("codex 실행 파일을 찾을 수 없음. `npm i -g @openai/codex` 로 설치하고 `hpr doctor` 로 확인",
                                   backend=backend, model=role_cfg.get("model"), effort=role_cfg.get("effort"), web_search=web_search) from error
            try:
                _wait_with_heartbeat(proc, events, codex_cfg.get("timeout", 900), heartbeat)
            except subprocess.TimeoutExpired as error:
                parsed = parse_events(events)
                tail = stderr.read_text(encoding="utf-8", errors="replace")[-4000:] + events.read_text(encoding="utf-8", errors="replace")[-4000:]
                raise CodexError(f"{name}: 시간 초과 {codex_cfg.get('timeout')}s", usage=parsed["usage"],
                                 usage_known=parsed["usage_known"], stderr=tail, seconds=elapsed(), **extra_meta) from error
        if proc.returncode != 0:
            parsed = parse_events(events)
            tail = stderr.read_text(encoding="utf-8", errors="replace")[-4000:] + events.read_text(encoding="utf-8", errors="replace")[-4000:]
            limited, resets = detect_usage_limit(tail)
            if limited:
                raise UsageLimit(f"{name}: 사용량 한도 도달" + (f" (리셋 {resets})" if resets else ""), resets, usage=parsed["usage"],
                                usage_known=parsed["usage_known"], stderr=tail, seconds=elapsed(), **extra_meta)
            if detect_auth_error(tail):
                raise AuthRequired(f"{name}: 로그인이 만료됐거나 인증 실패. `codex login` 뒤 `hpr resume` (로그: {stderr})",
                                  usage=parsed["usage"], usage_known=parsed["usage_known"], stderr=tail, seconds=elapsed(), **extra_meta)
            raise CodexError(f"{name}: codex exec 종료코드 {proc.returncode} (로그: {stderr})",
                             usage=parsed["usage"], usage_known=parsed["usage_known"], stderr=tail, seconds=elapsed(), **extra_meta)
        if not out_file.exists():
            parsed = parse_events(events)
            raise CodexError(f"{name}: 마지막 메시지 파일 없음", usage=parsed["usage"], usage_known=parsed["usage_known"], seconds=elapsed(), **extra_meta)
        parsed = parse_events(events)
        try:
            result = _extract_json(out_file.read_text(encoding="utf-8"))
        except CodexError as error:
            raise CodexError(f"{name}: 모델 응답 파싱 실패 {error}", usage=parsed["usage"], usage_known=parsed["usage_known"],
                             stderr=(stderr.read_text(encoding="utf-8", errors="replace")[-4000:] if stderr else ""),
                             seconds=elapsed(), **extra_meta) from error
        return result, {"step": name, "backend": backend, "model": role_cfg.get("model"), "effort": role_cfg.get("effort"),
                        "web_search": web_search, "seconds": elapsed(), "attempt": attempt, **parsed}
    finally:
        shutil.rmtree(work, ignore_errors=True)
