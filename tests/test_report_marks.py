import unittest

from hprc.citation_sampling import select_samples
from hprc.verification import _quantity_values, mark_report_claims


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

    def test_judgment_with_date_absent_from_all_sources_gets_no_source(self):
        src = {"S1": "The pilot ran from March 1, 2025 to February 28, 2026."}
        text, _ = mark_report_claims("## Answer\nThe program began on March 3, 2025 (judgment).\n"
                                     "The pilot likely ran past March 1, 2025 (judgment).\n", src, "en")
        self.assertIn("March 3, 2025 (judgment) (no source).", text)
        self.assertIn("past March 1, 2025 (judgment).\n", text)

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


class CausalPeriodInternalTests(unittest.TestCase):
    SRC = {"S1": "Ridership rose 12 percent in March. The report cannot establish that the pass caused the rise.",
           "S2": "The program planted 2,300 trees per year. Maintenance requests for street trees rose 30 percent."}

    def mark(self, body: str, sources=None) -> tuple[str, dict]:
        return mark_report_claims(f"## Answer\n{body}\n\n## Sources\n- [S1] a\n", sources or self.SRC, "en")

    def test_causal_claim_against_disclaimer_is_marked(self):
        text, changes = self.mark("The pass caused ridership to rise 12 percent in March [S1].")
        self.assertIn("(source mismatch) [S1]", text)
        self.assertEqual(1, len(changes["causal_conflict"]))

    def test_causal_claim_supported_or_without_disclaimer_is_left_alone(self):
        supported = {"S1": "Boarding time fell 14 percent because riders no longer paid at the door."}
        text, _ = self.mark("Boarding time fell 14 percent because riders no longer paid [S1].", supported)
        self.assertNotIn("(source mismatch)", text)
        silent = {"S1": "Ridership rose 12 percent in March."}     # 인과 낱말이 없을 뿐인 원문은 표시하지 않는다(보수적)
        text, _ = self.mark("The pass caused ridership to rise 12 percent in March [S1].", silent)
        self.assertNotIn("(source mismatch)", text)

    def test_unrelated_positive_causal_sentence_does_not_cancel_disclaimer(self):
        src = {"S1": "The study cannot establish that the campaign caused traffic growth. Rain caused one closure."}
        text, changes = self.mark("The campaign caused traffic growth [S1].", src)
        self.assertIn("(source mismatch) [S1]", text)
        self.assertEqual(1, len(changes["causal_conflict"]))

    def test_period_is_tied_to_each_number_in_a_sentence(self):
        src = {"S1": "The daily average was 100 visitors, for 3,000 visitors in total."}
        text, _ = self.mark("The site drew 3,000 visitors per day [S1].", src)
        self.assertIn("(source mismatch) [S1]", text)
        text, _ = self.mark("The site drew 3,000 visitors in total [S1]. The daily average was 100 visitors [S1].", src)
        self.assertNotIn("(source mismatch)", text)

    def test_period_swap_is_marked_for_cited_and_judgment(self):
        text, changes = self.mark("The program planted 2,300 trees in total [S2]. It planted 2,300 trees a day (judgment).")
        self.assertEqual(2, text.count("(source mismatch)"))
        self.assertEqual(2, len(changes["period_conflict"]))
        text, _ = self.mark("The program planted 2,300 trees per year [S2].")
        self.assertNotIn("(source mismatch)", text)

    def test_judgment_contradicting_cited_sentence_is_marked(self):
        body = "Maintenance requests for street trees rose 30 percent [S2]. The program reduced maintenance requests (judgment)."
        text, changes = self.mark(body)
        self.assertIn("reduced maintenance requests (judgment) (source mismatch).", text)
        self.assertEqual(1, len(changes["internal_conflict"]))
        self.assertEqual(text, self.mark(text.split("\n", 1)[1].split("\n\n## Sources")[0])[0])   # 다시 돌려도 같다

    def test_unrelated_opposite_direction_is_not_a_contradiction(self):
        text, _ = self.mark("Maintenance requests for street trees rose 30 percent [S2]. Ticket prices fell (judgment).")
        self.assertNotIn("(source mismatch)", text)

    def test_korean_causal_period_internal(self):
        src = {"S1": "발급자는 3월 한 달 동안 18,400명이었다. 이용 건수는 12% 늘었다. 보고서는 이용 증가가 패스 때문인지 구분하지 못했다.",
               "S2": "도심 주차장 이용 대수는 5% 증가했다."}
        report = ("## 답\n패스 덕분에 이용 건수가 12% 늘었다 [S1]. 도심 주차장 이용이 감소했다 (판단).\n\n"
                  "## 근거\n- 도심 주차장 이용 대수는 5% 증가했다 [S2].\n- 발급은 하루 18,400명 규모다 (판단).\n\n## 출처\n- [S1] a\n")
        text, changes = mark_report_claims(report, src, "ko")
        self.assertEqual(3, text.count("(출처 불일치)"))
        self.assertTrue(changes["causal_conflict"] and changes["internal_conflict"] and changes["period_conflict"])


