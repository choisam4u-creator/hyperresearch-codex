"""창고(vault): 마크다운 노트가 정본, SQLite FTS5 는 언제든 다시 만들 수 있는 캐시."""
import json
import hashlib
import os
import re
import sqlite3
import tempfile
import time
from pathlib import Path

def slugify(text: str, limit: int = 60) -> str:
    slug = re.sub(r"[^0-9A-Za-z가-힣]+", "-", text).strip("-").lower()
    return slug[:limit] or "note"


def _snapshot_metadata(page: dict) -> dict:
    """재방문 때 의미가 달라졌는지 판단할 메타만, 고정 순서로 만든다."""
    return {"url": page["url"], "final_url": page.get("final_url", page["url"]), "title": page.get("title", ""),
            "domain": page.get("domain", ""), "via": page.get("via", ""), "official": bool(page.get("official")),
            "published": page.get("published", ""), "published_source": page.get("published_source", ""),
            "modified": page.get("modified", ""), "modified_source": page.get("modified_source", ""),
            "canonical": page.get("canonical", "")}


def _snapshot_id(page: dict) -> str:
    payload = {"text": page["text"], "metadata": _snapshot_metadata(page)}
    stable = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "N-" + hashlib.sha256(stable.encode("utf-8")).hexdigest()


def _atomic_create(path: Path, text: str) -> None:
    """완성된 임시 파일을 hard-link로 공개해 기존 스냅샷을 절대 덮어쓰지 않는다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".hpr-note-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_note(notes_dir: Path, source_id: str, page: dict) -> Path:
    """가져온 페이지를 불변 스냅샷으로 저장하고, 같은 스냅샷은 기존 경로를 돌려준다."""
    note_id = _snapshot_id(page)
    front = {"id": note_id, **_snapshot_metadata(page),
             "fetched_at": page.get("fetched_at") or time.strftime("%Y-%m-%dT%H:%M:%S"),
             "chars": len(page["text"]), "sha256": page.get("sha256") or hashlib.sha256(page["text"].encode("utf-8")).hexdigest(),
             "status": page.get("status", ""), "error": page.get("error", "")}
    body = "---\n" + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in front.items()) + "\n---\n\n"
    body += f"# {front['title'] or front['url']}\n\n{page['text']}\n"
    path = notes_dir / f"{note_id}-{slugify(front['title'] or front['domain'])}.md"
    _atomic_create(path, body)
    return path


def read_front(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    head = text.split("\n---\n", 1)[0][4:]
    out = {}
    for line in head.splitlines():
        key, _, value = line.partition(": ")
        try:
            out[key] = json.loads(value)
        except ValueError:
            out[key] = value
    return out


def note_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return text.split("\n---\n", 1)[1] if text.startswith("---\n") else text


def sync(root: Path) -> int:
    """마크다운 전체를 다시 읽어 FTS5 색인을 새로 만든다. 색인은 지워도 된다."""
    notes_dir = root / "research" / "notes"
    db = sqlite3.connect(root / "research" / "index.sqlite")
    try:
        # 여러 run이 같은 vault를 갱신해도 DROP/CREATE 사이를 다른 writer가
        # 관찰하지 않도록 전체 재구축을 하나의 쓰기 트랜잭션으로 직렬화한다.
        db.execute("BEGIN IMMEDIATE")
        db.execute("DROP TABLE IF EXISTS notes")
        db.execute("CREATE VIRTUAL TABLE notes USING fts5(id, title, url, domain, path, body)")
        count = 0
        for path in sorted(notes_dir.glob("*.md")) if notes_dir.is_dir() else []:
            front = read_front(path)
            db.execute("INSERT INTO notes VALUES (?,?,?,?,?,?)",
                       (front.get("id", ""), front.get("title", ""), front.get("url", ""), front.get("domain", ""), str(path), note_body(path)))
            count += 1
        db.commit()
        return count
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def search(root: Path, query: str, limit: int = 10) -> list[dict]:
    db = sqlite3.connect(root / "research" / "index.sqlite")
    rows = db.execute("SELECT id, title, url, path, snippet(notes, 5, '[', ']', '…', 18) FROM notes WHERE notes MATCH ? ORDER BY rank LIMIT ?",
                      (query, limit)).fetchall()
    db.close()
    return [{"id": r[0], "title": r[1], "url": r[2], "path": r[3], "snippet": r[4]} for r in rows]
