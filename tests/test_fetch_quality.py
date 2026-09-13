"""합성 응답으로 fetch 본문·날짜·오류 표기를 검증한다. 네트워크는 사용하지 않는다."""
import unittest
import socket
from unittest import mock

import httpx

from hprc import fetch


CFG = {"user_agent": "test", "timeout": 1, "max_bytes": 64, "parallel": 1, "allow_private_hosts": []}
REAL_CLIENT = httpx.Client


def response(status, body=b"", headers=None):
    return httpx.Response(status, content=body, headers=headers or {}, request=httpx.Request("GET", "https://example.test/a"))


class FetchQualityTests(unittest.TestCase):
    def setUp(self):
        self.dns = mock.patch("hprc.safe_http.socket.getaddrinfo", return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))
        ])
        self.dns.start()

    def tearDown(self):
        self.dns.stop()

    def client_for(self, handler):
        transport = httpx.MockTransport(handler)
        return mock.patch("hprc.fetch.httpx.Client", side_effect=lambda **kwargs: REAL_CLIENT(transport=transport, **kwargs))

    def test_unclosed_navigation_does_not_hide_article_body(self):
        title, text, _ = fetch.html_to_text("<header>브랜드<img src=x><nav>메뉴<main><article><h1>제목</h1><p>검증할 본문</p></article></main>")
        self.assertEqual("", title)
        self.assertIn("검증할 본문", text)
        self.assertNotIn("브랜드", text)
        self.assertNotIn("메뉴", text)

    def test_article_inside_hidden_aside_remains_hidden(self):
        _, text, _ = fetch.html_to_text("<aside>광고<article>숨겨진 본문</article></aside><article>실제 본문</article>")
        self.assertNotIn("숨겨진 본문", text)
        self.assertIn("실제 본문", text)

    def test_published_and_modified_dates_are_distinct_with_sources(self):
        _, _, meta = fetch.html_to_text("""<meta property='article:published_time' content='2023-01-02'>
        <meta property='article:modified_time' content='2024-03-04'><script type='application/ld+json'>
        {\"datePublished\": \"2020-01-01\", \"dateModified\": \"2025-05-06\"}</script>""")
        self.assertEqual("2023-01-02", meta["published"])
        self.assertEqual("meta:article:published_time", meta["published_source"])
        self.assertEqual("2024-03-04", meta["modified"])
        self.assertEqual("meta:article:modified_time", meta["modified_source"])

    def test_non_utf8_html_uses_declared_charset(self):
        body = "<title>café</title><article><p>olá 본문</p></article>".encode("latin-1", errors="replace")
        with self.client_for(lambda request: response(200, body, {"content-type": "text/html; charset=iso-8859-1"})):
            page = fetch.fetch_one({"url": "https://example.test/a"}, CFG)
        self.assertEqual("café", page["title"])
        self.assertIn("olá", page["text"])

    def test_last_modified_is_kept_as_modified_when_published_exists(self):
        body = "<meta property='article:published_time' content='2023-01-02'><article>본문</article>".encode()
        headers = {"last-modified": "Thu, 04 May 2024 12:00:00 GMT"}
        with self.client_for(lambda request: response(200, body, headers)):
            page = fetch.fetch_one({"url": "https://example.test/a"}, CFG)
        self.assertEqual("2023-01-02", page["published"])
        self.assertEqual("2024-05-04", page["modified"])
        self.assertEqual("last-modified", page["modified_source"])

    def test_http_failure_is_not_parsed_as_source_text(self):
        with self.client_for(lambda request: response(404, "<article>오류 본문</article>".encode())):
            page = fetch.fetch_one({"url": "https://example.test/a"}, CFG)
        self.assertEqual("http_404", page["error"])
        self.assertEqual("", page["text"])

    def test_truncated_download_is_explicit_and_capped(self):
        with self.client_for(lambda request: response(200, b"<article>" + b"x" * 100 + b"</article>")):
            page = fetch.fetch_one({"url": "https://example.test/a"}, CFG)
        self.assertEqual("download_truncated", page["error"])
        self.assertLessEqual(len(page["text"].encode("utf-8")), CFG["max_bytes"])

    def test_pdf_parse_failure_is_readable(self):
        with self.client_for(lambda request: response(200, b"%PDF-bad", {"content-type": "application/pdf"})), \
             mock.patch("hprc.fetch._pdf_to_text", side_effect=RuntimeError("bad pdf")):
            page = fetch.fetch_one({"url": "https://example.test/a.pdf"}, CFG)
        self.assertEqual("pdf_parse_failed", page["error"])
        self.assertEqual("", page["text"])
