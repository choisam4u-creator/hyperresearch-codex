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
        self.assertFalse(any(changes.values()))

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

    def test_ambiguous_units_and_partial_dates_are_not_marked_as_mismatch(self):
        text, changes = mark_report_claims("## Answer\nMeasured power was 12 MW [S1].\n", {"S1": "Measured power was 12 MW."}, "en")
        self.assertNotIn("(source mismatch)", text)
        text, changes = mark_report_claims("## 답\n점검은 7월 22일에 진행됐다 [S1].\n", {"S1": "점검은 7월 22일에 진행됐다."}, "ko")
        self.assertNotIn("(출처 불일치)", text)
        self.assertEqual([], changes["mismatch"])

    def test_full_date_absent_from_source_is_marked(self):
        text, _ = mark_report_claims("## 답\n점검은 2026년 7월 23일에 진행됐다 [S1].\n", {"S1": "점검은 2026년 7월 22일에 진행됐다."}, "ko")
        self.assertIn("(출처 불일치) [S1]", text)

    def test_missing_source_text_does_not_claim_mismatch(self):
        text, changes = mark_report_claims("## 답\n전력은 18% 줄었다 [S9].\n", {}, "ko")
        self.assertNotIn("(출처 불일치)", text)
        self.assertEqual([], changes["mismatch"])


class ValueConflictMarkTests(unittest.TestCase):
    """원문에 같은 값이 있어도 반대 방향·다른 문맥이면 표시한다(2026-10-04 2회차). 오탐 방지 조건도 함께 고정한다."""

    EN_SRC = {"S1": "Weekday ridership rose 21 percent compared with a year earlier. "
                    "The report notes that 9 percent of surveyed riders switched from driving.",
              "S2": "Complaints about crowding increased during the morning peak."}

    def test_opposite_direction_with_same_number_is_marked(self):
        text, changes = mark_report_claims("## Answer\nWeekday ridership fell 21 percent from a year earlier [S1].\n", self.EN_SRC, "en")
        self.assertIn("(source mismatch) [S1]", text)
        self.assertEqual(1, len(changes["direction_conflict"]))

    def test_opposite_direction_without_number_needs_close_sentence(self):
        text, _ = mark_report_claims("## Evidence\n- Complaints about crowding decreased during the morning peak [S2].\n", self.EN_SRC, "en")
        self.assertIn("(source mismatch) [S2]", text)
        loose, changes = mark_report_claims("## Evidence\n- Overall satisfaction decreased in winter [S2].\n", self.EN_SRC, "en")
        self.assertNotIn("(source mismatch)", loose)
        self.assertEqual([], changes["direction_conflict"])

    def test_same_direction_is_not_marked(self):
        text, _ = mark_report_claims("## Answer\nWeekday ridership increased 21 percent [S1].\n", self.EN_SRC, "en")
        self.assertNotIn("(source mismatch)", text)

    def test_number_from_unrelated_source_sentence_is_marked(self):
        text, changes = mark_report_claims("## Evidence\n- Traffic congestion on pilot corridors decreased 9 percent [S1].\n", self.EN_SRC, "en")
        self.assertIn("(source mismatch) [S1]", text)
        self.assertEqual(1, len(changes["context_conflict"]))

    def test_cross_language_citation_is_not_called_out_of_context(self):
        text, changes = mark_report_claims("## 근거\n- 승객 중 9%가 운전에서 전환했다 [S1].\n", self.EN_SRC, "ko")
        self.assertNotIn("(출처 불일치)", text)
        self.assertEqual([], changes["context_conflict"])

    def test_korean_direction_and_context(self):
        src = {"S1": "7월 쉼터 이용자는 하루 평균 1,240명이었고, 이 중 65세 이상이 71%였다.",
               "S2": "7월 온열질환 신고는 23건으로 전년보다 감소했다. 오늘 집계를 공개했다."}
        report = ("## 답\n온열질환 신고는 23건으로 전년보다 증가했다 [S2]. 온열질환 신고는 23건으로 줄었다 [S2].\n"
                  "## 근거\n- 야간 운영으로 온열질환 신고가 71% 감소했다 [S1].\n- 이용자 중 65세 이상은 71%였다 [S1].\n")
        text, changes = mark_report_claims(report, src, "ko")
        self.assertIn("증가했다 (출처 불일치) [S2]", text)
        self.assertIn("23건으로 줄었다 [S2].", text)
        self.assertIn("71% 감소했다 (출처 불일치) [S1]", text)
        self.assertIn("65세 이상은 71%였다 [S1].", text)
        self.assertEqual(1, len(changes["direction_conflict"]))
        self.assertEqual(1, len(changes["context_conflict"]))

    def test_judgment_with_number_absent_from_all_sources_gets_no_source(self):
        src = {"S1": "신고는 23건으로 전년 31건보다 감소했다."}
        report = "## 답\n쉼터 덕분에 입원이 40% 줄었다 (판단).\n신고 23건은 작년 31건보다 적다 (판단).\n## 다음 행동\n- 40곳을 더 본다 (판단)\n"
        text, changes = mark_report_claims(report, src, "ko")
        self.assertIn("40% 줄었다 (판단) (출처 없음).", text)
        self.assertIn("31건보다 적다 (판단).\n", text)
        self.assertIn("- 40곳을 더 본다 (판단)\n", text)
        self.assertEqual(1, len(changes["no_source"]))
        again, _ = mark_report_claims(text, src, "ko")
        self.assertEqual(text, again)

    def test_independence_claim_over_similar_sources_is_marked(self):
        src = {"S1": "피크 전력이 감소했다.", "S3": "[전재] 피크 전력이 감소했다."}
        note = " (S1·S3: 본문 유사, 독립 출처가 아닐 수 있음)"
        text, changes = mark_report_claims(f"## 근거\n- 두 독립 출처가 피크 전력 감소를 확인한다 [S1][S3]{note}.\n", src, "ko")
        self.assertIn("확인한다 (출처 불일치) [S1][S3]", text)
        self.assertEqual(1, len(changes["independence_conflict"]))
        plain, changes = mark_report_claims(f"## 근거\n- 피크 전력이 감소했다 [S1][S3]{note}.\n", src, "ko")
        self.assertNotIn("(출처 불일치)", plain)       # 경고 주석 안의 '독립'은 주장으로 세지 않는다
        unwarned, _ = mark_report_claims("## 근거\n- 두 독립 출처가 피크 전력 감소를 확인한다 [S1][S3].\n", src, "ko")
        self.assertNotIn("(출처 불일치)", unwarned)     # 묶음 경고가 없으면 독립성을 판단하지 않는다
        en, _ = mark_report_claims("## Evidence\n- Two independent sources confirm the drop [S1][S3] "
                                   "(S1·S3: similar text, may not be independent).\n", src, "en")
        self.assertIn("(source mismatch) [S1][S3]", en)


if __name__ == "__main__":
    unittest.main()
