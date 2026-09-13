"""창고(vault): 마크다운 노트가 정본, SQLite FTS5 는 언제든 다시 만들 수 있는 캐시."""
import json
import re
import sqlite3
import time
from pathlib import Path

from .manifest import atomic_write


def slugify(text: str, limit: int = 60) -> str:
    slug = re.sub(r"[^0-9A-Za-z가-힣]+", "-", text).strip("-").lower()
    return slug[:limit] or "note"


def write_note(notes_dir: Path, source_id: str, page: dict) -> Path:
    front = {"id": source_id, "url": page["url"], "final_url": page.get("final_url", page["url"]),
             "title": page.get("title", ""), "domain": page.get("domain", ""), "via": page.get("via", ""),
             "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "chars": len(page["text"]), "sha256": page["sha256"],
             "status": page.get("status", ""), "error": page.get("error", "")}
    body = "---\n" + "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in front.items()) + "\n---\n\n"
    body += f"# {front['title'] or front['url']}\n\n{page['text']}\n"
    path = notes_dir / f"{source_id}-{slugify(front['title'] or front['domain'])}.md"
    atomic_write(path, body)
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
    db.execute("DROP TABLE IF EXISTS notes")
    db.execute("CREATE VIRTUAL TABLE notes USING fts5(id, title, url, domain, path, body)")
    count = 0
    for path in sorted(notes_dir.glob("*.md")) if notes_dir.is_dir() else []:
        front = read_front(path)
        db.execute("INSERT INTO notes VALUES (?,?,?,?,?,?)",
                   (front.get("id", ""), front.get("title", ""), front.get("url", ""), front.get("domain", ""), str(path), note_body(path)))
        count += 1
    db.commit()
    db.close()
    return count


def search(root: Path, query: str, limit: int = 10) -> list[dict]:
    db = sqlite3.connect(root / "research" / "index.sqlite")
    rows = db.execute("SELECT id, title, url, path, snippet(notes, 5, '[', ']', '…', 18) FROM notes WHERE notes MATCH ? ORDER BY rank LIMIT ?",
                      (query, limit)).fetchall()
    db.close()
    return [{"id": r[0], "title": r[1], "url": r[2], "path": r[3], "snippet": r[4]} for r in rows]
