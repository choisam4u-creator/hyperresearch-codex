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
        for body, lang in (("대조군이 없어 효과 크기를 확정할 수 없다 [S1].", "ko"),
                           ("Most opponents of the project had moved away before residents were polled [S2].", "en")):
            text, changes = self.mark(body, src, lang)
            self.assertIn("불일치" if lang == "ko" else "mismatch", text, body)
            self.assertEqual(1, len(changes["wording_conflict"]), body)
        for body, lang in (("담당자는 대조군을 두지 않았다 [S1].", "ko"), ("사고 건수가 적어 유의성은 검정하지 않았다 [S1].", "ko"),
                           ("설문은 자발 참여라 사업 지지 주민이 많이 응답했을 수 있다 [S2].", "ko"),
                           ("The voluntary survey may over-represent residents who supported the project [S2].", "en"),
                           ("The department kept no control group [S1].", "en"),
                           ("보고서에 따르면 담당자는 대조군을 두지 않았다 [S1].", "ko"),
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
