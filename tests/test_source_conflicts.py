import unittest

from hprc.verification import mark_report_claims, note_source_conflicts


SRC = {"S1": "시 교통국 자료에 따르면 도심 버스 이용 건수는 4월에 8% 증가했다.",
       "S2": "운수 노조 집계에 따르면 도심 버스 이용 건수는 4월에 3% 감소했다.",
       "S3": "주차 요금은 동결됐다."}
KO = ("## 답\n도심 버스 이용 건수는 4월에 8% 증가했다 [S1].\n\n"
      "## 근거\n- 도심 버스 이용 건수는 4월에 3% 감소했다 [S2].\n- 주차 요금은 동결됐다 [S3].\n\n"
      "## 반대 근거와 한계\n- 주차 요금은 동결됐다 [S3].\n\n## 다음 행동\n- 원자료를 찾는다 (판단)\n\n## 출처\n- [S1] a\n- [S2] b\n- [S3] c\n")


class SourceConflictTests(unittest.TestCase):
    def test_opposite_directions_from_different_sources_are_noted_in_limits(self):
        text, pairs = note_source_conflicts(KO, SRC, "ko")
        self.assertEqual([["S1", "S2"]], pairs)
        limits = text.split("## 반대 근거와 한계\n", 1)[1].split("\n\n## 다음 행동", 1)[0]
        self.assertIn("출처끼리 상충: S1·S2를", limits)
        self.assertTrue(limits.rstrip().endswith("(판단)."))
        self.assertNotIn("(출처 불일치)", text)   # 본문 문장에는 표시하지 않는다

    def test_idempotent_and_survives_claim_marking(self):
        text, _ = note_source_conflicts(KO, SRC, "ko")
        self.assertEqual((text, []), note_source_conflicts(text, SRC, "ko"))
        marked, changes = mark_report_claims(text, SRC, "ko")
        self.assertEqual(text, marked)          # 덧붙인 줄은 (출처 없음)·(출처 불일치) 표시를 부르지 않는다
        self.assertFalse(changes["no_source"] or changes["mismatch"])

    def test_limits_already_discussing_both_sources_is_left_alone(self):
        report = KO.replace("- 주차 요금은 동결됐다 [S3].\n\n## 다음", "- S1과 S2의 집계가 다르다 (판단).\n\n## 다음")
        self.assertEqual((report, []), note_source_conflicts(report, SRC, "ko"))

    def test_separate_unrelated_mentions_of_each_source_do_not_count(self):
        # PR #15 리뷰: 한계 절에서 S1·S2가 따로따로 다른 한계로 언급된 것은 상충을 다룬 것이 아니다.
        report = KO.replace("- 주차 요금은 동결됐다 [S3].\n\n## 다음",
                            "- S1의 주차 자료는 4월만 다룬다 (판단).\n- S2의 표본은 작다 (판단).\n\n## 다음")
        text, pairs = note_source_conflicts(report, SRC, "ko")
        self.assertEqual([["S1", "S2"]], pairs)
        self.assertIn("출처끼리 상충", text)

    def test_same_source_unrelated_subject_or_no_limits_section_is_left_alone(self):
        src = {"S1": "버스 이용 건수는 8% 증가했다. 주차장 이용 대수는 3% 감소했다."}
        report = "## 답\n버스 이용 건수는 8% 증가했다 [S1]. 주차장 이용 대수는 3% 감소했다 [S1].\n\n## 한계\n- 표본이 작다 (판단).\n"
        self.assertEqual((report, []), note_source_conflicts(report, src, "ko"))
        src = {"S1": "Bus ridership rose 8 percent.", "S2": "Parking fees fell 3 percent."}
        report = "## Answer\nBus ridership rose 8 percent [S1]. Parking fees fell 3 percent [S2].\n\n## Limits\n- Small sample (judgment).\n"
        self.assertEqual([], note_source_conflicts(report, src, "en")[1])
        self.assertEqual([], note_source_conflicts(KO.split("## 반대 근거와 한계")[0], SRC, "ko")[1])

    def test_english_row(self):
        src = {"S1": "Downtown bus ridership rose 8 percent in April.", "S2": "Downtown bus ridership fell 3 percent in April."}
        report = ("## Answer\nDowntown bus ridership rose 8 percent in April [S1]. Downtown bus ridership fell 3 percent in April [S2].\n\n"
                  "## Counter-evidence and limits\n- Small sample (judgment).\n\n## Sources\n- [S1] a\n- [S2] b\n")
        text, pairs = note_source_conflicts(report, src, "en")
        self.assertEqual([["S1", "S2"]], pairs)
        self.assertIn("- Sources disagree: sentences citing S1 and S2", text)
        self.assertEqual(text, mark_report_claims(text, src, "en")[0])


    BIKE = {"S1": "시 보고서에 따르면 2025년 공공자전거 대여 건수는 전년보다 8% 증가했다.",
            "S2": "운영사 요약에 따르면 2025년 공공자전거 대여 건수는 전년보다 31% 증가했다."}

    def bike(self, s2_value: str, limits: str = "- 표본이 작다 (판단).") -> str:
        return ("## 답\n2025년 공공자전거 대여 건수는 전년보다 8% 증가했다 [S1]. "
                f"2025년 공공자전거 대여 건수는 전년보다 {s2_value} 증가했다 [S2].\n\n"
                f"## 반대 근거와 한계\n{limits}\n\n## 출처\n- [S1] a\n- [S2] b\n")

    def test_same_direction_with_large_magnitude_gap_is_noted(self):
        text, pairs = note_source_conflicts(self.bike("31%"), self.BIKE, "ko")
        self.assertEqual([["S1", "S2"]], pairs)
        self.assertIn("- 출처끼리 증감 폭이 크게 다름: S1·S2를 인용한 문장이 같은 대상의 증감 폭을 8%·31%로 말하므로", text)
        self.assertEqual((text, []), note_source_conflicts(text, self.BIKE, "ko"))   # 다시 돌려도 같다
        self.assertEqual(text, mark_report_claims(text, self.BIKE, "ko")[0])

    def test_small_gap_or_acknowledged_gap_is_left_alone(self):
        src = dict(self.BIKE, S2=self.BIKE["S2"].replace("31%", "12%"))
        self.assertEqual([], note_source_conflicts(self.bike("12%"), src, "ko")[1])   # 2배 미만
        report = self.bike("31%", "- S1은 거치형만, S2는 전기자전거까지 센다 (판단).")
        self.assertEqual((report, []), note_source_conflicts(report, self.BIKE, "ko"))
        src = dict(self.BIKE, S2=self.BIKE["S2"].replace("31%", "31%포인트"))
        self.assertEqual([], note_source_conflicts(self.bike("31%포인트"), src, "ko")[1])   # 퍼센트와 퍼센트포인트는 비교하지 않는다

    def test_english_magnitude_row(self):
        src = {"S1": "Bike-share trips increased 8 percent in 2025.", "S2": "Bike-share trips increased 31 percent in 2025."}
        report = ("## Answer\nBike-share trips increased 8 percent in 2025 [S1]. Bike-share trips increased 31 percent in 2025 [S2].\n\n"
                  "## Limits\n- Small sample (judgment).\n")
        text, pairs = note_source_conflicts(report, src, "en")
        self.assertEqual([["S1", "S2"]], pairs)
        self.assertIn("- Sources differ in size: sentences citing S1 and S2 give 8% and 31% for the same subject's change", text)


if __name__ == "__main__":
    unittest.main()
