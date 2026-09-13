import unittest
from unittest import mock

import httpx

from hprc import search


def response(status=200, body=b"", json_data=None):
    kwargs = {"json": json_data} if json_data is not None else {"content": body}
    return httpx.Response(status, **kwargs, request=httpx.Request("GET", "https://search.example/search"))


class SearchDiagnosticsTests(unittest.TestCase):
    def test_duckduckgo_http_status_is_classified_without_body(self):
        with mock.patch("hprc.search.httpx.get", return_value=response(403, b"private response")):
            rows = search.duckduckgo("q", 3, "test")
        self.assertEqual("search_failed:http_403", rows[0]["error"])
        self.assertEqual((403, "http"), (rows[0]["status"], rows[0]["kind"]))
        self.assertNotIn("private", str(rows))

    def test_duckduckgo_429_and_timeout_are_distinct(self):
        with mock.patch("hprc.search.httpx.get", return_value=response(429)):
            limited = search.duckduckgo("q", 3, "test")
        with mock.patch("hprc.search.httpx.get", side_effect=httpx.ReadTimeout("slow")):
            timed_out = search.duckduckgo("q", 3, "test")
        self.assertEqual("search_failed:http_429", limited[0]["error"])
        self.assertEqual("search_failed:timeout", timed_out[0]["error"])

    def test_duckduckgo_empty_results_are_classified(self):
        with mock.patch("hprc.search.httpx.get", return_value=response(200, b"<html></html>")):
            rows = search.duckduckgo("q", 3, "test")
        self.assertEqual("search_failed:empty", rows[0]["error"])

    def test_duckduckgo_malformed_href_is_skipped(self):
        body = b'<a class="result__a" href="https://[::1">bad</a>'
        with mock.patch("hprc.search.httpx.get", return_value=response(200, body)):
            rows = search.duckduckgo("q", 3, "test")
        self.assertEqual("search_failed:empty", rows[0]["error"])

    def test_searxng_requires_explicit_endpoint(self):
        self.assertEqual("search_failed:unconfigured", search.searxng("q", 3, None, "test")[0]["error"])
        self.assertEqual("search_failed:invalid_endpoint", search.searxng("q", 3, "ftp://search", "test")[0]["error"])

    def test_searxng_rejects_endpoint_query_fragment_and_userinfo(self):
        for endpoint in ("https://search.example?key=secret", "https://search.example/#x", "https://user:pass@search.example"):
            with self.subTest(endpoint=endpoint):
                self.assertEqual("search_failed:invalid_endpoint", search.searxng("q", 3, endpoint, "test")[0]["error"])

    def test_searxng_limit_zero_does_not_call_http(self):
        with mock.patch("hprc.search.httpx.get") as get:
            self.assertEqual([], search.searxng("q", 0, "https://search.example", "test"))
            self.assertEqual([], search.duckduckgo("q", 0, "test"))
        get.assert_not_called()

    def test_searxng_allows_explicit_port_and_rejects_invalid_ports(self):
        with mock.patch("hprc.search.httpx.get", return_value=response(json_data={"results": []})) as get:
            search.searxng("q", 3, "http://localhost:8080/searx", "test")
        self.assertEqual("http://localhost:8080/searx/search", get.call_args.args[0])
        with mock.patch("hprc.search.httpx.get") as get:
            for endpoint in ("https://search.example:bad", "https://search.example:99999"):
                self.assertEqual("search_failed:invalid_endpoint", search.searxng("q", 3, endpoint, "test")[0]["error"])
        get.assert_not_called()

    def test_searxng_posts_json_query_and_normalizes_results(self):
        payload = {"results": [{"title": " A ", "url": "https://example.com/a#part"},
                                {"title": "B", "url": "https://example.com/a"}]}
        with mock.patch("hprc.search.httpx.get", return_value=response(json_data=payload)) as get:
            rows = search.searxng("q", 3, "https://search.example", "test")
        self.assertEqual([{"url": "https://example.com/a", "title": "A", "via": "searxng", "query": "q"}], rows)
        self.assertEqual("https://search.example/search", get.call_args.args[0])
        self.assertEqual({"q": "q", "format": "json"}, get.call_args.kwargs["params"])

    def test_searxng_distinguishes_http_errors_and_timeout(self):
        with mock.patch("hprc.search.httpx.get", return_value=response(401)):
            unauthorized = search.searxng("q", 3, "https://search.example", "test")
        with mock.patch("hprc.search.httpx.get", side_effect=httpx.ReadTimeout("slow")):
            timed_out = search.searxng("q", 3, "https://search.example", "test")
        self.assertEqual("search_failed:http_401", unauthorized[0]["error"])
        self.assertEqual("search_failed:timeout", timed_out[0]["error"])

    def test_searxng_malformed_json_and_schema_are_distinct(self):
        with mock.patch("hprc.search.httpx.get", return_value=response(200, b"{")):
            malformed = search.searxng("q", 3, "https://search.example", "test")
        with mock.patch("hprc.search.httpx.get", return_value=response(json_data={"results": {}})):
            schema = search.searxng("q", 3, "https://search.example", "test")
        self.assertEqual("search_failed:malformed_json", malformed[0]["error"])
        self.assertEqual("search_failed:invalid_results_schema", schema[0]["error"])

    def test_searxng_invalid_result_schema_does_not_expose_payload(self):
        with mock.patch("hprc.search.httpx.get", return_value=response(json_data={"results": [{"secret": "token"}]})):
            rows = search.searxng("q", 3, "https://search.example", "test")
        self.assertEqual("search_failed:invalid_result_schema", rows[0]["error"])
        self.assertNotIn("token", str(rows))

    def test_searxng_skips_malformed_result_url(self):
        payload = {"results": [{"title": "bad", "url": "https://[::1"}]}
        with mock.patch("hprc.search.httpx.get", return_value=response(json_data=payload)):
            rows = search.searxng("q", 3, "https://search.example", "test")
        self.assertEqual("search_failed:empty", rows[0]["error"])


if __name__ == "__main__":
    unittest.main()
