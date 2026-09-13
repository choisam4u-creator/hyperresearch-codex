import datetime as dt
import hashlib
import sqlite3
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from hprc import reuse, vault


class ReuseTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="hpr-reuse-"))
        self.notes = self.root / "research" / "notes"
        self.notes.mkdir(parents=True)
        self.now = dt.datetime(2026, 9, 14, 12, tzinfo=dt.timezone.utc)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def add(self, *, url="https://example.test/a", title="Alpha", fetched="2026-09-10T12:00:00+00:00", text="검색 가능한 합성 본문 " * 40):
        page = {"url": url, "final_url": url, "title": title, "domain": "example.test", "via": "fetch",
                "official": False, "published": "2026-01-01", "published_source": "meta:date",
                "modified": "", "modified_source": "", "canonical": url, "text": text,
                "sha256": hashlib.sha256(text.encode()).hexdigest(), "fetched_at": fetched}
        path = vault.write_note(self.notes, "S1", page)
        vault.sync(self.root)
        return path

    def test_fresh_n_id_note_is_returned_with_vault_metadata(self):
        path = self.add()
        rows = reuse.reusable_sources(self.root, "검색 가능한", now=self.now)
        self.assertEqual(1, len(rows))
        self.assertEqual({"vault", path.name}, {rows[0]["via"], Path(rows[0]["path"]).name})
        self.assertTrue(rows[0]["note_id"].startswith("N-"))

    def test_ttl_stale_future_legacy_and_malformed_are_excluded(self):
        self.add(fetched="2026-07-01T00:00:00+00:00", title="stale")
        future = self.add(fetched="2026-09-15T00:00:00+00:00", title="future")
        legacy = self.notes / "S1-legacy.md"
        legacy.write_text("---\nid: S1\ntitle: Legacy\nurl: https://example.test/l\nfetched_at: 2026-09-10\n---\n\n# Legacy\n검색 가능한 본문\n", encoding="utf-8")
        malformed = self.notes / ("N-" + "0" * 64 + "-bad.md")
        malformed.write_text("not frontmatter", encoding="utf-8")
        vault.sync(self.root)
        rows = reuse.reusable_sources(self.root, "검색 가능한", max_age_days=30, now=self.now)
        self.assertEqual([], rows)
        self.assertTrue(future.exists())

    def test_tampered_body_and_changed_url_are_excluded(self):
        path = self.add()
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("검색 가능한 합성 본문", "변조된 본문", 1), encoding="utf-8")
        vault.sync(self.root)
        self.assertEqual([], reuse.reusable_sources(self.root, "검색 가능한", now=self.now))
        path = self.add(url="https://example.test/original", title="URL")
        changed = path.read_text(encoding="utf-8").replace('url: "https://example.test/original"', 'url: "https://evil.test/changed"', 1)
        path.write_text(changed, encoding="utf-8")
        vault.sync(self.root)
        self.assertFalse(any(row["title"] == "URL" for row in reuse.reusable_sources(self.root, "검색 가능한", now=self.now)))

    def test_latest_fresh_duplicate_url_wins_and_limit(self):
        self.add(url="https://example.test/dup", title="Old", fetched="2026-09-01T00:00:00+00:00")
        self.add(url="https://example.test/dup", title="New", fetched="2026-09-13T00:00:00+00:00")
        self.add(url="https://example.test/other", title="Other")
        self.assertEqual(["New", "Other"], [r["title"] for r in reuse.reusable_sources(self.root, "검색 가능한", now=self.now, limit=2)])

    def test_query_is_fts_safe_and_db_errors_return_empty(self):
        self.add()
        self.assertEqual([], reuse.reusable_sources(self.root, '" OR (broken', now=self.now))
        with mock.patch("hprc.reuse.vault.search", side_effect=sqlite3.DatabaseError("db")):
            self.assertEqual([], reuse.reusable_sources(self.root, "검색 가능한", now=self.now))

    def test_missing_index_does_not_create_or_regenerate_one(self):
        self.assertFalse((self.root / "research" / "index.sqlite").exists())
        self.assertEqual([], reuse.reusable_sources(self.root, "검색 가능한", now=self.now))
        self.assertFalse((self.root / "research" / "index.sqlite").exists())

    def test_cached_page_revalidates_and_returns_fetch_shape(self):
        path = self.add()
        candidate = reuse.reusable_sources(self.root, "검색 가능한", now=self.now)[0]
        page = reuse.cached_page(self.root, candidate, now=self.now)
        self.assertEqual("vault", page["via"])
        self.assertEqual(str(path.resolve()), page["snapshot_path"])
        self.assertEqual(candidate["note_id"], reuse.vault.read_front(path)["id"])
        candidate["note_id"] = "N-" + "0" * 64
        self.assertIsNone(reuse.cached_page(self.root, candidate, now=self.now))

    def test_cached_page_rejects_path_outside_notes(self):
        self.add()
        candidate = reuse.reusable_sources(self.root, "검색 가능한", now=self.now)[0]
        candidate["path"] = str(self.root / "outside.md")
        self.assertIsNone(reuse.cached_page(self.root, candidate, now=self.now))


if __name__ == "__main__":
    unittest.main()
