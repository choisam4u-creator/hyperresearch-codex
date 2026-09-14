import unittest

from hprc.citation_sampling import enrich_checks, render_summary, select_samples


class CitationSamplingTests(unittest.TestCase):
    def test_mixed_korean_english_table_list_and_position_diversity(self):
        report = """# 제목 [S99]
첫 근거입니다. [S1]
- 목록 근거 [S2]
| 항목 | 근거 |
| --- | --- |
| 중간 | table fact [S3] |
중간 영어 근거입니다. [S4]
끝 근거입니다. [S5]
## 출처
- [S99] 출처 제목
"""
        got = select_samples(report, 3, "(판단)")
        self.assertEqual("sample_only", got["scope"])
        self.assertEqual(5, got["eligible_count"])
        self.assertEqual(3, got["selected_count"])
        self.assertEqual([2, 6, 8], [sample["line"] for sample in got["samples"]])
        self.assertIn("| 중간 | table fact [S3] |", [sample["sentence"] for sample in got["samples"]])

    def test_excludes_judgment_headers_sources_and_fenced_code(self):
        report = """## 헤더 [S9]
사실 문장 [S1]
추천 문장 (판단) [S2]
```python
print('[S3]')
```
## Sources
- source title [S4]
"""
        got = select_samples(report, 10, "(판단)")
        self.assertEqual(1, got["eligible_count"])
        self.assertEqual(1, got["excluded_judgment_count"])
        self.assertEqual("사실 문장 [S1]", got["samples"][0]["sentence"])

    def test_source_words_in_body_headings_and_empty_table_cites_are_not_excluded_or_sampled(self):
        report = """## Sources of error
이 절의 근거 [S1]
## 출처 편중의 영향
다른 근거 [S2]
| 링크 |
| --- |
| [S3] |
## Sources
- 출처 제목 [S4]
"""
        got = select_samples(report, 10, "(judgment)")
        self.assertEqual(2, got["eligible_count"])
        self.assertEqual(["S1", "S2"], [sample["cites"][0] for sample in got["samples"]])

    def test_trailing_judgment_stays_attached_without_hiding_adjacent_facts(self):
        for marker in ("(판단)", "(judgment)", "[recommendation]"):
            with self.subTest(marker=marker):
                report = f"Fact one.[S1] Recommend action.[S2] {marker}\nFact two. [S3]"
                result = select_samples(report, 10, marker)
                self.assertEqual(1, result["excluded_judgment_count"])
                self.assertEqual(["Fact one.[S1]", "Fact two. [S3]"], [s["sentence"] for s in result["samples"]])

    def test_judgment_suffix_multiple_spaces_and_following_fact(self):
        for marker in ("(판단)", "(judgment)", "[recommendation]"):
            for space in (" ", "  ", "\t "):
                for recommendation in (f"Recommend.[S1]{space}{marker}", f"Recommend.{space}{marker} [S1]"):
                    with self.subTest(marker=marker, space=space, recommendation=recommendation):
                        result = select_samples(recommendation + " Actual fact.[S2]", 10, marker)
                        self.assertEqual(1, result["excluded_judgment_count"])
                        self.assertEqual(["Actual fact.[S2]"], [s["sentence"] for s in result["samples"]])

    def test_marker_before_citation_and_empty_marker_still_work(self):
        result = select_samples("Recommend. (판단) [S1]\nFact.[S2]", 10, "(판단)")
        self.assertEqual((1, 1), (result["eligible_count"], result["excluded_judgment_count"]))
        self.assertEqual(2, select_samples("One.[S1] Two.[S2]", 10, "")["eligible_count"])

    def test_limit_duplicates_and_late_source_are_deterministic(self):
        report = """앞 동일 [S1]
앞 동일 [S1]
중간 근거 [S2]
뒤쪽 고유 근거 [S8]
"""
        first = select_samples(report, 3, "(judgment)")
        second = select_samples(report, 3, "(judgment)")
        self.assertEqual(first, second)
        self.assertLessEqual(first["selected_count"], 3)
        self.assertIn("S8", {cite for sample in first["samples"] for cite in sample["cites"]})
        self.assertEqual("앞 동일 [S1]", first["samples"][0]["sentence"])

    def test_empty_and_zero_limit(self):
        self.assertEqual([], select_samples("인용 없음", 3, "(판단)")["samples"])
        got = select_samples("근거 [S1]", 0, "(판단)")
        self.assertEqual((1, 0), (got["eligible_count"], got["selected_count"]))

    def test_summary_marks_sample_scope_and_unsupported_location(self):
        meta = {"eligible_count": 6, "selected_count": 2, "scope": "sample_only"}
        text = render_summary([{"sentence": "근거 [S7]", "cites": ["S7"], "line": 12, "supported": False}], meta, "ko")
        self.assertIn("표본 밖 문장은 검증하지 않았습니다", text)
        self.assertIn("L12 [S7] — 근거 [S7]", text)
        self.assertIn("행 번호는 report.md 기준", text)
        self.assertIn("미반환 표본 1개는 미검증", text)
        english = render_summary([], meta, "en")
        self.assertIn("Sentences outside this sample were not checked", english)

    def test_enrich_checks_adds_sample_location_and_reason_is_rendered(self):
        meta = {"samples": [{"sentence": "근거 [S7]", "cites": ["S7"], "line": 12}], "selected_count": 1, "eligible_count": 1}
        checks = enrich_checks([{"sentence": "근거 [S7]", "cites": ["S7"], "supported": False, "reason": "부분 지지"}], meta)
        self.assertEqual(12, checks[0]["line"])
        self.assertIn("부분 지지", render_summary(checks, meta, "ko"))

    def test_enrich_rejects_duplicate_and_unmatched_results_without_hiding_missing_sample(self):
        meta = {"samples": [{"sentence": "첫 근거 [S1]", "cites": ["S1"], "line": 3},
                            {"sentence": "둘째 근거 [S2]", "cites": ["S2"], "line": 9}],
                "selected_count": 2, "eligible_count": 2}
        returned = [{"sentence": "첫 근거 [S1]", "cites": ["S1"], "supported": True, "reason": "ok"},
                    {"sentence": "첫 근거 [S1]", "cites": ["S1"], "supported": True, "reason": "duplicate"},
                    {"sentence": "없는 문장 [S9]", "cites": ["S9"], "supported": True, "reason": "unmatched"}]
        checks = enrich_checks(returned, meta)
        self.assertEqual(1, len(checks))
        self.assertEqual((1, 2), (meta["checked_count"], meta["unmatched_count"]))
        summary = render_summary(checks, meta, "ko")
        self.assertIn("미반환 표본 1개는 미검증", summary)
        self.assertIn("중복된 반환 결과 2개는 판정 수에서 제외", summary)

    def test_duplicate_candidates_are_selected_once_and_legacy_summary_is_explicit(self):
        samples = select_samples("같은 문장 [S1]\n같은 문장 [S1]\n다른 문장 [S2]", 5, "(판단)")
        self.assertEqual(2, samples["selected_count"])
        legacy = render_summary([], None, "ko")
        self.assertIn("전체 인용 문장 수와 표본 범위가 기록되지 않았습니다", legacy)
        self.assertNotIn("0/0", legacy)
