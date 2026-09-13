"""창고(vault)용 최소 MCP 서버(stdio, 줄 단위 JSON-RPC 2.0). 표준 라이브러리만 쓴다.
Codex 세션이 이전 조사 노트를 검색·읽기 위한 도구 6개. 쓰기 도구는 일부러 없다."""
import json
import sys
from pathlib import Path

from . import vault

TOOLS = [
    {"name": "search_notes", "description": "창고 노트 전문 검색(FTS5). query 는 검색어.", "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["query"]}},
    {"name": "read_note", "description": "노트 하나 읽기. id(S3 처럼) 또는 path.", "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}, "path": {"type": "string"}}}},
    {"name": "list_notes", "description": "노트 목록(최근 순).", "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer"}}}},
    {"name": "vault_status", "description": "노트 수·색인 존재·실행 수.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "list_runs", "description": "실행(run) 목록과 단계 상태.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "read_report", "description": "실행의 최종 보고서 읽기. run_id 필요.", "inputSchema": {"type": "object", "properties": {"run_id": {"type": "string"}}, "required": ["run_id"]}},
]


def _notes(root: Path):
    d = root / "research" / "notes"
    return sorted(d.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True) if d.is_dir() else []


def call_tool(root: Path, name: str, args: dict) -> str:
    if name == "search_notes":
        if not (root / "research" / "index.sqlite").exists():
            vault.sync(root)
        return json.dumps(vault.search(root, args["query"], int(args.get("limit", 10))), ensure_ascii=False, indent=1)
    if name == "read_note":
        if args.get("path"):
            p = Path(args["path"])
            if not p.resolve().is_relative_to((root / "research").resolve()):
                return "research/ 밖 경로는 읽지 않는다"
        else:
            p = next((n for n in _notes(root) if n.name.startswith(args.get("id", "") + "-")), None)
        return p.read_text(encoding="utf-8") if p and p.exists() else "노트 없음"
    if name == "list_notes":
        return "\n".join(f"{vault.read_front(p).get('id','')}\t{vault.read_front(p).get('title','')[:70]}\t{p.name}" for p in _notes(root)[: int(args.get("limit", 30))]) or "노트 없음"
    if name == "vault_status":
        runs = root / "research" / "runs"
        return json.dumps({"notes": len(_notes(root)), "index": (root / "research" / "index.sqlite").exists(),
                           "runs": len(list(runs.iterdir())) if runs.is_dir() else 0}, ensure_ascii=False)
    if name == "list_runs":
        runs = root / "research" / "runs"
        out = []
        for d in sorted(runs.iterdir()) if runs.is_dir() else []:
            mf = d / "manifest.json"
            if mf.exists():
                m = json.loads(mf.read_text())
                out.append(f"{d.name}\t{m.get('tier')}\t{m['prompt'][:50]}\t" + ",".join(f"{s['name']}:{s['status']}" for s in m["steps"]))
        return "\n".join(out) or "실행 없음"
    if name == "read_report":
        p = root / "research" / "runs" / args["run_id"] / "final_report.md"
        return p.read_text(encoding="utf-8") if p.exists() else "보고서 없음"
    return f"모르는 도구: {name}"


def serve(root: Path, stdin=sys.stdin, stdout=sys.stdout) -> None:
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
        if method == "initialize":
            result = {"protocolVersion": params.get("protocolVersion", "2025-03-26"), "capabilities": {"tools": {}},
                      "serverInfo": {"name": "hyperresearch-codex", "version": "0.2.0"}}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            try:
                text = call_tool(root, params.get("name", ""), params.get("arguments") or {})
                result = {"content": [{"type": "text", "text": text}], "isError": False}
            except Exception as error:  # noqa: BLE001 - 도구 오류는 응답으로 돌려준다
                result = {"content": [{"type": "text", "text": f"오류: {type(error).__name__}: {error}"}], "isError": True}
        elif method == "ping":
            result = {}
        elif mid is None:
            continue  # notifications/initialized 등
        else:
            stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"method not found: {method}"}}) + "\n")
            stdout.flush()
            continue
        if mid is not None:
            stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}, ensure_ascii=False) + "\n")
            stdout.flush()
