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
import time
from pathlib import Path


class CodexError(RuntimeError):
    pass


class UsageLimit(CodexError):
    """구독 사용량 한도·요청 제한. 재시도하지 않고 멈춘 뒤 리셋 후 resume 한다."""
    def __init__(self, message: str, resets_at: str = ""):
        super().__init__(message)
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
        return json.loads(match.group(1))
    raise CodexError("모델 답이 JSON 이 아님")


def parse_events(path: Path) -> dict:
    """--json 이벤트 파일에서 사용량과 도구 사용 횟수를 뽑는다."""
    usage, kinds = {}, {}
    if not path.exists():
        return {"usage": usage, "items": kinds}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = event["usage"]
        item = event.get("item") or {}
        if event.get("type") == "item.completed" and item.get("type"):
            kinds[item["type"]] = kinds.get(item["type"], 0) + 1
    return {"usage": usage, "items": kinds}


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


def run_step(name: str, prompt: str, schema: dict, inputs: dict[str, str], role_cfg: dict, codex_cfg: dict,
             log_dir: Path, mock=None, web_search: bool = False, heartbeat=None) -> tuple[dict, dict]:
    backend = os.environ.get("HPR_BACKEND", "codex")
    started = time.time()
    if backend == "mock":
        if mock is None:
            raise CodexError("mock 응답 생성기가 없음")
        # mock 도 입력 크기에 비례한 토큰을 보고해 예산·비용 로직을 테스트할 수 있게 한다(4자 ≈ 1토큰 가정)
        approx_in = (sum(len(v) for v in inputs.values()) + len(prompt)) // 4
        return mock(name, prompt, inputs), {"step": name, "backend": "mock", "seconds": round(time.time() - started, 2),
                                            "usage": {"input_tokens": approx_in, "cached_input_tokens": 0, "output_tokens": 200}, "items": {}}
    work = Path(tempfile.mkdtemp(prefix=f"hpr-{name}-"))
    try:
        write_inputs(work, inputs)
        schema_path = work / "_schema.json"
        schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
        out_file = work / "_last_message.txt"
        cmd = build_cmd(work, schema_path, out_file, role_cfg, codex_cfg, web_search) + [prompt]
        log_dir.mkdir(parents=True, exist_ok=True)
        events = log_dir / f"{name}.events.jsonl"
        with open(events, "w", encoding="utf-8") as out, open(log_dir / f"{name}.stderr.log", "w", encoding="utf-8") as err:
            err.write("$ " + " ".join(cmd[:-1]) + " <prompt>\n\n")
            err.flush()
            try:
                proc = subprocess.Popen(cmd, cwd=work, stdin=subprocess.DEVNULL, stdout=out, stderr=err, text=True,
                                        env={**os.environ, "NO_COLOR": "1"})
            except FileNotFoundError as error:
                raise CodexMissing("codex 실행 파일을 찾을 수 없음. `npm i -g @openai/codex` 로 설치하고 `hpr doctor` 로 확인") from error
            try:
                _wait_with_heartbeat(proc, events, codex_cfg.get("timeout", 900), heartbeat)
            except subprocess.TimeoutExpired as error:
                raise CodexError(f"{name}: 시간 초과 {codex_cfg.get('timeout')}s") from error
        if proc.returncode != 0:
            tail = (log_dir / f"{name}.stderr.log").read_text(encoding="utf-8", errors="replace")[-4000:]
            tail += events.read_text(encoding="utf-8", errors="replace")[-4000:] if events.exists() else ""
            limited, resets = detect_usage_limit(tail)
            if limited:
                raise UsageLimit(f"{name}: 사용량 한도 도달" + (f" (리셋 {resets})" if resets else ""), resets)
            if detect_auth_error(tail):
                raise AuthRequired(f"{name}: 로그인이 만료됐거나 인증 실패. `codex login` 뒤 `hpr resume` (로그: {log_dir / (name + '.stderr.log')})")
            raise CodexError(f"{name}: codex exec 종료코드 {proc.returncode} (로그: {log_dir / (name + '.stderr.log')})")
        if not out_file.exists():
            raise CodexError(f"{name}: 마지막 메시지 파일 없음")
        result = _extract_json(out_file.read_text(encoding="utf-8"))
        parsed = parse_events(events)
        return result, {"step": name, "backend": "codex", "model": role_cfg.get("model"), "effort": role_cfg.get("effort"),
                        "web_search": web_search, "seconds": round(time.time() - started, 1), **parsed}
    finally:
        shutil.rmtree(work, ignore_errors=True)
