"""기존 vault note를 읽기 전용으로 재사용한다. 네트워크·색인 재생성은 하지 않는다."""
import datetime as dt
import hashlib
import re
import sqlite3
from pathlib import Path

from . import vault


_ID = re.compile(r"^N-[0-9a-f]{64}$")
_TERM = re.compile(r"[0-9A-Za-z가-힣]+")


def _when(value: object) -> dt.datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    # 구형 vault의 timezone 없는 fetched_at은 저장한 컴퓨터의 로컬 시각이다.
    return parsed.astimezone(dt.timezone.utc)


def _body_without_heading(path: Path, front: dict) -> str:
    body = vault.note_body(path)
    heading = "# " + str(front.get("title") or front.get("url") or "")
    prefix = "\n" + heading + "\n\n"
    if not body.startswith(prefix):
        return ""
    body = body[len(prefix):]
    return body[:-1] if body.endswith("\n") else body


def _validated(path: Path, front: dict, now: dt.datetime, max_age_days: int) -> tuple[bool, str]:
    if not _ID.fullmatch(str(front.get("id", ""))) or not isinstance(front.get("url"), str):
        return False, ""
    if not front["url"].startswith(("http://", "https://")) or not front.get("title"):
        return False, ""
    fetched = _when(front.get("fetched_at"))
    if fetched is None or fetched > now or (now - fetched).total_seconds() > max_age_days * 86400:
        return False, ""
    sha = front.get("sha256")
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
        return False, ""
    text = _body_without_heading(path, front)
    if not text or hashlib.sha256(text.encode("utf-8")).hexdigest() != sha:
        return False, ""
    metadata = {key: front.get(key, "") for key in
                ("url", "final_url", "title", "domain", "via", "official", "published", "published_source",
                 "modified", "modified_source", "canonical")}
    try:
        return vault._snapshot_id({"text": text, **metadata}) == front["id"], text
    except (AttributeError, TypeError, ValueError):
        return False, ""


def _valid_snapshot(path: Path, front: dict, now: dt.datetime, max_age_days: int) -> bool:
    return _validated(path, front, now, max_age_days)[0]


def _fts_query(query: str) -> str:
    terms = list(dict.fromkeys(_TERM.findall(query)))
    return " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)


def reusable_sources(root: Path, query: str, max_age_days: int = 30, limit: int = 3,
                     now: dt.datetime | None = None) -> list[dict]:
    """질문과 일치하는 신선한 N-ID note를 최신 URL별로 반환한다."""
    if limit <= 0 or max_age_days < 0:
        return []
    fts = root / "research" / "index.sqlite"
    if not fts.is_file():
        return []
    fts_query = _fts_query(query)
    if not fts_query:
        return []
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None:
        current = current.astimezone(dt.timezone.utc)
    try:
        hits = vault.search(root, fts_query, max(limit * 10, limit))
    except (sqlite3.Error, OSError, ValueError):
        return []
    candidates = []
    for hit in hits:
        path = Path(hit.get("path", ""))
        try:
            if not path.resolve().is_relative_to((root / "research" / "notes").resolve()):
                continue
            front = vault.read_front(path)
            if not _valid_snapshot(path, front, current, max_age_days):
                continue
        except (OSError, UnicodeError, ValueError):
            continue
        candidates.append({"url": front["url"], "title": front["title"], "via": "vault",
                           "note_id": front["id"], "path": str(path), "fetched_at": front["fetched_at"],
                           "published": front.get("published", ""), "modified": front.get("modified", ""),
                           "domain": front.get("domain", ""), "canonical": front.get("canonical", "")})
    candidates.sort(key=lambda row: _when(row["fetched_at"]), reverse=True)
    unique, seen = [], set()
    for row in candidates:
        if row["url"] in seen:
            continue
        seen.add(row["url"])
        unique.append(row)
        if len(unique) >= limit:
            break
    return unique


def cached_page(root: Path, candidate: dict, max_age_days: int = 30,
                now: dt.datetime | None = None) -> dict | None:
    """후보 note를 다시 검증해 fetch_one과 호환되는 page로 반환한다."""
    if max_age_days < 0 or not isinstance(candidate, dict):
        return None
    notes_root = (root / "research" / "notes").resolve()
    try:
        path = Path(candidate.get("path", "")).resolve()
        path.relative_to(notes_root)
    except (AttributeError, OSError, ValueError):
        return None
    if not path.name.startswith("N-") or path.suffix != ".md" or not path.is_file():
        return None
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None:
        current = current.astimezone(dt.timezone.utc)
    try:
        front = vault.read_front(path)
        valid, text = _validated(path, front, current, max_age_days)
    except (OSError, UnicodeError, ValueError):
        return None
    if not valid or candidate.get("note_id") != front.get("id") or candidate.get("url") != front.get("url"):
        return None
    return {"url": front["url"], "final_url": front.get("final_url", front["url"]), "title": front["title"],
            "domain": front.get("domain", ""), "via": "vault", "official": bool(front.get("official")),
            "published": front.get("published", ""), "published_source": front.get("published_source", ""),
            "modified": front.get("modified", ""), "modified_source": front.get("modified_source", ""),
            "canonical": front.get("canonical", ""), "status": front.get("status", 200), "error": "",
            "text": text, "sha256": front["sha256"], "fetched_at": front["fetched_at"],
            "snapshot_path": str(path)}
