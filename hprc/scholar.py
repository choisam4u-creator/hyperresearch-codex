"""학술 검색(키 없음): arXiv Atom API + OpenAlex works API. 결과는 일반 후보 URL 로 합쳐져 같은 파이프라인을 탄다."""
import re
import urllib.parse
import xml.etree.ElementTree as ET

import httpx

ATOM = "{http://www.w3.org/2005/Atom}"


def arxiv(query: str, limit: int = 5, timeout: int = 20) -> list[dict]:
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode({"search_query": f"all:{query}", "start": 0, "max_results": limit})
    try:
        xml = httpx.get(url, timeout=timeout).text
        root = ET.fromstring(xml)
    except (httpx.HTTPError, ET.ParseError):
        return []
    rows = []
    for entry in root.findall(ATOM + "entry"):
        link = entry.findtext(ATOM + "id", "").replace("http://", "https://")
        rows.append({"url": link, "title": re.sub(r"\s+", " ", entry.findtext(ATOM + "title", "")).strip(),
                     "published": entry.findtext(ATOM + "published", "")[:10], "via": "arxiv", "official": True})
    return rows


def openalex(query: str, limit: int = 5, timeout: int = 20) -> list[dict]:
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode({"search": query, "per-page": limit, "select": "title,publication_date,doi,primary_location,open_access"})
    try:
        data = httpx.get(url, timeout=timeout, headers={"User-Agent": "hyperresearch-codex/0.2"}).json()
    except (httpx.HTTPError, ValueError):
        return []
    rows = []
    for w in data.get("results", []):
        oa = (w.get("open_access") or {}).get("oa_url")
        landing = ((w.get("primary_location") or {}).get("landing_page_url")) or w.get("doi")
        link = oa or landing
        if not link:
            continue
        rows.append({"url": link, "title": w.get("title") or "", "published": w.get("publication_date") or "",
                     "via": "openalex" + ("-oa" if oa else ""), "official": True})
    return rows
