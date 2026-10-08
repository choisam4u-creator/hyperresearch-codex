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
