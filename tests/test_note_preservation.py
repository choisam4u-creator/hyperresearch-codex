import concurrent.futures
import tempfile
import unittest
from pathlib import Path

from hprc import vault


def page(url="https://example.test/a", text="본문", **extra):
    return {"url": url, "title": "같은 제목", "domain": "example.test", "text": text,
            "sha256": "x" * 64, "published": "2023-01-02", "published_source": "meta:article:published_time",
            "modified": "2024-05-04", "modified_source": "last-modified", "canonical": "https://example.test/canonical", **extra}


class NotePreservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.notes = Path(self.tmp.name) / "notes"

    def tearDown(self):
        self.tmp.cleanup()

    def test_same_alias_title_different_urls_keep_separate_snapshots(self):
        first = vault.write_note(self.notes, "S1", page("https://a.test/x"))
        second = vault.write_note(self.notes, "S1", page("https://b.test/x"))
        self.assertNotEqual(first, second)
        self.assertEqual(2, len(list(self.notes.glob("*.md"))))

    def test_same_url_changed_body_creates_snapshot_but_identical_page_reuses_it(self):
        first = vault.write_note(self.notes, "S1", page(text="첫 본문"))
        changed = vault.write_note(self.notes, "S1", page(text="수정 본문"))
        repeated = vault.write_note(self.notes, "S9", page(text="첫 본문"))
        self.assertNotEqual(first, changed)
        self.assertEqual(first, repeated)
        self.assertEqual(2, len(list(self.notes.glob("*.md"))))

    def test_changed_published_or_modified_date_creates_separate_snapshot(self):
        first = vault.write_note(self.notes, "S1", page())
        changed_published = vault.write_note(self.notes, "S1", page(published="2023-01-03"))
        changed_modified = vault.write_note(self.notes, "S1", page(modified="2024-05-05"))
        self.assertEqual(3, len({first, changed_published, changed_modified}))

    def test_legacy_note_is_readable_and_never_replaced(self):
        self.notes.mkdir()
        legacy = self.notes / "S1-legacy.md"
        legacy.write_text('---\nid: "S1"\ntitle: "옛 노트"\n---\n\n옛 본문\n', encoding="utf-8")
        created = vault.write_note(self.notes, "S1", page())
        self.assertTrue(legacy.exists())
        self.assertNotEqual(legacy, created)
        self.assertEqual("S1", vault.read_front(legacy)["id"])
        self.assertEqual("\n옛 본문\n", vault.note_body(legacy))

    def test_date_metadata_and_fetched_at_are_preserved(self):
        saved = vault.write_note(self.notes, "S1", page(fetched_at="2026-09-14T10:11:12"))
        front = vault.read_front(saved)
        self.assertEqual("N-", front["id"][:2])
        self.assertNotIn("source_alias", front)
        self.assertEqual("2023-01-02", front["published"])
        self.assertEqual("meta:article:published_time", front["published_source"])
        self.assertEqual("2024-05-04", front["modified"])
        self.assertEqual("last-modified", front["modified_source"])
        self.assertEqual("https://example.test/canonical", front["canonical"])
        self.assertEqual("2026-09-14T10:11:12", front["fetched_at"])

    def test_identical_snapshot_keeps_its_original_fetched_at(self):
        first = vault.write_note(self.notes, "S1", page(fetched_at="2026-09-14T10:11:12"))
        repeated = vault.write_note(self.notes, "S9", page(fetched_at="2026-09-14T11:12:13"))
        self.assertEqual(first, repeated)
        self.assertEqual("2026-09-14T10:11:12", vault.read_front(repeated)["fetched_at"])

    def test_parallel_identical_writes_publish_one_complete_snapshot(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            paths = list(pool.map(lambda _: vault.write_note(self.notes, "S1", page(text="동시 본문")), range(24)))
        self.assertEqual(1, len(set(paths)))
        self.assertEqual(1, len(list(self.notes.glob("*.md"))))
        self.assertIn("동시 본문", paths[0].read_text(encoding="utf-8"))
