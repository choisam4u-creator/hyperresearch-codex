"""가져오기: httpx 병렬 다운로드, html.parser 본문 추출, 게시일·정본 URL 메타 추출. PDF 는 pypdf 가 있으면 읽는다."""
import hashlib
import json
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

import httpx


class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.title, self._skip_tags, self._in_title = [], "", [], False
        self.meta, self.canonical, self.times, self.jsonld = {}, "", [], []
        self._in_ld = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self._skip_tags.append(tag)
        # HTMLParser는 브라우저의 묵시적 종료 태그 규칙을 적용하지 않는다.
        # 닫히지 않은 header/nav 뒤 실제 본문은 복구하되, aside/form 안은 숨긴다.
        elif tag in {"main", "article"} and self._skip_tags and all(item in {"header", "nav"} for item in self._skip_tags):
            self._skip_tags.clear()
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if key and a.get("content"):
                self.meta.setdefault(key, a["content"])
        if tag == "link" and (a.get("rel") or "").lower() == "canonical" and a.get("href"):
            self.canonical = a["href"]
        if tag == "time" and a.get("datetime"):
            self.times.append((a["datetime"], a))
        if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._in_ld = True
        if tag in {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "tr", "section", "article"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            for index in range(len(self._skip_tags) - 1, -1, -1):
                if self._skip_tags[index] == tag:
                    del self._skip_tags[index]
                    break
        if tag == "title":
            self._in_title = False
        if tag == "script":
            self._in_ld = False

    def handle_data(self, data):
        if self._in_ld:
            self.jsonld.append(data)
        elif self._in_title:
            self.title += data
        elif not self._skip_tags:
            self.parts.append(data)


_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _dated(value: str) -> str:
    match = _DATE.search(value)
    return match.group(0) if match else ""


def date_metadata(parser: _Text) -> dict:
    """게시일과 수정일을 섞지 않고, 각 날짜의 추출 근거도 남긴다."""
    result = {"published": "", "published_source": "", "modified": "", "modified_source": ""}
    published_keys = ("article:published_time", "datepublished", "date", "dc.date", "dc.date.issued", "pubdate", "publish_date")
    modified_keys = ("article:modified_time", "og:updated_time", "datemodified", "dateupdated", "last-modified")
    for key in published_keys:
        value = _dated(parser.meta.get(key, ""))
        if value:
            result["published"], result["published_source"] = value, f"meta:{key}"
            break
    for key in modified_keys:
        value = _dated(parser.meta.get(key, ""))
        if value:
            result["modified"], result["modified_source"] = value, f"meta:{key}"
            break
    for blob in parser.jsonld:
        try:
            data = json.loads(blob)
        except ValueError:
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if not result["published"]:
                    for key in ("datePublished", "dateCreated"):
                        value = node.get(key, "")
                        if isinstance(value, str) and _dated(value):
                            result["published"], result["published_source"] = _dated(value), f"jsonld:{key}"
                            break
                if not result["modified"]:
                    value = node.get("dateModified", "")
                    if isinstance(value, str) and _dated(value):
                        result["modified"], result["modified_source"] = _dated(value), "jsonld:dateModified"
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    for value, attrs in parser.times:
        date = _dated(value)
        if not date:
            continue
        marker = " ".join(str(attrs.get(key, "")).lower() for key in ("itemprop", "class", "rel"))
        if not result["published"] and not any(word in marker for word in ("modified", "updated")):
            result["published"], result["published_source"] = date, "time:datetime"
        if not result["modified"] and any(word in marker for word in ("modified", "updated")):
            result["modified"], result["modified_source"] = date, "time:datetime"
    return result


def published_date(parser: _Text) -> str:
    """기존 호출자 호환용 게시일 값."""
    return date_metadata(parser)["published"]


def html_to_text(raw: str) -> tuple[str, str, dict]:
    parser = _Text()
    parser.feed(raw)
    text = re.sub(r"[ \t\r\f\v]+", " ", "".join(parser.parts))
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    meta = {**date_metadata(parser), "canonical": parser.canonical}
    return parser.title.strip(), text, meta


def _pdf_to_text(data: bytes) -> str:
    try:
        import io
        from pypdf import PdfReader
    except ImportError:
        return ""
    reader = PdfReader(io.BytesIO(data))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages[:40])


