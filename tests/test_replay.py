import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from hprc.replay import load_case, pages_for_case


FIXTURE = Path(__file__).parent / "fixtures" / "benchmark_inputs.json"


class ReplayTests(unittest.TestCase):
    def test_load_case_accepts_frozen_fixture_and_pages_preserve_exact_body(self):
        case = load_case(FIXTURE, "fact-ko-01")
        pages = pages_for_case(case)
        self.assertEqual(["S1", "S2"], [page["url"].rsplit("/", 1)[1] for page in pages])
        self.assertEqual(case["sources"]["S1"], pages[0]["text"])
        self.assertEqual(hashlib.sha256(case["sources"]["S1"].encode("utf-8")).hexdigest(), pages[0]["sha256"])
        self.assertEqual("fixture.invalid", pages[0]["domain"])
        self.assertEqual(case["baseline_time"], pages[0]["fetched_at"])

    def test_load_case_rejects_answer_fixture_and_nested_answer_key(self):
        answers = Path(__file__).parent / "fixtures" / "benchmark_answers.json"
        with self.assertRaises(ValueError):
            load_case(answers, "fact-ko-01")
        with tempfile.TemporaryDirectory() as temp:
            bad = {"cases": [{"id": "x", "prompt": "p", "lang": "en", "baseline_time": "2026-09-14",
                              "sources": {"S1": {"text": "body", "expected": "leak"}}}]}
            path = Path(temp) / "bad.json"; path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_case(path, "x")

    def test_load_case_rejects_non_string_text_and_non_contiguous_source_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.json"
            for sources in ({"S1": 7}, {"S1": "a", "S3": "b"}):
                data = {"cases": [{"id": "x", "prompt": "p", "lang": "en", "baseline_time": "2026-09-14", "sources": sources}]}
                path.write_text(json.dumps(data), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_case(path, "x")

    def test_load_case_rejects_calendar_invalid_baseline_date(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad-date.json"
            data = {"cases": [{"id": "x", "prompt": "p", "lang": "en", "baseline_time": "2026-02-30", "sources": {"S1": "body"}}]}
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_case(path, "x")

    def test_equal_body_hashes_do_not_collapse_distinct_source_positions(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "same.json"
            data = {"cases": [{"id": "same-body", "prompt": "p", "lang": "en", "baseline_time": "2026-09-14",
                               "sources": {"S1": "same raw body", "S2": "same raw body"}}]}
            path.write_text(json.dumps(data), encoding="utf-8")
            pages = pages_for_case(load_case(path, "same-body"))
            self.assertEqual(pages[0]["sha256"], pages[1]["sha256"])
            self.assertNotEqual(pages[0]["url"], pages[1]["url"])


if __name__ == "__main__":
    unittest.main()