class PlanScopeTests(unittest.TestCase):
    EN = {"S1": "The office reported that 8,200 heat pumps were installed in 2025. The office plans to reach 20,000 installations by 2028.",
          "S2": "A pilot survey of 400 households in two counties found that heating bills fell 23 percent."}
    KO = {"S1": "충전기는 5월 말 기준 1,240기다. 시는 2027년까지 충전기를 3,000기로 늘릴 계획이라고 밝혔다.",
          "S2": "시범 사업이 진행된 3개 구에서 평균 대기 시간은 18분에서 11분으로 줄었다."}

    def mark(self, body, src, lang="en"):
        head = "## Answer\n" if lang == "en" else "## 답\n"
        return mark_report_claims(head + body + "\n", src, lang)

    def test_plan_stated_as_done_is_marked(self):
        text, changes = self.mark("The program reached 20,000 installations [S1].", self.EN)
        self.assertIn("installations (source mismatch) [S1].", text)
        self.assertEqual(1, len(changes["plan_conflict"]))

    def test_plan_kept_as_plan_or_actual_value_is_left_alone(self):
        for body in ("The office plans to reach 20,000 installations by 2028 [S1].",
                     "The target is 20,000 installations [S1].",
                     "The program installed 8,200 heat pumps in 2025 [S1]."):
            text, _ = self.mark(body, self.EN)
            self.assertNotIn("(source mismatch)", text, body)

    def test_value_reported_both_as_actual_and_plan_is_left_alone(self):
        src = {"S1": "Installations reached 500 in 2025. The office plans another 500 next year."}
        text, _ = self.mark("Installations reached 500 [S1].", src)
        self.assertNotIn("(source mismatch)", text)

    def test_pilot_result_generalized_is_marked(self):
        text, changes = self.mark("Households statewide saw heating bills fall 23 percent [S2].", self.EN)
        self.assertIn("(source mismatch)", text)
        self.assertEqual(1, len(changes["scope_conflict"]))
        text, _ = self.mark("In a pilot of two counties, heating bills fell 23 percent [S2].", self.EN)
        self.assertNotIn("(source mismatch)", text)

    def test_wide_scope_backed_by_source_is_left_alone(self):
        src = {"S1": "A statewide survey of 2,000 households found that bills fell 9 percent."}
        text, _ = self.mark("Households statewide saw bills fall 9 percent [S1].", src)
        self.assertNotIn("(source mismatch)", text)

    def test_achieved_and_planned_value_in_one_clause_is_left_alone(self):
        # PR #15 리뷰: 실적과 계획이 한 절에 이어지면 계획 낱말은 뒤 명제에만 붙는다.
        src = {"S1": "The city has installed 500 chargers and plans to add 500 more."}
        text, _ = self.mark("The city has installed 500 chargers [S1].", src)
        self.assertNotIn("(source mismatch)", text)
        src = {"S1": "시는 충전기 500기를 설치했고 500기를 더 늘릴 계획이다."}
        text, _ = self.mark("시는 충전기 500기를 설치했다 [S1].", src, "ko")
        self.assertNotIn("(출처 불일치)", text)
        text, _ = self.mark("The city reached 20,000 installations [S1].",
                            {"S1": "The city installed 8,200 units and plans to reach 20,000 installations."})
        self.assertIn("(source mismatch)", text)

    def test_qualitative_scope_generalization_is_marked(self):
        # PR #15 리뷰: 수치 없는 일반화도 같은 대상의 원문 문장이 모두 시범 범위면 표시한다.
        src = {"S1": "Participating households in a two-county pilot reported lower heating bills."}
        text, changes = self.mark("Households statewide reported lower heating bills [S1].", src)
        self.assertIn("(source mismatch)", text)
        self.assertEqual(1, len(changes["scope_conflict"]))
        src = {"S1": "Households statewide reported lower heating bills in the annual survey of utilities."}
        text, _ = self.mark("Households statewide reported lower heating bills [S1].", src)
        self.assertNotIn("(source mismatch)", text)

    def test_korean_plan_and_scope(self):
        text, changes = self.mark("시는 충전기를 3,000기로 늘렸다 [S1]. 시 전역의 평균 대기 시간은 18분에서 11분으로 줄었다 [S2].",
                                  self.KO, "ko")
        self.assertEqual(2, text.count("(출처 불일치)"))
        self.assertTrue(changes["plan_conflict"] and changes["scope_conflict"])
        text, _ = self.mark("시는 2027년까지 충전기를 3,000기로 늘릴 계획이다 [S1]. 시범 사업 3개 구의 대기 시간은 11분으로 줄었다 [S2].",
                            self.KO, "ko")
        self.assertNotIn("(출처 불일치)", text)
        self.assertEqual(text, self.mark(text.split("\n", 1)[1].strip(), self.KO, "ko")[0])   # 다시 돌려도 같다

    EST = {"S1": "The county's preliminary count found 2,140 people in January 2026. The count recorded 610 people in shelters.",
           "S2": "A memo estimates that the pilot cost 3.8 million dollars, and the city spent 1.2 million dollars on buses."}

    def test_estimate_stated_as_fact_gets_weak_mark(self):
        text, changes = self.mark("The county counted 2,140 people in January 2026 [S1].", self.EST)
        self.assertIn("in January 2026 (source estimate) [S1].", text)
        self.assertNotIn("(source mismatch)", text)
        self.assertEqual(1, len(changes["estimate_dropped"]))
        self.assertEqual([], changes["mismatch"])
        self.assertEqual(text, self.mark(text.split("\n", 1)[1].strip(), self.EST)[0])   # 다시 돌려도 같다

    def test_hedged_estimate_actual_value_and_date_are_left_alone(self):
        for body in ("A preliminary count found 2,140 people [S1].",
                     "The pilot cost an estimated 3.8 million dollars [S2].",
                     "The pilot cost about 3.8 million dollars [S2].",
                     "The count recorded 610 people in shelters [S1].",
                     "The city spent 1.2 million dollars on buses [S2]."):
            text, changes = self.mark(body, self.EST)
            self.assertNotIn("(source estimate)", text, body)
            self.assertEqual([], changes["estimate_dropped"], body)

    def test_mismatch_takes_priority_over_estimate(self):
        text, changes = self.mark("The pilot cost 3.8 million dollars and rose 9 percent [S2].", self.EST)
        self.assertIn("(source mismatch)", text)
        self.assertNotIn("(source estimate)", text)
        self.assertEqual([], changes["estimate_dropped"])

    def test_estimate_hedge_is_scoped_to_its_own_value(self):
        # PR #16 리뷰: 한 문장의 다른 수치에 붙은 유보가 추정치 수치를 가리지 않는다.
        text, changes = self.mark("The pilot cost 3.8 million dollars, while the city spent approximately 1.2 million dollars [S2].",
                                  self.EST)
        self.assertIn("(source estimate)", text)
        self.assertEqual(1, len(changes["estimate_dropped"]))

    def test_approx_abbreviation_stays_with_its_value(self):
        # PR #16 리뷰: "approx." 뒤에서 원문·주장 문장을 끊지 않는다.
        src = {"S1": "The pilot cost was approx. 3.8 million dollars. Buses ran on 4 routes."}
        text, _ = self.mark("The pilot cost 3.8 million dollars [S1].", src)
        self.assertIn("(source estimate)", text)
        text, _ = self.mark("The pilot cost approx. 3.8 million dollars [S1].", src)
        self.assertNotIn("(source estimate)", text)

    def test_four_digit_count_is_not_a_year(self):
        # PR #16 리뷰: 연도 자리가 아닌 네 자리 수량은 추정치 판정에서 빼지 않는다.
        src = {"S1": "A preliminary count found 2000 people in shelters."}
        text, _ = self.mark("The county counted 2000 people in shelters [S1].", src)
        self.assertIn("(source estimate)", text)
        src = {"S1": "A preliminary count in 2026 found 610 people. Shelters opened in 2026."}
        text, _ = self.mark("Shelters opened in 2026 [S1].", src)
        self.assertNotIn("(source estimate)", text)

    def test_korean_estimate(self):
        src = {"S1": "시는 2026년 7월 집중호우 재산 피해를 약 420억 원으로 추산했다. 침수 주택은 1,280가구로 집계됐다."}
        text, changes = self.mark("7월 집중호우 재산 피해는 420억 원이었다 [S1]. 침수 주택은 1,280가구로 집계됐다 [S1].", src, "ko")
        self.assertEqual(1, text.count("(원문 추정치)"))
        self.assertIn("420억 원이었다 (원문 추정치) [S1].", text)
        text, _ = self.mark("재산 피해는 약 420억 원으로 추산됐다 [S1].", src, "ko")
        self.assertNotIn("(원문 추정치)", text)


    YEAR = {"S1": "2023년 분리배출 교육 참여 가구는 12,000가구였고, 2025년에는 18,500가구로 늘었다.",
            "S2": "In 2023, the subsidy program enrolled 41,000 households. Enrollment reached 56,000 households in 2025."}

    def test_value_moved_to_other_year_is_marked(self):
        text, changes = self.mark("The subsidy program enrolled 41,000 households in 2025 [S2].", self.YEAR)
        self.assertIn("in 2025 (source mismatch) [S2].", text)
        self.assertEqual(1, len(changes["year_conflict"]))
        text, changes = self.mark("2025년 분리배출 교육 참여 가구는 12,000가구였다 [S1].", self.YEAR, "ko")
        self.assertIn("(출처 불일치)", text)
        self.assertEqual(1, len(changes["year_conflict"]))

    def test_matching_or_unknown_year_is_left_alone(self):
        for body in ("In 2023, the subsidy program enrolled 41,000 households [S2].",
                     "Enrollment reached 56,000 households in 2025 [S2].",
                     "The subsidy program enrolled 41,000 households [S2]."):
            text, _ = self.mark(body, self.YEAR)
            self.assertNotIn("(source mismatch)", text, body)
        src = {"S1": "Access rose from 71 percent in 2022 to 78 percent in 2025, an increase of 7 percentage points."}
        text, _ = self.mark("In 2025, access rose by 7 percentage points [S1].", src)
        self.assertNotIn("(source mismatch)", text)   # 원문 자리의 연도가 둘 이상이면 모른다고 본다
        text, _ = self.mark("2023~2025년 교육 참여 가구는 18,500가구로 늘었다 [S1].", self.YEAR, "ko")
        self.assertNotIn("(출처 불일치)", text)

    def test_sentence_initial_english_year_is_a_year(self):
        # PR #17 리뷰: 문장 첫머리 연도도 연도로 본다.
        src = {"S1": "2023 enrollment reached 41,000. 2025 enrollment reached 56,000."}
        text, changes = self.mark("In 2025 enrollment reached 41,000 [S1].", src)
        self.assertIn("(source mismatch)", text)
        self.assertEqual(1, len(changes["year_conflict"]))
        text, _ = self.mark("In 2023 enrollment reached 41,000 [S1].", src)
        self.assertNotIn("(source mismatch)", text)

    def test_percent_point_swapped_with_percent_is_marked(self):
        src = {"S1": "재활용률은 2022년 41%에서 2025년 47%로 6%포인트 올랐다.", "S2": "Monthly bills fell by 12 percent on average."}
        text, changes = self.mark("재활용률은 6% 올랐다 [S1].", src, "ko")
        self.assertIn("6% 올랐다 (출처 불일치) [S1].", text)
        self.assertEqual(1, len(changes["unit_conflict"]))
        text, changes = self.mark("Monthly bills fell by 12 percentage points [S2].", src)
        self.assertIn("(source mismatch)", text)
        self.assertEqual(1, len(changes["unit_conflict"]))
        for body, lang in (("재활용률은 6%포인트 올랐다 [S1].", "ko"), ("재활용률은 6%p 올랐다 [S1].", "ko"),
                           ("Monthly bills fell by 12 percent [S2].", "en")):
            text, _ = self.mark(body, src, lang)
            self.assertNotIn("불일치" if lang == "ko" else "mismatch", text, body)
        self.assertEqual(text, self.mark(text.split("\n", 1)[1].strip(), src)[0])   # 다시 돌려도 같다
    def test_upper_bound_or_range_endpoint_stated_as_value_is_marked(self):
        # 2026-10-08 품질 회차: 원문의 상한·범위 끝값을 대표값처럼 쓰면 '(출처 불일치)'.
        src = {"S1": "공사 뒤 난방비는 건물별로 최대 30% 줄었다. 단열 개선은 에너지 사용량을 10~20% 줄인다. "
                     "태양광 설치율은 10%에서 18%로 늘었다.",
               "S2": "Traffic fell by up to 25 percent at peak hours. Pollution fell by between 8 and 12 percent. "
                     "Daily cyclists rose from 9,000 to 14,000."}
        for body, lang in (("난방비는 30% 줄었다 [S1].", "ko"), ("에너지 사용량을 20% 줄인다 [S1].", "ko"),
                           ("Traffic fell by 25 percent [S2].", "en"), ("Pollution fell by 12 percent [S2].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertIn("불일치" if lang == "ko" else "mismatch", text, body)
            self.assertEqual(1, len(changes["bound_conflict"]), body)
        for body, lang in (("난방비는 최대 30% 줄었다 [S1].", "ko"), ("에너지 사용량을 10~20% 줄인다 [S1].", "ko"),
                           ("태양광 설치율은 18%로 늘었다 [S1].", "ko"), ("Traffic fell by up to 25 percent [S2].", "en"),
                           ("Pollution fell by 8 to 12 percent [S2].", "en"), ("Daily cyclists rose to 14,000 [S2].", "en"),
                           ("Daily cyclists rose from 9,000 [S2].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertNotIn("불일치" if lang == "ko" else "mismatch", text, body)
            self.assertEqual([], changes["bound_conflict"], body)

    def test_lower_bound_dropped_is_marked_like_upper_bound(self):
        # 2026-10-08 2회차 검토: 하한("최소"·"이상"·"at least"·"more than")을 뗀 수치도 정확한 값처럼 읽히므로 상한과 같은
        # '(출처 불일치)'를 붙인다. 세는 말 뒤 하한("300가구 이상")도 본다.
        src = {"S1": "행사에는 최소 2,000명이 참여했다. 신청 가구는 300가구 이상이었다. At least 1,500 people joined. "
                     "More than 40 percent of riders were students."}
        for body, lang in (("행사에는 2,000명이 참여했다 [S1].", "ko"), ("신청 가구는 300가구였다 [S1].", "ko"),
                           ("1,500 people joined [S1].", "en"), ("40 percent of riders were students [S1].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual(1, len(changes["bound_conflict"]), body)
        for body, lang in (("행사에는 최소 2,000명이 참여했다 [S1].", "ko"), ("신청 가구는 300가구 이상이었다 [S1].", "ko"),
                           ("At least 1,500 people joined [S1].", "en"), ("More than 40 percent of riders were students [S1].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual([], changes["bound_conflict"], body)

    def test_value_moved_to_parallel_subject_is_marked(self):
        # 2026-10-08 2회차 품질 회차: 원문 한 대상의 수치를 나란히 나오는 다른 대상의 값으로 옮기면 '(출처 불일치)'.
        src = {"S1": "1년 동안 심야버스 이용객은 18% 늘었고 지하철 막차 이용객은 4% 늘었다. 시범 지역 주민의 30%가 버스를 탄다. "
                     "급속 충전기 평균 대기 시간은 지난해 18분에서 올해 11분으로 줄었다. 버스 이용객은 12% 늘었다.",
               "S2": "Leak repairs reported by customers rose 40 percent, and billing complaints rose 15 percent. "
                     "Average household water use fell 9 percent, while commercial water use fell 3 percent."}
        for body, lang in (("1년 동안 지하철 막차 이용객이 18% 늘었다 [S1].", "ko"),
                           ("Billing complaints rose 40 percent [S2].", "en"), ("Commercial water use fell 9 percent [S2].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertIn("불일치" if lang == "ko" else "mismatch", text, body)
            self.assertEqual(1, len(changes["subject_conflict"]), body)
        for body, lang in (("1년 동안 심야버스 이용객은 18% 늘었다 [S1].", "ko"), ("지하철 막차 이용객은 4% 늘었다 [S1].", "ko"),
                           ("시범 지역 버스 이용객이 12% 늘었다 [S1].", "ko"),
                           ("급속 충전기 평균 대기 시간이 18분에서 11분으로 줄었다 [S1].", "ko"),
                           ("Leak repairs rose 40 percent [S2].", "en"), ("Household water use fell 9 percent [S2].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertNotIn("불일치" if lang == "ko" else "mismatch", text, body)
            self.assertEqual([], changes["subject_conflict"], body)

    def test_per_unit_value_moved_to_total_or_other_unit_is_marked(self):
        # 2026-10-09 품질 회차: 원문의 1인당·가구당 값을 총계로(또는 1인당↔가구당) 말하면 '(출처 불일치)'.
        src = {"S1": "시는 청년 정착 지원금으로 1인당 20만 원을 지급했다. 에너지 바우처는 가구당 15만 원이었고, 사업비는 총 36억 원이었다.",
               "S2": "The state paid a rebate of 350 dollars per household. The budget was 21 million dollars in total."}
        for body, lang in (("청년 정착 지원금 총액은 20만 원이었다 [S1].", "ko"), ("에너지 바우처는 1인당 15만 원이었다 [S1].", "ko"),
                           ("The rebate cost 350 dollars in total [S2].", "en"),
                           ("The budget was 21 million dollars per household [S2].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertIn("불일치" if lang == "ko" else "mismatch", text, body)
            self.assertEqual(1, len(changes["basis_conflict"]), body)
        for body, lang in (("청년 정착 지원금은 1인당 20만 원이었다 [S1].", "ko"), ("에너지 바우처 사업비는 총 36억 원이었다 [S1].", "ko"),
                           ("에너지 바우처는 15만 원이었다 [S1].", "ko"),
                           ("The state paid 350 dollars per household [S2].", "en"), ("The budget totaled 21 million dollars [S2].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertNotIn("불일치" if lang == "ko" else "mismatch", text, body)
            self.assertEqual([], changes["basis_conflict"], body)

    def test_per_site_vehicle_school_and_average_value_moved_is_marked(self):
        # 2026-10-09 2회차: 곳당·대당·학교당·평균 값을 총계나 다른 기준으로 말하면 '(출처 불일치)'. 평균은 단위당 값과는 어긋나지 않는다.
        src = {"S1": "시는 대당 1억 원의 보조금을 지급했다. 새 충전소의 설치비는 평균 2억 원이었고, 보조금 총액은 120억 원이었다.",
               "S2": "The district gave a grant of 25,000 dollars per school. Library branches received an average of 1,800 new books."}
        for body, lang in (("새 충전소 설치비는 총 2억 원이었다 [S1].", "ko"),
                           ("The grant was 25,000 dollars per student [S2].", "en"),
                           ("Libraries received 1,800 new books in total [S2].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertIn("불일치" if lang == "ko" else "mismatch", text, body)
            self.assertEqual(1, len(changes["basis_conflict"]), body)
        for body, lang in (("새 충전소 설치비는 평균 2억 원이었다 [S1].", "ko"), ("충전소 1곳당 설치비는 2억 원이었다 [S1].", "ko"),
                           ("보조금 총액은 120억 원이었다 [S1].", "ko"),
                           ("Each school received a grant of 25,000 dollars [S2].", "en"),
                           ("Each library branch received 1,800 new books on average [S2].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertNotIn("불일치" if lang == "ko" else "mismatch", text, body)
            self.assertEqual([], changes["basis_conflict"], body)

    def test_cited_claim_absent_from_source_wording_is_marked(self):
        # 2026-10-09 3회차: 수치 없이 원문에 없는 추론·사실을 인용만 달아 말하면 '(출처 불일치)'(wording_conflict).
        # 같은 문자 체계일 때만 보고, 바꿔 말한 맞는 문장·번역 인용·다음 행동 절은 건드리지 않는다.
        src = {"S1": "담당자는 기온과 점유 인원을 기록했지만 대조군은 두지 않았다. 사고 건수가 적어 통계적으로 유의한지는 검정하지 않았다.",
               "S2": "The association noted that the survey was voluntary and may over-represent residents who supported the project. "
                     "Of 210 responses, 58 percent said sleep quality had improved since the barrier was built."}
        for body, lang in (("대조군을 둔 덕분에 효과 크기가 정확히 확인됐다 [S1].", "ko"),
                           ("Most opponents of the project had moved away before residents were polled [S2].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertIn("불일치" if lang == "ko" else "mismatch", text, body)
            self.assertEqual(1, len(changes["wording_conflict"]), body)
        for body, lang in (("담당자는 대조군을 두지 않았다 [S1].", "ko"), ("사고 건수가 적어 유의성은 검정하지 않았다 [S1].", "ko"),
                           ("설문은 자발 참여라 사업 지지 주민이 많이 응답했을 수 있다 [S2].", "ko"),
                           ("The voluntary survey may over-represent residents who supported the project [S2].", "en"),
                           ("The department kept no control group [S1].", "en"),
                           ("보고서에 따르면 담당자는 대조군을 두지 않았다 [S1].", "ko"),
                           # 8회차: 유보·부정 문장은 원문보다 덜 말하는 쪽이라 낱말 대조로 표시하지 않는다(독립 라벨에서 대부분 맞는 문장).
                           ("대조군이 없어 효과 크기를 확정할 수 없다 [S1].", "ko"),
                           ("An unusually cold counting week might explain part of the drop [S2].", "en"),
                           ("According to the association, the survey may over-represent supporters of the project [S2].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertNotIn("불일치" if lang == "ko" else "mismatch", text, body)
            self.assertEqual([], changes["wording_conflict"], body)
        text, changes = mark_report_claims("## 다음 행동\n- 인접 미설치 건물을 비교군으로 둔다 [S1].\n", src, "ko")
        self.assertNotIn("불일치", text)

    def test_subject_swap_ignores_plural_and_different_count_nouns(self):
        # 2026-10-09 3회차: "the barrier"와 "noise barriers"는 같은 대상이고, "2.4-mile"과 "71 decibels"는 다른 종류 수치다.
        # 옛 코드는 둘을 다르게·같게 세어 맞는 인용 문장에 '(source mismatch)'(subject_conflict)를 붙였다.
        src = {"S1": "The state transportation department installed noise barriers along a 2.4-mile stretch of Route 9 in 2024. "
                     "Daytime noise readings at 12 homes near the barrier fell from 71 decibels to 64 decibels after construction."}
        text, changes = self.mark("The barrier covers a 2.4-mile stretch of Route 9 and was installed in 2024 [S1].", src)
        self.assertNotIn("mismatch", text)
        self.assertEqual([], changes["subject_conflict"])

    def test_derived_korean_values_are_read_as_source_values(self):
        # 8회차(holdout4): 단위 기호 ㎏, 단위당 값 환산, 세는 말이 다른 개수의 몫, '1건당', '10명 중 약 8명', 건수×건당 금액.
        src = {"S1": "주민이 꽁초를 가져오면 1g당 20원을 지급했다. 참여 점포는 전체 410개 점포 가운데 152곳이었다. "
                     "배송 건수는 26,000건이었고 배송비는 시가 건당 3,500원씩 부담했다. 사업비는 1억 2천만 원, 이용 건수는 5,400건이었다. "
                     "이용자의 78%가 여성이었다."}
        for body in ("꽁초 1㎏을 가져오면 2만 원을 받을 수 있었다 [S1].", "점포의 약 37%가 참여했다 [S1].",
                     "시가 부담한 배송비는 모두 9,100만 원 정도였다 [S1].", "이용 1건당 사업비는 약 2만 2천 원이었다 [S1].",
                     "이용자 10명 중 약 8명은 여성이었다 [S1]."):
            text, changes = self.mark(body, src, "ko")
            self.assertNotIn("불일치", text, body)
        text, _ = self.mark("꽁초 1㎏을 가져오면 5만 원을 받을 수 있었다 [S1].", src, "ko")
        self.assertIn("불일치", text)   # 단위당 값과 맞지 않는 금액은 그대로 표시

    def test_rate_rule_does_not_hide_a_unit_swap(self):
        # 단위당 값 환산은 서로 다른 단위를 잇는 값만 쓴다. 같은 단위 두 값의 비율로는 km→mile 바꿔치기가 서로 상쇄돼 통과했다.
        src = {"S1": "Average bus speeds inside it rose from 11 to 13 kilometers per hour."}
        text, _ = self.mark("Average bus speeds inside the zone rose from 11 to 13 miles per hour [S1].", src)
        self.assertIn("mismatch", text)

    def test_survey_share_restated_as_population_share_is_marked(self):
        # 8회차(holdout4): 설문 응답자의 몫을 주민·시민 전체의 몫으로 말하면 범위를 넓힌 것(scope_conflict).
        src = {"S1": "구 설문에서 이용자 450명 중 91%가 귀가가 더 안전하게 느껴졌다고 답했다.",
               "S2": "A resident survey of 600 households found 58 percent supported continuing the program.",
               "S3": "Census data show 58 percent of residents rent their homes."}
        for body, lang in (("다온구 주민의 91%가 귀가가 더 안전해졌다고 느꼈다 [S1].", "ko"),
                           ("A majority of pilot-district residents support continuing the program [S2].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertIn("불일치" if lang == "ko" else "mismatch", text, body)
            self.assertEqual(1, len(changes["scope_conflict"]), body)
        for body, lang in (("설문에 응한 이용자의 91%가 더 안전하다고 답했다 [S1].", "ko"),
                           ("In the survey, 58 percent of households supported continuing the program [S2].", "en"),
                           ("Most residents rent their homes [S3].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual([], changes["scope_conflict"], body)

    def test_attribution_the_source_declined_is_marked(self):
        # 8회차(holdout4): 원문이 '보기 어렵다'·'not necessarily due to'로 유보한 귀속·평가를 결론처럼 말하면 causal_conflict.
        src = {"S1": "꽁초 수는 320개에서 210개로 줄었다. 환경과는 단속 강화가 함께 이루어져 감소분 전체를 보상제 효과로 보기는 어렵다고 밝혔다.",
               "S2": "The audit said the gap could reflect differences in road type and was not necessarily due to the app.",
               "S3": "신고는 6% 줄었으나, 경찰은 신고 건수가 적어 의미 있는 변화로 보기 어렵다고 밝혔다."}
        for body, lang in (("환경과는 꽁초 감소가 전적으로 보상제의 효과라고 결론지었다 [S1].", "ko"),
                           ("The audit attributed the repair gap to the app [S2].", "en"),
                           ("경찰은 신고가 6% 줄어든 것을 의미 있는 감소로 평가했다 [S3].", "ko")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual(1, len(changes["causal_conflict"]), body)
        for body, lang in (("환경과는 감소분 전체를 보상제 효과로 보기 어렵다고 밝혔다 [S1].", "ko"),
                           ("The audit said the gap was not necessarily due to the app [S2].", "en"),
                           ("신고는 6% 줄었다 [S3].", "ko")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual([], changes["causal_conflict"], body)

    def test_cause_the_source_only_called_possible_is_marked(self):
        # 11회차: 원문이 원인을 가능성으로만 말하거나('may reflect', '줄였을 수 있다') 근거 한계를 밝혔는데 단정하면 causal_conflict.
        src = {"S1": "Litter complaints fell from 300 to 180. The office said the new bins may reflect part of the drop, "
                     "but the numbers are too small to draw firm conclusions.",
               "S2": "참여 학교의 결석은 12% 줄었다. 교육청은 아침 급식이 결석을 줄였을 수 있다고 보면서도 비교 학교 선정에 한계가 있다고 적었다.",
               "S3": "Residents may apply online. Wait times fell from 9 to 6 days after the portal opened."}
        for body, lang in (("The new bins caused the drop in litter complaints [S1].", "en"),
                           ("The data proved the bins worked [S1].", "en"),
                           ("교육청은 아침 급식이 결석을 줄였다고 결론 내렸다 [S2].", "ko")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual(1, len(changes["causal_conflict"]), body)
        for body, lang in (("The office said the new bins may have contributed to the drop [S1].", "en"),
                           ("교육청은 아침 급식이 결석을 줄였을 수 있다고 봤다 [S2].", "ko"),
                           ("The online portal cut wait times from 9 to 6 days [S3].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual([], changes["causal_conflict"], body)

    def test_dropped_or_added_eligibility_condition_is_marked(self):
        # 11회차: 원문이 조건으로 묶은 이용을 조건 없다고, 조건 없다고 한 것을 조건부로 말하면 scope_conflict.
        src = {"S1": "Garden plots were rented to residents only if they completed a safety course. Plot fees were waived for "
                     "all renters regardless of income.",
               "S2": "상담실은 평일 오후에만 문을 열었다. 상담은 사전 예약을 마친 학생만 이용할 수 있었다.",
               "S3": "Only 12 percent of renters grew vegetables in winter."}
        for body, lang in (("Residents could rent garden plots without any restrictions [S1].", "en"),
                           ("Plot fees were waived only for low-income renters [S1].", "en"),
                           ("상담실은 평일 오후와 주말에도 문을 열었다 [S2].", "ko"),
                           ("상담은 사전 예약 여부와 관계없이 학생 누구나 이용할 수 있었다 [S2].", "ko")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual(1, len(changes["scope_conflict"]), body)
        more = {"S1": "Plot fees of $3 per day applied after 6 hours, except overnight between 9 p.m. and 7 a.m. "
                      "Crews also planted street trees without a request unless an owner opted out.",
                "S2": "분수는 기온이 30도 이상이고 바람이 약할 때만 가동되었다."}
        for body, lang in (("Plot fees of $3 per day applied after 6 hours, including overnight [S1].", "en"),
                           ("Crews planted street trees only where an owner made a request [S1].", "en"),
                           ("분수는 기온 30도 이상이면 바람과 관계없이 가동되었다 [S2].", "ko")):
            text, changes = self.mark(body, more, lang)
            self.assertEqual(1, len(changes["scope_conflict"]), body)
        for body, lang in (("Residents could rent garden plots only if they completed a safety course [S1].", "en"),
                           ("Plot fees were waived for every renter, whatever their income [S1].", "en"),
                           ("상담실은 평일 오후에만 운영되었다 [S2].", "ko"),
                           ("Few renters, at any time of year, grew vegetables in winter [S3].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual([], changes["scope_conflict"], body)

    def test_remainders_unit_bases_small_per_unit_quotients_and_base_years(self):
        # 11회차(holdout7): 세 갈래 응답의 나머지, '1톤당' 기준 수량, 10 미만 단위당 몫, 부분을 말한 몫 곱, 비교 기준 연도.
        src = {"S1": "Of 900 residents surveyed, 61 percent supported the plan, 26 percent opposed it, and the rest were unsure. "
                     "Crews completed 1,560 clearings for 240 households.",
               "S2": "운영 기간 물 사용량은 3,200톤이었고 운영비는 1,280만 원이었다. 신청 가구 250곳에 방문은 모두 455회였다. "
                     "운영비는 연 2억 4천만 원이었고 이 가운데 40%를 도비로 지원받았다. 2025년 이용자는 12,000명이었다. 2024년 이용자는 8,000명이었다."}
        for body, lang in (("About 13 percent of respondents were unsure [S1].", "en"),
                           ("Crews cleared an average of 6.5 sidewalks per household [S1].", "en"),
                           ("운영비는 물 1톤당 약 4,000원꼴이었다 [S2].", "ko"),
                           ("신청 가구 1곳당 평균 1.8회 방문이 이루어졌다 [S2].", "ko"),
                           ("운영비 가운데 도비 지원액은 연 9,600만 원이었다 [S2].", "ko"),
                           ("이용자는 2024년보다 50% 늘어 12,000명을 기록했다 [S2].", "ko")):
            text, _ = self.mark(body, src, lang)
            self.assertNotIn("불일치" if lang == "ko" else "mismatch", text, body)
        for body, lang in (("About 9 percent of respondents were unsure [S1].", "en"),
                           ("Crews cleared an average of 8.5 sidewalks per household [S1].", "en"),
                           ("운영비는 물 1톤당 약 9,000원꼴이었다 [S2].", "ko"),
                           ("신청 가구 1곳당 평균 2.4회 방문이 이루어졌다 [S2].", "ko"),
                           ("운영비 가운데 도비 지원액은 연 1억 2천만 원이었다 [S2].", "ko"),
                           ("2024년 이용자는 12,000명이었다 [S2].", "ko")):
            text, _ = self.mark(body, src, lang)
            self.assertIn("불일치" if lang == "ko" else "mismatch", text, body)

    def test_exact_quotients_shares_and_month_lengths_are_read_as_source_values(self):
        # 10회차(holdout6): '12-month', 세는 말이 다른 개수의 몫·나머지, 어림 표시 없는 정확한 나눗셈·절반.
        src = {"S1": "Over 12 months the fridges collected 38,400 kilograms of food.",
               "S2": "충전기 36곳에서 1년 동안 9,720회 충전했다. 조성비는 3억 8천만 원이었으며 이 중 절반은 도비 보조금이었다. "
                     "1,050구획 가운데 84개가 시즌 중 경작을 포기했다. 컵 대여는 31만 2천 건이었고 반납률은 91%였다."}
        for body, lang in (("Over the 12-month pilot, donations averaged roughly 3,200 kilograms per month [S1].", "en"),
                           ("충전기 한 곳당 연평균 충전 횟수는 270회였다 [S2].", "ko"),
                           ("조성비 3억 8천만 원 가운데 도비 보조금은 1억 9천만 원이었다 [S2].", "ko"),
                           ("시즌 종료 때까지 경작을 이어간 구획은 약 92%였다 [S2].", "ko"),
                           ("반납되지 않은 컵은 약 2만 8천 개로 추산된다 [S2].", "ko")):
            text, _ = self.mark(body, src, lang)
            self.assertNotIn("불일치" if lang == "ko" else "mismatch", text, body)
        text, _ = self.mark("충전기 한 곳당 연평균 충전 횟수는 300회였다 [S2].", src, "ko")
        self.assertIn("불일치", text)
        # PR #18 Codex 리뷰: 나눗셈은 단위당 표현이 있을 때만, 몫 곱은 전체 값도 함께 말할 때만 인정한다.
        cost = {"S1": "The project cost 100 million dollars and involved 20 volunteers."}
        text, _ = self.mark("The project cost 5 million dollars [S1].", cost)
        self.assertIn("mismatch", text)
        text, _ = self.mark("The project cost 5 million dollars per volunteer [S1].", cost)
        self.assertNotIn("mismatch", text)
        text, _ = self.mark("충전 횟수는 270회였다 [S2].", src, "ko")
        self.assertIn("불일치", text)
        # 연령대 '20~30대'는 다른 세는 말과 섞지 않는다(60대 ÷ 2개 = 30 같은 우연한 몫).
        text, _ = self.mark("참여자는 대부분 20~30대였다 [S1].", {"S1": "2개 동에서 참여자 가운데 60대 이상이 64%였다."}, "ko")
        self.assertIn("불일치", text)

    def test_minority_survey_share_said_without_of_called_most_is_marked(self):
        # 10회차(holdout6): 원문 설문 몫이 "of" 없이 쓰여도("23 percent said …", "응답이 35%") '대부분·most'로 말하면 share_conflict.
        src = {"S1": "The evaluation surveyed 610 fridge users; 23 percent said it was their main source of fresh produce.",
               "S2": "참여자 620명 설문에서 '채소 구입비가 줄었다'는 응답이 35%였다."}
        for body, lang in (("Most surveyed users said the fridges were their main source of fresh produce [S1].", "en"),
                           ("응답자 대다수가 채소 구입비가 줄었다고 답했다 [S2].", "ko")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual(1, len(changes["share_conflict"]), body)
        text, changes = self.mark("About a quarter of surveyed users said the fridges were their main source of fresh produce [S1].",
                                  src)
        self.assertEqual([], changes["share_conflict"])

    def test_option_under_review_stated_as_done_is_marked(self):
        # 10회차(holdout6): '늘리는 방안을 검토하고 있다'를 '이미 늘려 운영하고 있다'로 쓰면 plan_conflict.
        src = {"S1": "군은 주말 관리 인력을 2명에서 4명으로 늘리는 방안을 검토하고 있다."}
        text, changes = self.mark("군은 이미 주말 관리 인력을 4명으로 늘려 운영하고 있다 [S1].", src, "ko")
        self.assertEqual(1, len(changes["plan_conflict"]))
        text, changes = self.mark("군은 주말 인력을 4명으로 늘리는 방안을 검토 중이다 [S1].", src, "ko")
        self.assertEqual([], changes["plan_conflict"])

    def test_different_main_reason_is_marked(self):
        # 10회차(holdout6): 원문과 다른 '주된 이유'를 대면 causal_conflict. 같은 이유를 바꿔 말한 문장은 그대로.
        src = {"S1": "Volunteers reported that a shortage of replacement parts was the main reason repairs failed.",
               "S2": "반대한 점주들은 주로 반납 처리에 드는 시간을 이유로 들었다. 이용하지 않은 이유로는 '위치를 몰라서'가 가장 많았다."}
        for body, lang in (("Repairs most often failed because volunteers lacked the necessary skills [S1].", "en"),
                           ("반대한 점주들은 주로 컵 분실에 따른 비용을 이유로 꼽았다 [S2].", "ko"),
                           ("이용하지 않은 사람들은 주로 충전 시간이 길다는 점을 이유로 들었다 [S2].", "ko")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual(1, len(changes["causal_conflict"]), body)
        for body, lang in (("Repairs most often failed because replacement parts were in short supply [S1].", "en"),
                           ("반대한 점주들은 주로 반납 처리 시간을 이유로 들었다 [S2].", "ko"),
                           ("이용하지 않은 사람들은 주로 위치를 몰라서라고 답했다 [S2].", "ko")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual([], changes["causal_conflict"], body)

    def test_approximate_suffixes_total_amounts_and_without_are_not_flagged(self):
        # 12회차(holdout8): '수준'·'규모'는 어림 표시, '전체 지원액'은 범위가 아니라 합계, '삭감 없이'의 '없이'는 부정 뒤집기가 아니다.
        src = {"S1": "8개월간 매출은 1억 1,200만 원이었고, 이용자는 대부분 70대 이상이었다. 참가자 360명에게 1인당 10만 원 바우처를 줬다. "
                     "반지하 주택 140가구에 공사를 했고 실제 평균 지원액은 186만 원이었다.",
               "S2": "위원회는 2026년 운영 예산 9천만 원을 원안대로 가결했다."}
        for body in ("8개월간 매출은 약 1억 1천만 원으로, 월평균 1,400만 원 수준이었다 [S1].", "지급된 바우처 총액은 3,600만 원 규모였다 [S1].",
                     "시범사업 전체 지원액은 약 2억 6천만 원이었다 [S1].", "위원회는 2026년 운영 예산 9천만 원을 삭감 없이 통과시켰다 [S2]."):
            text, _ = self.mark(body, src, "ko")
            self.assertNotIn("불일치", text, body)
        text, _ = self.mark("8개월간 매출은 약 1억 1천만 원으로, 월평균 2,000만 원 수준이었다 [S1].", src, "ko")
        self.assertIn("불일치", text)
        text, _ = self.mark("위원회는 2026년 운영 예산 9천만 원을 원안대로 가결하지 않았다 [S2].", src, "ko")
        self.assertIn("불일치", text)

    def test_intention_stated_as_already_done_is_marked(self):
        # 12회차(holdout8a): 원문이 의도·계획·권고로만 말한 것을 '이미·already' 시행했다고 쓰면 plan_conflict(수치 없어도).
        src = {"S1": "시는 올해 사업을 이어가되 겨울철에는 실내 치유 프로그램을 추가하겠다고 밝혔다.",
               "S2": "The district plans to launch a free paint voucher program next spring."}
        for body, lang in (("시는 겨울철 실내 치유 프로그램을 이미 도입했다 [S1].", "ko"),
                           ("The district has already launched a free paint voucher program [S2].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual(1, len(changes["plan_conflict"]), body)
        for body, lang in (("시는 겨울철 실내 치유 프로그램을 추가할 계획이다 [S1].", "ko"),
                           ("The district plans to launch a free paint voucher program [S2].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual([], changes["plan_conflict"], body)

    def test_funder_swap_for_the_same_amount_is_marked(self):
        # 12회차(holdout8a): 같은 금액의 재원·부담 주체를 바꾸면 subject_conflict.
        src = {"S1": "트럭 운영은 지역 농협에 위탁했으며, 군은 차량 구입비 1억 4천만 원을 부담했다.",
               "S2": "The pilot's first-year cost was $3.1 million, paid from the city's housing trust fund."}
        for body, lang in (("차량 구입비 1억 4천만 원은 지역 농협이 부담했다 [S1].", "ko"),
                           ("The first-year cost of $3.1 million came from the general fund [S2].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual(1, len(changes["subject_conflict"]), body)
        for body, lang in (("차량 구입비 1억 4천만 원은 군이 부담했다 [S1].", "ko"),
                           ("The first-year cost of $3.1 million came from the housing trust fund [S2].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual([], changes["subject_conflict"], body)

    def test_unhedged_small_sum_or_difference_needs_an_arithmetic_cue(self):
        # 13회차(holdout8a): 작은 정수가 원문 아무 두 값의 합·차와 우연히 맞아 바꾼 조건·기간이 통과하던 결함.
        from hprc.verification import _absent_values
        en = ("The city offered a $600 stipend to residents aged 16 to 24 who worked at least 120 hours. "
              "The city opened all 9 pools, compared with 6 pools in 2024.")
        ko = "18가구가 공사 후 1년 안에 임대료 인상을 통보받았다. 구의회는 집주인에게 2년간 임대료 동결 확약서를 받으라고 권고했다."
        self.assertEqual(["30"], _absent_values("Eligibility was open to residents aged 16 to 30 [S1].", en))
        self.assertEqual(["3년"], _absent_values("구는 집주인에게 3년간 임대료 동결 확약서를 받도록 했다 [S2].", ko))
        self.assertEqual([], _absent_values("The number of open pools rose by 3 [S1].", en))
        self.assertEqual([], _absent_values("Altogether 15 pools were open across the two seasons [S1].", en))
        self.assertEqual([], _absent_values("가람군 놀이터에는 첫 1년 동안 반려견 600마리가 입장했다 [S1].", "반려견 600마리가 입장했다."))

    def test_difference_amount_and_year_are_not_comparison_sides(self):
        # 13회차: '3 more pools than in 2024'의 3은 차이, 2024는 연도라 비교 뒤집기가 아니다.
        src = {"S1": "The city opened all 9 pools, compared with 6 pools in 2024."}
        for body in ("The city opened 3 more pools than in 2024 [S1].", "Riders paid $7 more than $5 fares [S1]."):
            text, changes = self.mark(body, {"S1": src["S1"] + " Riders paid $12, up from $5."}, "en")
            self.assertEqual([], changes["antonym_conflict"], body)
        text, changes = self.mark("The new fare of $12 was less than $5 [S1].", {"S1": "The new fare was $12, compared with $5 before."}, "en")
        self.assertEqual(1, len(changes["antonym_conflict"]))

    def test_payer_swap_without_the_same_amount_is_marked(self):
        # 13회차(holdout9): 금액 없이·다른 동사로 말한 재원, 정부 층위 바꿈, '전액'으로 넓힌 재원.
        src = {"S1": "The pilot budget was $205,000, funded by the city general fund.",
               "S2": "The $187,000 cost was covered by a federal fire prevention grant.",
               "S3": "설치비 2억 3,000만 원은 행정안전부 특별교부세로 충당했고, 연간 통신·유지비 1,400만 원은 구가 부담한다.",
               "S4": "사업비는 1억 2,600만 원으로, 법무부 공모사업비 7,000만 원과 시비로 충당했다."}
        for body, lang in (("The pilot was funded mainly through a state aging grant [S1].", "en"),
                           ("The program cost $187,000, funded by a state fire prevention grant [S2].", "en"),
                           ("설치비 2억 3,000만 원은 구 예산으로 부담했다 [S3].", "ko"),
                           ("사업비 전액을 법무부 공모사업비로 충당했다 [S4].", "ko")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual(1, len(changes["subject_conflict"]), body)
        for body, lang in (("The pilot was paid for by the city general fund [S1].", "en"),
                           ("The program cost $187,000, paid for by a federal fire prevention grant [S2].", "en"),
                           ("연간 유지비 1,400만 원은 구가 부담한다 [S3].", "ko"),
                           ("사업비는 법무부 공모사업비와 시비로 충당했다 [S4].", "ko")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual([], changes["subject_conflict"], body)

    def test_completed_action_from_a_proposal_is_marked_without_already(self):
        # 13회차(holdout9): '이미' 없이 완료로 말했는데 원문은 제안·요청·권고·미확정.
        src = {"S1": "Staff recommend expanding to two more towns in 2027, subject to council approval.",
               "S2": "센터는 2026년 하반기 통역사 3명 증원을 요청했으나 예산은 아직 확정되지 않았다.",
               "S3": "소방서는 점포주 확인 후 출동하는 2단계 절차 도입을 구에 제안했다.",
               "S4": "The council approved the expansion to two more towns in March."}
        for body, lang in (("Staff have expanded the program to two more towns [S1].", "en"),
                           ("시는 하반기 통역사 3명 증원 예산을 확정했다 [S2].", "ko"),
                           ("구는 점포주 확인 후 출동하는 2단계 절차를 도입했다 [S3].", "ko")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual(1, len(changes["plan_conflict"]), body)
        for body, lang in (("Staff recommend expanding the program to two more towns [S1].", "en"),
                           ("The council has approved the expansion to two more towns [S4].", "en"),
                           ("소방서는 2단계 절차 도입을 구에 제안했다 [S3].", "ko")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual([], changes["plan_conflict"], body)

    def test_metric_tons_cross_year_months_and_rather_than(self):
        # 13회차: 'metric tons' ↔ 'tonnes', 해를 넘는 달 범위의 길이, 'rather than'으로 부정한 방식을 사실로 말한 문장.
        from hprc.verification import _absent_values
        self.assertEqual([], _absent_values("Lockers gathered 18.6 tonnes [S1].", "The lockers collected 18.6 metric tons of batteries."))
        self.assertEqual([], _absent_values("사업은 2025년 9월부터 10개월간 진행됐다 [S1].",
                                            "한빛군은 2025년 9월부터 2026년 6월까지 청년에게 취득비를 지원했다."))
        self.assertEqual(["11개월"], _absent_values("사업은 11개월간 진행됐다 [S1].", "한빛군은 2025년 9월부터 2026년 6월까지 지원했다."))
        src = {"S1": "The office estimated that the events diverted about 11 metric tons of material, "
                     "using average item weights rather than measuring each item."}
        text, changes = self.mark("The events diverted 11 tonnes of material, a figure measured by weighing each item [S1].", src, "en")
        self.assertEqual(1, len(changes["negation_conflict"]))
        text, changes = self.mark("The figure used average item weights rather than measuring each item [S1].", src, "en")
        self.assertEqual([], changes["negation_conflict"])

    def test_negation_over_a_coordinated_subject_is_marked(self):
        # 14회차: 원문 부정이 'A and B were not accepted'처럼 나열한 주어 전체에 걸린다.
        src = {"S1": "Residents could drop off household batteries up to 9 volts; lithium batteries over 100 watt-hours "
                     "and vehicle batteries were not accepted."}
        text, changes = self.mark("Vehicle batteries and lithium batteries over 100 watt-hours were accepted at the lockers [S1].", src, "en")
        self.assertEqual(1, len(changes["negation_conflict"]))
        for body in ("Residents could drop off household batteries up to 9 volts at the lockers [S1].",
                     "Lithium batteries over 100 watt-hours and vehicle batteries were not accepted [S1]."):
            text, changes = self.mark(body, src, "en")
            self.assertEqual([], changes["negation_conflict"], body)

    def test_value_moved_to_another_listed_member_is_marked(self):
        # 14회차: 원문이 나열한 대상 중 한 곳의 수치를 나열의 다른 대상에 붙인 문장.
        src = {"S1": "The county installed 24 lockers at grocery stores and fire stations. "
                     "Lockers at grocery stores collected 71 percent of the locker total.",
               "S2": "외국인 주민이 주민센터·보건소·학교와 통화할 때 통역사가 연결된다. 통화의 46%는 학교 관련 문의였다."}
        for body, lang in (("Fire stations accounted for 71 percent of the locker total [S1].", "en"),
                           ("통화의 46%는 보건소 관련 문의였다 [S2].", "ko")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual(1, len(changes["subject_conflict"]), body)
        for body, lang in (("Grocery-store lockers collected 71 percent of the locker total [S1].", "en"),
                           ("The 24 lockers were placed at grocery stores and fire stations [S1].", "en"),
                           ("통화의 46%는 학교 관련 문의였다 [S2].", "ko")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual([], changes["subject_conflict"], body)

    def test_paraphrased_subject_and_share_denominator_are_not_flagged(self):
        # 14회차(holdout9 오표시): 주제 낱말 하나로 대상을 옮겼다고 읽거나, 주장이 함께 말한 값의 대상 낱말을 옮김으로 읽거나,
        # '전체 이용의 40%'의 '전체'를 범위 넓힘으로 읽던 오표시. 사람 집단을 '전체'로 넓힌 문장은 계속 표시한다.
        src = {"S1": "The district tested a parent-facing app showing real-time school bus locations on 38 of its 112 routes. "
                     "Families on pilot routes could receive an alert when the bus was 10 minutes from their stop. "
                     "Calls about late buses on pilot routes averaged 22 per week. "
                     "The location data was shown with a delay of up to 45 seconds.",
               "S2": "서강군은 방치된 빈집 30채를 빌려 리모델링했다. 2026년 3월 기준 30채 중 26채에 입주가 완료됐다.",
               "S3": "언어별로는 베트남어가 1,920건으로 가장 많았다. 7개월간 이용 건수는 4,830건이었다.",
               "S4": "학부모 설문 응답자 412명 중 74%가 설치에 찬성했다."}
        for body, lang in (("Bus positions appeared with a lag of no more than 45 seconds [S1].", "en"),
                           ("빈집 30채 중 26채, 즉 약 87%에 입주가 이뤄졌다 [S2].", "ko"),
                           ("베트남어 통화는 전체 이용의 약 40%를 차지했다 [S3].", "ko")):
            text, changes = self.mark(body, src, lang)
            self.assertEqual([], changes["mismatch"], body)
        text, changes = self.mark("전체 학부모의 74%가 설치에 찬성했다 [S4].", src, "ko")
        self.assertEqual(1, len(changes["scope_conflict"]))

    def test_magnitude_word_swap_is_marked_and_equal_value_is_not(self):
        src = {"S1": "2025년 노후 하수관 정비 사업에 420억 원이 투입됐다. 정비 구간 주변에는 12만 가구가 산다.",
               "S2": "The state awarded a 4.2 million dollar grant. Annual ridership was 1.6 million trips."}
        for body, lang in (("정비 사업에 420만 원이 투입됐다 [S1].", "ko"),
                           ("The state awarded a 4.2 billion dollar grant [S2].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertIn("불일치" if lang == "ko" else "mismatch", text, body)
            self.assertEqual(1, len(changes["mismatch"]), body)
        for body, lang in (("정비 사업에 420억 원이 투입됐다 [S1].", "ko"), ("정비 구간 주변에는 120,000가구가 산다 [S1].", "ko"),
                           ("Annual ridership was 1,600,000 trips [S2].", "en"),
                           ("The state awarded a 4.2 million dollar grant [S2].", "en")):
            text, _ = self.mark(body, src, lang)
            self.assertNotIn("불일치" if lang == "ko" else "mismatch", text, body)

    def test_man_particle_is_not_a_magnitude(self):
        src = {"S1": "정비 공사는 3년 만에 끝났다. 신고는 17건이었다."}
        text, _ = self.mark("신고는 17건이었다 [S1].", src, "ko")
        self.assertNotIn("(출처 불일치)", text)
        self.assertEqual([3, 20000, 3], [int(v["value"]) for v in _quantity_values("3만큼, 2만 명, 3년 만에", [])])

    def test_abbreviated_and_compound_numbers_are_read_as_values(self):
        src = {"S1": "The dredging project cost 4.6 million dollars. The federal share was 3.8 million dollars. "
                     "The harbor had 12,000 vessel calls. A berth repair budget of 2.5 billion won is listed.",
               "S2": "2025년 지원 사업 예산은 1.2억 원이었다. 이용자는 35,000명이었다. 도서 구입비로 4천5백만 원이 쓰였다."}
        for body, lang in (("The dredging project cost $4.6bn [S1].", "en"), ("The federal share was $3.8B [S1].", "en"),
                           ("도서 구입비로 5천4백만 원이 쓰였다 [S2].", "ko"), ("지원 사업 예산은 1억 2천 원이었다 [S2].", "ko")):
            text, changes = self.mark(body, src, lang)
            self.assertIn("불일치" if lang == "ko" else "mismatch", text, body)
        for body, lang in (("The federal share was $3.8M [S1].", "en"), ("The federal share was $3.8m [S1].", "en"),
                           ("The harbor had 12k vessel calls [S1].", "en"),
                           ("A berth repair budget of 2.5bn won is listed [S1].", "en"),
                           ("지원 사업 예산은 1억 2천만 원이었다 [S2].", "ko"), ("이용자는 3만 5천 명이었다 [S2].", "ko"),
                           ("도서 구입비로 4,500만 원이 쓰였다 [S2].", "ko")):
            text, _ = self.mark(body, src, lang)
            self.assertNotIn("불일치" if lang == "ko" else "mismatch", text, body)

    def test_abbreviation_does_not_swallow_units_or_words(self):
        values = _quantity_values("5MB, 3.8 m, 18.4kW, 10 백신, 5천안, 3 만 명, 1조 5,000억 원", [])
        self.assertEqual([("5", "data_decimal"), ("3.8", "length"), ("18400.0", "power"), ("10", "unitless"),
                          ("5", "unitless"), ("30000", "명"), ("1500000000000", "KRW")],
                         [(str(v["value"]), v["dimension"]) for v in values])


if __name__ == "__main__":
    unittest.main()


class LabeledRoundTests(unittest.TestCase):
    """2026-10-10 라벨 평가 회차: 단위 환산·반올림·부정 뒤집기."""

    def mark(self, body, sources, lang="en"):
        head = "## Answer\n" if lang == "en" else "## 답\n"
        return mark_report_claims(head + body + "\n", sources, lang)

    def test_mass_and_length_units_compare_by_converted_value(self):
        src = {"S1": "The pilot diverted 1,800 tonnes of food waste along a 12-kilometer route."}
        for body in ("The pilot diverted 1,800 kilograms of food waste [S1].", "The route is 12 miles long [S1].",
                     "The route is a 12-mile stretch [S1]."):
            text, _ = self.mark(body, src)
            self.assertIn("(source mismatch)", text, body)
        text, _ = self.mark("That equals 1.8 million kilograms of food waste [S1].", src)
        self.assertNotIn("(source mismatch)", text)
        text, _ = mark_report_claims("## 답\n- 시는 하루 450킬로그램을 처리했다 [S1].\n", {"S1": "시는 하루 평균 450톤을 처리했다."}, "ko")
        self.assertIn("(출처 불일치)", text)

    def test_hedged_rounding_and_derived_values_are_not_marked(self):
        en = {"S1": "Visits rose to 3,047, compared with 2,210 a year earlier. Employment was 4.6 percent higher. "
                    "The repair cost 4.2 million dollars.",
              "S2": "A survey of 120 owners found that 71 raised prices."}
        for body in ("That is an increase of roughly 38 percent [S1].", "Employment was nearly 5 percent higher [S1].",
                     "The repair cost about 4 million dollars [S1].", "About 59 percent of surveyed owners raised prices [S2]."):
            text, _ = self.mark(body, en)
            self.assertNotIn("(source mismatch)", text, body)
        for body in ("Employment rose about 6 percent [S1].", "The repair cost about 5 million dollars [S1].",
                     "That is an increase of 38 percent and 120 new branches [S1]."):
            text, _ = self.mark(body, en)
            self.assertIn("(source mismatch)", text, body)
        ko = {"S1": "시는 하루 평균 450톤을 처리했다. 처리량 가운데 62%는 재활용됐다. 참여 학생 860명과 비참여 학생 910명을 비교했다.",
              "S2": "응답 교사 75명 중 52명이 나아졌다고 답했다."}
        for body in ("연간으로 환산하면 약 16만 톤이다 [S1].", "소각량은 하루 약 171톤이다 [S1].", "학생 1,770명을 비교했다 [S1].",
                     "응답 교사 10명 중 7명꼴로 나아졌다고 답했다 [S2].", "처리량의 약 5분의 3이 재활용됐다 [S1]."):
            text, _ = self.mark(body, ko, "ko")
            self.assertNotIn("(출처 불일치)", text, body)
        for body in ("연간으로 환산하면 약 30만 톤이다 [S1].", "응답 교사 10명 중 9명꼴로 나아졌다고 답했다 [S2].",
                     "학생 1,800명을 비교했다 [S1]."):
            text, _ = self.mark(body, ko, "ko")
            self.assertIn("(출처 불일치)", text, body)

    def test_quotients_points_lower_bounds_and_compound_numbers_are_derived(self):
        en = {"S1": "The clinic handled 4,200 calls over 7 days. Two thirds of callers were women. "
                    "The pass rate was 64 percent for the program and 51 percent for the comparison group. "
                    "Ridership fell from 3.2 million to 1.1 million riders. The line runs at 40Mbps."}
        for body in ("That is roughly 600 calls a day [S1].", "About 67 percent of callers were women [S1].",
                     "The program's pass rate was 13 points higher [S1].", "Ridership fell by more than 60 percent [S1].",
                     "Ridership fell by 2.1 million riders [S1]."):
            text, _ = self.mark(body, en)
            self.assertNotIn("(source mismatch)", text, body)
        for body in ("That is roughly 900 calls a day [S1].", "The program's pass rate was 9 points higher [S1].",
                     "Ridership fell by more than 80 percent [S1].", "The line runs at 40Gbps [S1]."):
            text, _ = self.mark(body, en)
            self.assertIn("(source mismatch)", text, body)
        ko = {"S1": "사업은 주민 640명에게 도시락 9,600개를 전달했다. 응답자 250명 중 231명이 만족했다. 월 지원금은 15만 원이었다. "
                    "보수에는 총 2만 4,500권을 들였다."}
        for body in ("주민 한 명당 15개꼴을 받았다 [S1].", "응답자 92%가 만족했다 [S1].", "지원금은 1년이면 180만 원이다 [S1].",
                     "보수에는 총 24,500권을 들였다 [S1]."):
            text, _ = self.mark(body, ko, "ko")
            self.assertNotIn("(출처 불일치)", text, body)
        for body in ("주민 한 명당 30개꼴을 받았다 [S1].", "응답자 85%가 만족했다 [S1].", "지원금은 1년이면 200만 원이다 [S1]."):
            text, _ = self.mark(body, ko, "ko")
            self.assertIn("(출처 불일치)", text, body)

    def test_antonym_flip_and_causal_reversal_are_marked(self):
        en = {"S1": "The council expanded night service because evening ridership had grown on the two routes. "
                    "The 2024 storm season lasted 5 weeks longer than the 2023 season."}
        for body, kind in (("Evening ridership grew on the two routes because the council expanded night service [S1].",
                            "causal_reversal_conflict"),
                           ("The 2024 storm season lasted 5 weeks shorter than the 2023 season [S1].", "antonym_conflict")):
            text, changes = self.mark(body, en)
            self.assertEqual(1, len(changes[kind]), body)
        for body in ("Night service was expanded because evening ridership had grown on the two routes [S1].",
                     "The 2024 storm season ran 5 weeks longer than the 2023 season [S1]."):
            text, changes = self.mark(body, en)
            self.assertNotIn("(source mismatch)", text, body)
        ko = {"S1": "정비 인력 부족으로 고장 차량 40대가 수리를 기다리고 있다. 신청자의 절반 이상이 60세 이상이었다."}
        for body, kind in (("고장 차량 40대가 밀리는 바람에 정비 인력이 부족해졌다 [S1].", "causal_reversal_conflict"),
                           ("신청자 대부분이 60세 미만이었다 [S1].", "antonym_conflict")):
            text, changes = self.mark(body, ko, "ko")
            self.assertEqual(1, len(changes[kind]), body)
        for body in ("정비 인력이 모자라 고장 차량 40대가 수리를 기다린다 [S1].", "신청자의 절반 이상이 60세를 넘었다 [S1]."):
            text, changes = self.mark(body, ko, "ko")
            self.assertNotIn("(출처 불일치)", text, body)

    def test_universal_scope_without_narrow_words_is_marked(self):
        en = {"S1": "The ferry discount was offered on 3 harbor routes in 2024. Weekday ferry trips on those routes rose 11 percent. "
                    "Each route kept its schedule."}
        for body in ("The ferry discount was offered on every route in the region [S1].",
                     "Weekday ferry trips rose 11 percent nationwide [S1]."):
            text, changes = self.mark(body, en)
            self.assertEqual(1, len(changes["scope_conflict"]), body)
        for body in ("Weekday ferry trips on the 3 discounted routes rose 11 percent [S1].",
                     "The discount did not cover all ferry routes [S1].", "All 3 harbor routes offered the ferry discount [S1]."):
            text, changes = self.mark(body, en)
            self.assertEqual([], changes["scope_conflict"], body)
        ko = {"S1": "교통공사는 2024년 도심 5개 역에 승강장 안전문을 새로 달았다. 해당 역의 추락 사고는 연 6건에서 1건으로 줄었다."}
        text, changes = self.mark("전국 모든 역의 추락 사고가 연 6건에서 1건으로 줄었다 [S1].", ko, "ko")
        self.assertEqual(1, len(changes["scope_conflict"]))
        for body in ("도심 5개 역의 추락 사고가 연 6건에서 1건으로 줄었다 [S1].", "안전문은 모든 역에 달리지는 않았다 [S1]."):
            text, changes = self.mark(body, ko, "ko")
            self.assertEqual([], changes["scope_conflict"], body)

    def test_effect_verb_against_hedge_and_null_result_flip_are_marked(self):
        en = {"S1": "Graffiti reports near the mural walls fell 15 percent, but the city could not rule out a change in reporting habits. "
                    "Shop vacancy on the mural streets did not change."}
        for body, kind in (("The murals reduced graffiti reports near the walls by 15 percent [S1].", "causal_conflict"),
                           ("Shop vacancy on the mural streets fell after the murals [S1].", "negation_conflict")):
            text, changes = self.mark(body, en)
            self.assertEqual(1, len(changes[kind]), body)
        for body in ("Graffiti reports near the mural walls fell 15 percent [S1].",
                     "Shop vacancy on the mural streets stayed the same [S1]."):
            text, _ = self.mark(body, en)
            self.assertNotIn("(source mismatch)", text, body)
        ko = {"S1": "급식 개편 뒤 잔반량은 하루 120kg에서 85kg으로 줄었다. 학교는 같은 시기 배식량도 줄여 급식 개편 효과를 따로 분리하지 못했다. "
                    "학생 만족도는 조금 올랐지만 차이는 통계적으로 유의하지 않았다. 급식 개편 뒤 결식률은 달라지지 않았다."}
        for body, kind in (("급식 개편이 잔반량을 하루 120kg에서 85kg으로 줄였다 [S1].", "causal_conflict"),
                           ("학생 만족도가 뚜렷하게 올랐다 [S1].", "negation_conflict"),
                           ("급식 개편 뒤 결식률이 줄었다 [S1].", "negation_conflict")):
            text, changes = self.mark(body, ko, "ko")
            self.assertEqual(1, len(changes[kind]), body)
        for body in ("급식 개편 뒤 잔반량은 하루 120kg에서 85kg으로 줄었다 [S1].", "학생 만족도는 조금 올랐다 [S1].",
                     "결식률은 그대로였다 [S1]."):
            text, _ = self.mark(body, ko, "ko")
            self.assertNotIn("(출처 불일치)", text, body)

    def test_time_abbreviation_does_not_split_sentence(self):
        en = {"S1": "Clinics moved opening time from 9 a.m. to 8 a.m. in May. Weekend hours did not change."}
        text, changes = self.mark("Clinics now open at 8 a.m. on weekdays [S1].", en)
        self.assertIn("Clinics now open at 8 a.m. on weekdays [S1].", text)
        self.assertEqual([], changes["no_source"])
        text, _ = self.mark("Clinics now open at 7 a.m. [S1].", en)
        self.assertIn("at 7 a.m. (source mismatch) [S1].", text)
        text, _ = self.mark("Clinics open at 8 a.m. Staff arrive earlier.", en)
        self.assertIn("at 8 a.m. (no source) Staff", text)

    def test_month_range_and_thousands_comma_do_not_cause_false_marks(self):
        ko = {"S1": "점검은 3월과 4월 두 달 동안만 이뤄졌다. 2025년 운전자 2,310명 가운데 41%가 속도를 줄였다고 답했다. "
                    "보행자는 27%가 길을 돌아갔다고 답했다."}
        for body in ("점검은 3~4월 두 달에 한정됐다 [S1].", "운전자의 41%가 속도를 줄였다 [S1]."):
            text, _ = self.mark(body, ko, "ko")
            self.assertNotIn("(출처 불일치)", text, body)
        text, changes = self.mark("보행자의 41%가 속도를 줄였다 [S1].", ko, "ko")
        self.assertEqual(1, len(changes["subject_conflict"]))

    def test_negation_flip_with_source_words_is_marked(self):
        en = {"S1": "The extension did not reduce daytime visits at the four branches. Evening security incidents were not "
                    "higher than before the change. Retail jobs were not lost, and retail employment was flat."}
        for body in ("The extension reduced daytime visits at the four branches [S1].",
                     "Evening security incidents were higher than before the change [S1]."):
            text, changes = self.mark(body, en)
            self.assertIn("(source mismatch)", text, body)
            self.assertEqual(1, len(changes["negation_conflict"]), body)
        for body in ("Daytime visits at the four branches were not reduced by the extension [S1].",
                     "Retail employment stayed flat [S1]."):
            text, changes = self.mark(body, en)
            self.assertEqual([], changes["negation_conflict"], body)
        ko = {"S1": "같은 기간 70세 이상 보행자 교통사고는 줄지 않았다. 설문은 복지관 이용자만 대상으로 했다."}
        text, changes = self.mark("같은 기간 70세 이상 보행자 교통사고는 줄었다 [S1].", ko, "ko")
        self.assertEqual(1, len(changes["negation_conflict"]))
        for body in ("같은 기간 70세 이상 보행자 교통사고는 줄지 않았다 [S1].",
                     "설문은 복지관 이용자만 대상으로 해 전체 고령자를 대표하지 않는다 [S1]."):
            text, changes = self.mark(body, ko, "ko")
            self.assertEqual([], changes["negation_conflict"], body)

    def test_share_overclaim_most_or_all_is_marked(self):
        en = {"S1": "After the repair, 3 of the 8 sites met the state swimming standard on every sampled week. "
                    "Hours were extended at four of its eleven branches. 23 percent of households in the two counties lacked a fast connection."}
        for body in ("Most sampling sites met the state swimming standard after the repair [S1].",
                     "Hours were extended at all eleven branches [S1].",
                     "Most households in the two counties lacked a fast connection [S1]."):
            text, changes = self.mark(body, en)
            self.assertEqual(1, len(changes["share_conflict"]), body)
        for body in ("After the repair, 3 of 8 sites met the swimming standard every sampled week [S1].",
                     "Nearly a quarter of households in the two counties lacked a fast connection [S1]."):
            text, changes = self.mark(body, en)
            self.assertEqual([], changes["share_conflict"], body)
        ko = {"S1": "조사 대상 12개 동 가운데 5개 동에서 야간 소음이 기준치 55dB을 넘었다. 기준치를 넘은 5개 동은 모두 간선도로에 접해 있었다.",
              "S2": "응답 교사 75명 중 52명이 참여 학생의 수업 태도가 나아졌다고 답했다."}
        for body in ("조사한 동 대부분에서 야간 소음이 기준치를 넘었다 [S1].", "모든 교사가 참여 학생의 수업 태도가 나아졌다고 답했다 [S2]."):
            text, changes = self.mark(body, ko, "ko")
            self.assertEqual(1, len(changes["share_conflict"]), body)
        text, changes = self.mark("기준치를 넘은 동은 모두 간선도로에 접해 있었다 [S1].", ko, "ko")
        self.assertEqual([], changes["share_conflict"])

    def test_derived_values_and_converted_units_are_read(self):
        # 2026-10-10 7회차: 범위 앞 값의 단위, 넓이·온도·전력량 낱말 단위, 차·곱·기간당 평균·증감률을 계산 값으로 읽는다.
        en = {"S1": "Average ferry speeds rose from 18 to 24 kilometers per hour. The 3,000 square meter plaza cost 250 dollars "
                    "per square meter. Wait times fell from 40 minutes to 30 minutes. Water temperatures rose by 4 degrees "
                    "Fahrenheit. Annual pumping energy fell from 52 gigawatt-hours to 40 gigawatt-hours. Ridership was 73,000 "
                    "trips in 2024."}
        for body in ("Ferries sped up by about 6 km/h [S1].", "The plaza covered 0.3 hectares [S1].",
                     "The plaza cost about 750,000 dollars in total [S1].", "Wait times fell by 25 percent [S1].",
                     "Water temperatures rose by about 2.2 degrees Celsius [S1].", "Ridership averaged about 200 trips a day [S1]."):
            text, changes = self.mark(body, en)
            self.assertNotIn("(source mismatch)", text, body)
        for body in ("Average ferry speeds rose from 18 to 24 miles per hour [S1].",
                     "Water temperatures rose by 4 degrees Celsius [S1].",
                     "Annual pumping energy fell from 52 megawatt-hours to 40 megawatt-hours [S1].",
                     "The plaza covered 3 hectares [S1]."):
            text, changes = self.mark(body, en)
            self.assertIn("(source mismatch)", text, body)
        ko = {"S1": "체험관 신규 회원은 두 달 동안 2만 4,000명이었다. 생태공원은 2만 5,000㎡이다. 놀이터 바닥은 화씨 10도 낮았다. "
                    "야간 개방 구역에 체육관은 포함되지 않았다."}
        for body in ("한 달에 약 1만 2,000명이 새로 가입했다 [S1].", "생태공원 면적은 2.5헥타르다 [S1].", "놀이터 바닥은 섭씨 약 5.6도 낮았다 [S1].",
                     "야간 개방 구역에서 체육관은 빠졌다 [S1]."):
            text, changes = self.mark(body, ko, "ko")
            self.assertNotIn("(출처 불일치)", text, body)
        text, changes = self.mark("놀이터 바닥은 섭씨 10도 낮았다 [S1].", ko, "ko")
        self.assertIn("(출처 불일치)", text)

    def test_transition_and_comparison_swaps_are_marked(self):
        # 2026-10-10 7회차: 원문 두 값의 전후 순서만 바꾸거나 비교 기준('…보다'·'than …')만 바꾼 문장.
        en = {"S1": "The shelter housed 840 people in 2025, up from 610 in 2024. Average stays fell from 19 nights to 12 nights. "
                    "Night-shift staff worked longer hours than day-shift staff."}
        for body in ("The shelter population fell from 840 to 610 [S1].", "Average stays rose from 12 nights to 19 nights [S1].",
                     "Day-shift staff worked longer hours than night-shift staff [S1]."):
            text, changes = self.mark(body, en)
            self.assertEqual(1, len(changes["antonym_conflict"]), body)
        for body in ("The shelter population rose from 610 to 840 [S1].", "Average stays fell from 19 to 12 nights [S1].",
                     "Night-shift staff worked longer hours than day-shift staff [S1]."):
            text, changes = self.mark(body, en)
            self.assertEqual([], changes["antonym_conflict"], body)
        ko = {"S1": "도서관 야간 이용자는 하루 평균 120명에서 180명으로 늘었다. 평일 대출은 주말보다 30% 많았다. 신축 건물의 관리비는 구관보다 15% 적었다."}
        for body in ("도서관 야간 이용자는 하루 평균 180명에서 120명으로 줄었다 [S1].", "주말 대출은 평일보다 30% 많았다 [S1].",
                     "신축 건물의 관리비는 구관보다 15% 많았다 [S1]."):
            text, changes = self.mark(body, ko, "ko")
            self.assertEqual(1, len(changes["antonym_conflict"]), body)
        for body in ("도서관 야간 이용자는 하루 평균 120명에서 180명으로 늘었다 [S1].", "평일 대출은 주말보다 30% 많았다 [S1]."):
            text, changes = self.mark(body, ko, "ko")
            self.assertEqual([], changes["antonym_conflict"], body)

    def test_month_span_from_date_range_is_read(self):
        # 백로그(7회차): "10개월"을 "10개"로 읽고, 원문 달 범위에서 센 기간·달 평균을 계산 값으로 보지 못하던 결함.
        ko = {"S1": "방문 간호는 2025년 4월부터 9월까지 어르신 300명을 4,800회 방문했다."}
        text, changes = self.mark("방문 간호는 6개월 동안 한 달 평균 약 800회 방문했다 [S1].", ko, "ko")
        self.assertNotIn("(출처 불일치)", text)
        text, changes = self.mark("방문 간호는 8개월 동안 방문했다 [S1].", ko, "ko")
        self.assertIn("(출처 불일치)", text)

    def test_span_total_restated_per_period_is_marked(self):
        # 9회차(holdout4 기간 바꿈): 수치 절에 기간 낱말이 없고 문장이 기간 길이("first twelve months")만 밝힌 합계를 '한 달에'로 말한 문장.
        en = {"S1": "In the first twelve months, the utility sent 1,120 leak alerts. Over three months, crews fixed 90 hydrants."}
        text, changes = self.mark("The utility issued 1,120 alerts per month during the pilot [S1].", en)
        self.assertEqual(1, len(changes["period_conflict"]))
        for body in ("The utility sent 1,120 alerts a year [S1].", "The utility sent 1,120 alerts in total [S1].",
                     "Crews fixed 90 hydrants in total [S1]."):
            text, changes = self.mark(body, en)
            self.assertEqual([], changes["period_conflict"], body)
        text, changes = self.mark("Crews fixed 90 hydrants a month [S1].", en)
        self.assertEqual(1, len(changes["period_conflict"]))
        ko = {"S1": "시범 기간 중 대여 건수는 18,400건이었다. 첫 6개월 동안 민원은 240건 접수됐다."}
        for body in ("하루 평균 대여는 18,400건이었다 [S1].", "민원은 한 달에 240건 접수됐다 [S1]."):
            text, changes = self.mark(body, ko, "ko")
            self.assertEqual(1, len(changes["period_conflict"]), body)
        text, changes = self.mark("민원은 6개월 동안 240건 접수됐다 [S1].", ko, "ko")
        self.assertEqual([], changes["period_conflict"])

    def test_value_comparison_flip_is_marked(self):
        # 9회차(holdout4 비교 뒤집기): 원문 한 문장이 두 대상 값을 말하는데 주장이 크기 비교를 뒤집은 문장.
        en = {"S1": "A resident survey of 600 households found 58 percent supported continuing the program, while 21 percent opposed it."}
        text, changes = self.mark("Opposition outweighed support in the household survey [S1].", en)
        self.assertEqual(1, len(changes["antonym_conflict"]))
        for body in ("Support outweighed opposition in the household survey [S1].",
                     "More households supported the program than opposed it [S1]."):
            text, changes = self.mark(body, en)
            self.assertEqual([], changes["antonym_conflict"], body)
        ko = {"S1": "이용자 600명 조사에서 71%가 외로움이 줄었다고 답했지만, 19%는 기계 음성이 불편하다고 답했다."}
        text, changes = self.mark("외로움이 줄었다고 답한 비율보다 기계 음성이 불편하다고 답한 비율이 더 높았다 [S1].", ko, "ko")
        self.assertEqual(1, len(changes["antonym_conflict"]))
        for body in ("기계 음성이 불편하다고 답한 비율보다 외로움이 줄었다고 답한 비율이 더 높았다 [S1].",
                     "외로움이 줄었다는 응답이 기계 음성이 불편하다는 응답보다 많았다 [S1]."):
            text, changes = self.mark(body, ko, "ko")
            self.assertEqual([], changes["antonym_conflict"], body)

    def test_korean_month_followed_by_count_is_not_a_date(self):
        # 9회차(holdout5): "2025년 2월 120곳"의 "2월 12"를 날짜로 읽어 원문 수치가 사라지고, 맞는 차(90곳)와 연월이 표시되던 결함.
        ko = {"S1": "개방 화장실은 2025년 2월 120곳에서 2026년 6월 210곳으로 늘었다."}
        text, changes = self.mark("개방 화장실은 2025년 2월과 비교해 90곳, 비율로는 75% 늘었다 [S1].", ko, "ko")
        self.assertNotIn("(출처 불일치)", text)
        text, changes = self.mark("개방 화장실은 2025년 2월 150곳이었다 [S1].", ko, "ko")
        self.assertIn("(출처 불일치)", text)

    def test_bare_numbers_after_a_unit_value_and_exact_ratios(self):
        # 9회차(holdout5): 단위를 앞 값에만 붙인 "from 38 to 29", 원문 두 금액의 배수 "1.6배"는 원문에서 온 값.
        en = {"S1": "Radar counts showed the 85th-percentile speed falling from 38 km/h before installation to 29 km/h after."}
        text, changes = self.mark("The 85th-percentile speed fell by 9 km/h, from 38 to 29 [S1].", en)
        self.assertNotIn("(source mismatch)", text)
        text, changes = self.mark("Speeds dropped from 38 mph to 29 mph [S1].", en)
        self.assertIn("(source mismatch)", text)
        ko = {"S1": "친환경 제설제의 톤당 가격은 48만 원으로 염화칼슘(톤당 30만 원)보다 비쌌다."}
        text, changes = self.mark("친환경 제설제는 톤당 18만 원 더 비싸 염화칼슘의 1.6배 가격이다 [S1].", ko, "ko")
        self.assertNotIn("(출처 불일치)", text)
        text, changes = self.mark("친환경 제설제는 염화칼슘의 2.6배 가격이다 [S1].", ko, "ko")
        self.assertIn("(출처 불일치)", text)

    def test_comparison_reference_and_inline_flips(self):
        # 9회차(holdout5): 원문이 '…보다'로 비교한 기준·방향을 뒤집은 문장, 주장 스스로 두 값을 반대로 비교한 문장, '-er than' 비교 낱말.
        ko = {"S1": "이용 경험자 중 청결 만족도는 72%로, 시 직영 공중화장실 만족도 61%보다 높았다. "
                    "다만 70대 이상 응답자는 이용 경험이 23%로, 40~50대(61%)보다 낮았다. 시범 구간 피해율은 6%였고 일반 구간은 11%였다."}
        for body in ("이용자의 청결 만족도는 직영 공중화장실보다 민간 개방화장실 쪽이 낮았다 [S1].",
                     "70대 이상 응답자의 이용 경험은 40~50대보다 높았다 [S1].",
                     "시범 구간의 피해율은 6%로 일반 구간 11%보다 높았다 [S1]."):
            text, changes = self.mark(body, ko, "ko")
            self.assertEqual(1, len(changes["antonym_conflict"]), body)
        for body in ("이용자의 청결 만족도는 직영 공중화장실보다 민간 개방화장실 쪽이 높았다 [S1].",
                     "70대 이상 응답자의 이용 경험은 40~50대보다 낮았다 [S1].",
                     "시범 구간의 피해율은 6%로 일반 구간 11%보다 낮았다 [S1]."):
            text, changes = self.mark(body, ko, "ko")
            self.assertEqual([], changes["antonym_conflict"], body)
        en = {"S1": "Fountains at transit stops dispensed more water on average than fountains in parks. "
                    "The division cautioned that summer 2026 was drier than 2025. Lower-income buyers received $1,200 and others $500."}
        for body in ("Park fountains dispensed more water on average than those at transit stops [S1].",
                     "Summer 2026 was wetter than 2025 [S1]."):
            text, changes = self.mark(body, en)
            self.assertEqual(1, len(changes["antonym_conflict"]), body)
        for body in ("Transit-stop fountains dispensed more water on average than park fountains [S1].",
                     "Summer 2026 was drier than 2025 [S1].", "Lower-income buyers received $1,200 rather than $500 [S1]."):
            text, changes = self.mark(body, en)
            self.assertEqual([], changes["antonym_conflict"], body)
