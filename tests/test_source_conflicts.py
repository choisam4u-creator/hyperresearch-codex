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


if __name__ == "__main__":
    unittest.main()
