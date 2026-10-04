import unittest

from hprc.citation_sampling import select_samples
from hprc.verification import mark_report_claims


KO = """# 질문: 냉방 시범사업 효과는?

## 답
연간 전력 사용량은 18% 줄었다 [S1]. 피크 전력은 12% 줄었다 [S1].

## 근거
- 장애 티켓은 대부분 30분 안에 처리됐다.
- 시범 기간이 짧아 일반화는 어렵다. (판단)
- 요약:

## 다음 행동
- 대조군이 있는 자료를 더 찾는다

## 출처
- [S1] 시범사업 보고서 2026년 12% 결과
"""
SOURCES = {"S1": "시범사업 결과 피크 전력은 12% 줄었다."}


class ReportMarkTests(unittest.TestCase):
    def test_number_absent_from_cited_source_is_marked_in_sentence(self):
        text, changes = mark_report_claims(KO, SOURCES, "ko")
        self.assertIn("18% 줄었다 (출처 불일치) [S1].", text)
        self.assertIn("피크 전력은 12% 줄었다 [S1].", text)
        self.assertEqual(1, len(changes["mismatch"]))

    def test_uncited_fact_in_claim_section_gets_no_source_marker(self):
        text, changes = mark_report_claims(KO, SOURCES, "ko")
        self.assertIn("30분 안에 처리됐다 (출처 없음).", text)
        self.assertEqual(["장애 티켓은 대부분 30분 안에 처리됐다."], changes["no_source"])

    def test_judgment_lead_in_next_actions_and_sources_are_untouched(self):
        text, _ = mark_report_claims(KO, SOURCES, "ko")
        self.assertIn("- 시범 기간이 짧아 일반화는 어렵다. (판단)\n", text)
        self.assertIn("- 요약:\n", text)
        self.assertIn("- 대조군이 있는 자료를 더 찾는다\n", text)
        self.assertIn("- [S1] 시범사업 보고서 2026년 12% 결과\n", text)

    def test_marking_is_idempotent(self):
        once, _ = mark_report_claims(KO, SOURCES, "ko")
        twice, changes = mark_report_claims(once, SOURCES, "ko")
        self.assertEqual(once, twice)
        self.assertEqual({"mismatch": [], "no_source": []}, changes)

    def test_marker_stays_with_its_sentence_for_citation_sampling(self):
        text, _ = mark_report_claims(KO, SOURCES, "ko")
        sentences = [s["sentence"] for s in select_samples(text, 100, "(판단)")["samples"]]
        self.assertIn("연간 전력 사용량은 18% 줄었다 (출처 불일치) [S1].", sentences)
        self.assertIn("피크 전력은 12% 줄었다 [S1].", sentences)

    def test_english_markers_and_present_numbers(self):
        report = ("# Question: q?\n\n## Answer\nTurnover was 11 percent versus 14 percent [S1].\n\n"
                  "## Evidence\n- Juniors got 25 percent fewer comments [S2].\n- Most managers prefer three office days.\n")
        text, changes = mark_report_claims(report, {"S1": "turnover 11 percent vs 14 percent", "S2": "fewer comments"}, "en")
        self.assertIn("Turnover was 11 percent versus 14 percent [S1].", text)
        self.assertIn("fewer comments (source mismatch) [S2].", text)
        self.assertIn("three office days (no source).", text)
        self.assertEqual(1, len(changes["no_source"]))

    def test_cite_after_period_keeps_marker_before_period(self):
        text, _ = mark_report_claims("## 답\n전력은 18% 줄었다. [S1]\n", SOURCES, "ko")
        self.assertIn("전력은 18% 줄었다 (출처 불일치). [S1]", text)
        sentences = [s["sentence"] for s in select_samples(text, 100, "(판단)")["samples"]]
        self.assertEqual(["전력은 18% 줄었다 (출처 불일치). [S1]"], sentences)

    def test_missing_source_text_does_not_claim_mismatch(self):
        text, changes = mark_report_claims("## 답\n전력은 18% 줄었다 [S9].\n", {}, "ko")
        self.assertNotIn("(출처 불일치)", text)
        self.assertEqual([], changes["mismatch"])


if __name__ == "__main__":
    unittest.main()
