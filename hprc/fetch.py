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
        self.parts, self.title, self._skip, self._in_title = [], "", 0, False
        self.meta, self.canonical, self.times, self.jsonld = {}, "", [], []
        self._in_ld = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if key and a.get("content"):
                self.meta.setdefault(key, a["content"])
        if tag == "link" and (a.get("rel") or "").lower() == "canonical" and a.get("href"):
            self.canonical = a["href"]
        if tag == "time" and a.get("datetime"):
            self.times.append(a["datetime"])
        if tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._in_ld = True
        if tag in {"p", "br", "div", "li", "h1", "h2", "h3", "h4", "tr", "section", "article"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False
        if tag == "script":
            self._in_ld = False

    def handle_data(self, data):
        if self._in_ld:
            self.jsonld.append(data)
        elif self._in_title:
            self.title += data
        elif not self._skip:
            self.parts.append(data)


_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def published_date(parser: _Text) -> str:
    """게시일 후보를 우선순위대로 찾아 YYYY-MM-DD 로. 없으면 빈 문자열."""
    keys = ("article:published_time", "datepublished", "date", "dc.date", "dc.date.issued", "pubdate", "publish_date",
            "og:updated_time", "article:modified_time", "last-modified")
    for key in keys:
        value = parser.meta.get(key, "")
        if value and _DATE.search(value):
            return _DATE.search(value).group(0)
    for blob in parser.jsonld:
        try:
            data = json.loads(blob)
        except ValueError:
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                for k in ("datePublished", "dateCreated", "dateModified"):
                    if isinstance(node.get(k), str) and _DATE.search(node[k]):
                        return _DATE.search(node[k]).group(0)
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
    for value in parser.times:
        if _DATE.search(value):
            return _DATE.search(value).group(0)
    return ""


def html_to_text(raw: str) -> tuple[str, str, dict]:
    parser = _Text()
    parser.feed(raw)
    text = re.sub(r"[ \t\r\f\v]+", " ", "".join(parser.parts))
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    meta = {"published": published_date(parser), "canonical": parser.canonical}
    return parser.title.strip(), text, meta


def _pdf_to_text(data: bytes) -> str:
    try:
        import io
        from pypdf import PdfReader
    except ImportError:
        return ""
    reader = PdfReader(io.BytesIO(data))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages[:40])


def fetch_one(row: dict, cfg: dict) -> dict:
    url = row["url"]
    lm = ""
    out = {"url": url, "title": row.get("title", ""), "via": row.get("via", ""), "official": bool(row.get("official")),
           "published": row.get("published", ""), "canonical": "", "status": "", "text": "", "error": ""}
    try:
        with httpx.Client(headers={"User-Agent": cfg["user_agent"]}, timeout=cfg["timeout"], follow_redirects=True) as client:
            with client.stream("GET", url) as response:
                out["status"] = str(response.status_code)
                ctype = response.headers.get("content-type", "")
                data = b""
                for chunk in response.iter_bytes():
                    data += chunk
                    if len(data) > cfg["max_bytes"]:
                        break
                out["final_url"] = str(response.url)
                lm = response.headers.get("last-modified", "")
        if "pdf" in ctype or url.lower().endswith(".pdf"):
            out["text"] = _pdf_to_text(data)
            if not out["text"]:
                out["error"] = "pdf_unsupported_or_empty"
        else:
            title, text, meta = html_to_text(data.decode("utf-8", errors="replace"))
            out["title"] = out["title"] or title
            out["text"] = text
            out["published"] = out["published"] or meta["published"]
            out["canonical"] = meta["canonical"]
        if not out["published"] and lm:
            try:
                from email.utils import parsedate_to_datetime
                out["published"] = parsedate_to_datetime(lm).strftime("%Y-%m-%d")
                out["published_source"] = "last-modified"
            except (TypeError, ValueError):
                pass
        if out["status"] and not out["status"].startswith("2"):
            out["error"] = f"http_{out['status']}"
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
