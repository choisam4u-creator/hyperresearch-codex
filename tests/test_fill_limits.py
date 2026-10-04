import unittest

from hprc.gates import fill_empty_limits, judgment_sentences


EMPTY = "# 질문: q\n\n## 답\n답이다 [S1].\n\n## 반대 근거와 한계\n\n## 다음 행동\n- 더 찾는다\n"


class FillLimitsTests(unittest.TestCase):
    def test_empty_limits_section_gets_analysis_gaps_marked_as_judgment(self):
        text, rows = fill_empty_limits(EMPTY, ["대조군 자료가 없다."], [{"note": "S1과 S2의 감소율이 다르다", "claim_ids": ["C1"]}], "ko")
        self.assertEqual(2, rows)
        self.assertIn("- 분석 단계가 찾은 상충: S1과 S2의 감소율이 다르다. (판단)", text)
        self.assertIn("- 분석 단계가 남긴 근거 빈틈: 대조군 자료가 없다. (판단)", text)
        self.assertLess(text.index("근거 빈틈"), text.index("## 다음 행동"))
        self.assertEqual(2, judgment_sentences(text, "ko"))

    def test_no_gaps_states_review_needed_instead_of_claiming_no_limits(self):
        text, rows = fill_empty_limits(EMPTY, [], [], "ko")
        self.assertEqual(1, rows)
        self.assertIn("반대 근거가 없다는 뜻은 아니므로 검토가 필요하다. (판단)", text)

    def test_existing_content_and_missing_heading_are_left_alone(self):
        filled = EMPTY.replace("## 반대 근거와 한계\n", "## 반대 근거와 한계\n표본이 작다 [S1].\n")
        self.assertEqual((filled, 0), fill_empty_limits(filled, ["x"], [], "ko"))
        no_heading = "# 질문: q\n\n## 답\n답 [S1].\n"
        self.assertEqual((no_heading, 0), fill_empty_limits(no_heading, ["x"], [], "ko"))

    def test_trailing_empty_english_limits_and_row_cap(self):
        report = "# Question: q\n\n## Answer\nA [S1].\n\n## Limits\n"
        text, rows = fill_empty_limits(report, [f"gap {i}" for i in range(9)], [], "en")
        self.assertEqual(5, rows)
        self.assertTrue(text.rstrip().endswith("- Evidence gap left by analysis: gap 4. (judgment)"))
        self.assertEqual((text, 0), fill_empty_limits(text, ["gap"], [], "en"))


if __name__ == "__main__":
    unittest.main()
