"""검색: (1) Codex 정찰(codex --search, 파이프라인에서 호출) (2) 키 없는 DuckDuckGo HTML (3) 사용자 URL 목록.
결과는 파이썬이 가져온다. 어떤 제공자가 실패해도 다른 제공자와 URL 목록으로 계속 간다."""
import html
import re
import urllib.parse

import httpx

_RESULT = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_TAG = re.compile(r"<[^>]+>")


def _decode_ddg(href: str) -> str:
    parsed = urllib.parse.urlparse(href)
    query = urllib.parse.parse_qs(parsed.query)
    if "uddg" in query:
        return query["uddg"][0]
    return "https:" + href if href.startswith("//") else href


def duckduckgo(query: str, limit: int, user_agent: str, timeout: int = 20) -> list[dict]:
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    try:
        response = httpx.get(url, headers={"User-Agent": user_agent}, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as error:
        return [{"error": f"search_failed:{type(error).__name__}"}]
    rows, seen = [], set()
    for href, title in _RESULT.findall(response.text):
        link = _decode_ddg(html.unescape(href))
        if not link.startswith("http") or link in seen:
            continue
        seen.add(link)
        rows.append({"url": link, "title": html.unescape(_TAG.sub("", title)).strip(), "via": "duckduckgo", "query": query})
        if len(rows) >= limit:
            break
    return rows


def query_variants(prompt: str) -> list[str]:
    """모델 없이 만드는 검색어 변형: 원문, '공식 문서', 'documentation'."""
    base = re.sub(r"\s+", " ", prompt).strip()
    short = base if len(base) <= 80 else base[:80]
    return [short, short + " 공식 문서", short + " official documentation"]


def from_file(path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if line and not line.startswith("#"):
                rows.append({"url": line, "title": "", "via": "user"})
    return rows


def normalize_url(url: str) -> str:
    """가져오기 전에 더 읽기 쉬운 같은 문서로 바꾼다: arXiv pdf → abs, Google 문서 지역 미러·언어 매개변수 제거."""
    m = re.match(r"^https?://(?:www\.)?arxiv\.org/pdf/([0-9.]+(?:v\d+)?)(?:\.pdf)?$", url)
    if m:
        return f"https://arxiv.org/abs/{m.group(1)}"
    # developers.google.cn 은 developers.google.com 의 미러이고, hl= 은 번역본을 고른다(독일어 페이지가 잡힌 실측: tp-light-ko-1b S5)
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:                           # 깨진 URL 은 손대지 않고 가져오기 단계에서 건너뛰게 둔다
        return url
    host = parts.netloc.lower()
    if host in ("developers.google.cn", "developer.android.google.cn"):
        host = host.replace("google.cn", "google.com")
    if host.endswith("google.com") and parts.query:
        q = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True) if k != "hl"]
        parts = parts._replace(query=urllib.parse.urlencode(q))
    if host != parts.netloc.lower():
        parts = parts._replace(netloc=host)
    return urllib.parse.urlunsplit(parts)


def canonical_key(url: str) -> str:
    key = url.split("#")[0].split("?")[0].rstrip("/")
    key = re.sub(r"(/tree/[^/]+/?|/blob/[^/]+/?)$", "", key)
    key = re.sub(r"^https?://(www\.)?", "", key)
    return key.lower()


def prioritize(rows: list[dict], preferred_domains: list[str]) -> list[dict]:
    """정찰(official) → 선호 도메인 → 나머지 순으로, 중복은 정규화 키로 제거."""
    def rank(row):
        try:
            parts = urllib.parse.urlparse(row["url"])
        except ValueError:                       # "https://[::1" 같은 깨진 URL: 순위만 뒤로, 가져오기에서 건너뛴다
            return (2, 1, 1)
        host = parts.netloc.removeprefix("www.")
        pref = any(p in (host + parts.path) for p in preferred_domains)
        return (0 if row.get("official") else 1, 0 if pref else 1, 0 if row.get("via") == "user" else 1)
    seen, out = set(), []
    for row in sorted(rows, key=rank):
        row["url"] = normalize_url(row["url"])
        key = canonical_key(row["url"])
        if key not in seen:
            seen.add(key)
            out.append(row)
    return out


def domain_skew(sources: list[dict]) -> tuple[str, float]:
    """가장 많은 도메인과 그 비율. (예: ('support.google.com', 0.65))"""
    if not sources:
        return "", 0.0
    counts = {}
    for row in sources:
        counts[row.get("domain", "")] = counts.get(row.get("domain", ""), 0) + 1
    top = max(counts, key=counts.get)
    return top, counts[top] / len(sources)
