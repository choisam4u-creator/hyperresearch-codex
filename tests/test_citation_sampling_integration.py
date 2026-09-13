import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hprc import pipeline


class CitationSamplingIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_citecheck_uses_pre_polish_snapshot_and_final_labels_it(self):
        run = pipeline.Run(self.root, "질문", "full", "cite-snapshot", quiet=True)
        report = "첫 근거입니다. [S1]\n중간 근거입니다. [S2]\n끝 근거입니다. [S1]\n"
        (run.dir / "report.md").write_text(report, encoding="utf-8")
        run.known = {"S1", "S2"}
        run.notes = lambda ids=None, cap=None, query="": {f"{sid}-note.md": "근거" for sid in (ids or run.known)}
        run.call = lambda name, *args, **kwargs: {"checks": [{"sentence": sample["sentence"], "cites": sample["cites"], "supported": True, "reason": "mock"}
                                                        for sample in json.loads(args[2]["samples.json"])]}
        run.step_citecheck()
        data = json.loads((run.dir / "citecheck.json").read_text())
        self.assertEqual("citecheck_report.md", data["sampling"]["line_reference"])
        self.assertEqual(report, (run.dir / "citecheck_report.md").read_text())
        (run.dir / "report.md").write_text("다듬긴 본문입니다. [S1]\n", encoding="utf-8")
        run.sources, run.relevant = [], set()
        (run.dir / "sources.json").write_text(json.dumps({"warnings": []}), encoding="utf-8")
        (run.dir / "findings.json").write_text(json.dumps({"findings": []}), encoding="utf-8")
        final = run.step_final().read_text(encoding="utf-8")
        self.assertIn("citecheck_report.md 기준", final)
        self.assertIn("다듬긴 본문", final)

    def test_searxng_runs_only_after_empty_duckduckgo_with_explicit_endpoint(self):
        run = pipeline.Run(self.root, "질문", "light", "search-fallback", quiet=True)
        run.cfg["search"] = {"providers": ["duckduckgo"], "preferred_domains": [], "query_variants": False,
                             "searxng_endpoint": "https://search.example"}
        with mock.patch("hprc.pipeline.searchmod.duckduckgo", return_value=[]), \
             mock.patch("hprc.pipeline.searchmod.searxng", return_value=[{"url": "https://result.example/a", "title": "결과", "via": "searxng"}]) as searx:
            run.step_search(None, False, False)
        self.assertTrue(searx.called)
        candidates = json.loads((run.dir / "candidates.json").read_text())["candidates"]
        self.assertEqual("searxng", candidates[0]["via"])

    def test_search_keeps_provider_errors_and_no_search_skips_scholar(self):
        run = pipeline.Run(self.root, "질문", "light", "search-errors", quiet=True)
        run.cfg["search"] = {"providers": ["duckduckgo"], "preferred_domains": [], "query_variants": False,
                             "searxng_endpoint": None}
        urls = self.root / "urls.txt"
        urls.write_text("https://user.example/a\n", encoding="utf-8")
        error = {"error": "search_failed:timeout", "provider": "duckduckgo", "kind": "timeout"}
        with mock.patch("hprc.pipeline.searchmod.duckduckgo", return_value=[error]) as ddg, \
             mock.patch("hprc.pipeline.scholarmod.arxiv") as arxiv, \
             mock.patch("hprc.pipeline.scholarmod.openalex") as openalex:
            run.step_search(str(urls), True, True)
        self.assertFalse(ddg.called)
        self.assertFalse(arxiv.called)
        self.assertFalse(openalex.called)
        stats = json.loads((run.dir / "candidates.json").read_text())["stats"]
        self.assertNotIn("errors", stats)

    def test_duckduckgo_error_is_recorded_and_user_candidate_blocks_fallback(self):
        run = pipeline.Run(self.root, "질문", "light", "search-user", quiet=True)
        run.cfg["search"] = {"providers": ["duckduckgo"], "preferred_domains": [], "query_variants": False,
                             "searxng_endpoint": "https://search.example"}
        urls = self.root / "urls.txt"
        urls.write_text("https://user.example/a\n", encoding="utf-8")
        error = {"error": "search_failed:timeout", "provider": "duckduckgo", "kind": "timeout"}
        with mock.patch("hprc.pipeline.searchmod.duckduckgo", return_value=[error]), \
             mock.patch("hprc.pipeline.searchmod.searxng") as searx:
            run.step_search(str(urls), False, False)
        self.assertFalse(searx.called)
        stats = json.loads((run.dir / "candidates.json").read_text())["stats"]
        self.assertEqual("search_failed:timeout", stats["errors"][0]["error"])

    def test_malformed_candidate_does_not_block_explicit_searxng_fallback(self):
        run = pipeline.Run(self.root, "질문", "light", "search-malformed", quiet=True)
        run.cfg["search"] = {"providers": ["duckduckgo"], "preferred_domains": [], "query_variants": False,
                             "searxng_endpoint": "https://search.example"}
        malformed = {"url": "not a url", "title": "깨진 후보", "via": "duckduckgo"}
        with mock.patch("hprc.pipeline.searchmod.duckduckgo", return_value=[malformed]), \
             mock.patch("hprc.pipeline.searchmod.searxng", return_value=[{"url": "https://result.example/a", "title": "결과", "via": "searxng"}]) as searx:
            run.step_search(None, False, False)
        self.assertTrue(searx.called)

    def test_fetch_sources_preserve_modified_date_metadata(self):
        run = pipeline.Run(self.root, "질문", "light", "fetch-dates", quiet=True)
        (run.dir / "candidates.json").write_text(json.dumps({"candidates": [{"url": "https://example.test/a"}]}), encoding="utf-8")
        page = {"url": "https://example.test/a", "title": "제목", "domain": "example.test", "text": "본문 " * 150,
                "sha256": "a" * 64, "error": "", "published": "2023-01-02", "published_source": "meta:article:published_time",
                "modified": "2024-05-04", "modified_source": "last-modified", "canonical": "", "via": "user", "official": False}
        with mock.patch("hprc.pipeline.fetch_all", return_value=[page]), mock.patch("hprc.pipeline.sync", return_value=0):
            run.step_fetch()
        source = json.loads((run.dir / "sources.json").read_text())["sources"][0]
        self.assertEqual(("2024-05-04", "last-modified"), (source["modified"], source["modified_source"]))