def _decode_html(data: bytes, content_type: str) -> str:
    """HTTP charset을 우선하고, 없으면 HTML 선언을 사용해 UTF-8 이외 페이지도 보존한다."""
    match = re.search(r"charset\s*=\s*[\"']?([^\s;\"'>]+)", content_type, re.I)
    if not match:
        head = data[:4096].decode("ascii", errors="ignore")
        match = re.search(r"<meta[^>]+charset\s*=\s*[\"']?([^\s;\"'>]+)", head, re.I)
    encoding = match.group(1) if match else "utf-8"
    try:
        return data.decode(encoding, errors="replace")
    except LookupError:
        return data.decode("utf-8", errors="replace")


def fetch_one(row: dict, cfg: dict) -> dict:
    url = row["url"]
    lm = ""
    out = {"url": url, "title": row.get("title", ""), "via": row.get("via", ""), "official": bool(row.get("official")),
           "published": row.get("published", ""), "published_source": "row" if row.get("published") else "", "modified": "", "modified_source": "",
           "canonical": "", "status": "", "text": "", "error": ""}
    try:
        with httpx.Client(headers={"User-Agent": cfg["user_agent"]}, timeout=cfg["timeout"], follow_redirects=True) as client:
            with client.stream("GET", url) as response:
                out["status"] = str(response.status_code)
                ctype = response.headers.get("content-type", "")
                out["final_url"] = str(response.url)
                lm = response.headers.get("last-modified", "")
                data = b""
                if out["status"].startswith("2"):
                    for chunk in response.iter_bytes():
                        remaining = cfg["max_bytes"] - len(data)
                        if remaining <= 0 or len(chunk) > remaining:
                            data += chunk[:max(remaining, 0)]
                            out["error"] = "download_truncated"
                            break
                        data += chunk
                else:
                    out["error"] = f"http_{out['status']}"
        if "pdf" in ctype or url.lower().endswith(".pdf"):
            try:
                out["text"] = _pdf_to_text(data)
            except Exception:  # pypdf has several parse-error types across releases.
                out["error"] = out["error"] or "pdf_parse_failed"
            if not out["text"] and not out["error"]:
                out["error"] = "pdf_unsupported_or_empty"
        else:
            title, text, meta = html_to_text(_decode_html(data, ctype))
            out["title"] = out["title"] or title
            out["text"] = text
            out["published"] = out["published"] or meta["published"]
            out["published_source"] = out["published_source"] or meta["published_source"]
            out["modified"] = meta["modified"]
            out["modified_source"] = meta["modified_source"]
            out["canonical"] = meta["canonical"]
        if lm:
            try:
                from email.utils import parsedate_to_datetime
                last_modified = parsedate_to_datetime(lm).strftime("%Y-%m-%d")
                if not out["published"]:
                    out["published"] = last_modified
                    out["published_source"] = "last-modified"
                out["modified"] = out["modified"] or last_modified
                out["modified_source"] = out["modified_source"] or "last-modified"
            except (TypeError, ValueError):
                pass
    except (httpx.HTTPError, httpx.InvalidURL, ValueError, OSError) as error:
        out["error"] = f"fetch_failed:{type(error).__name__}"   # 잘못된 URL·연결 거부·프로토콜 오류 모두 건너뛰고 이유를 남긴다
    out["sha256"] = hashlib.sha256(out["text"].encode("utf-8")).hexdigest()
    try:
        out["domain"] = urllib.parse.urlparse(out.get("final_url") or url).netloc.removeprefix("www.")
    except ValueError:
        out["domain"], out["error"] = "", out["error"] or "fetch_failed:InvalidURL"
    return out


def fetch_all(rows: list[dict], cfg: dict) -> list[dict]:
    with ThreadPoolExecutor(max_workers=cfg["parallel"]) as pool:
        return list(pool.map(lambda r: fetch_one(r, cfg), rows))
