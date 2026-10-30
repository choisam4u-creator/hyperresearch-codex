"""한국어 시각 양끝의 반(30분) 회귀시험."""
from decimal import Decimal
import unittest

from hprc.verification import _absent_values, _clock_spans, mark_report_claims


class ClockHalfTests(unittest.TestCase):
    def test_end_half_is_90_minutes(self):
        self.assertEqual([Decimal(5400)], _clock_spans("센터는 오후 7시부터 8시 반까지 운영한다."))

    def test_half_at_each_endpoint_for_existing_separators(self):
        for separator in ("부터", "~", "–", "-"):
            for start, end, minutes in (("7시", "8시 반", 90),
                                        ("7시 반", "8시", 30),
                                        ("7시 반", "8시 반", 60),
                                        ("7시 15분", "8시 반", 75),
                                        ("7시 반", "8시 45분", 75)):
                with self.subTest(separator=separator, start=start, end=end):
                    self.assertEqual([Decimal(minutes * 60)],
                                     _clock_spans(f"센터는 오후 {start}{separator}{end}까지 운영한다."))

    def test_half_preserves_overnight_and_morning_inference(self):
        for text, minutes in (("오후 11시 반~오전 1시", 90),
                              ("오전 9시 반부터 6시까지", 510),
                              ("오전 9시부터 6시 반까지", 570)):
            with self.subTest(text=text):
                self.assertEqual([Decimal(minutes * 60)], _clock_spans(text))

    def test_duration_words_do_not_become_clock_ranges(self):
        for text in ("센터는 2시간 반 운영한다.", "센터는 반나절 운영한다."):
            with self.subTest(text=text):
                self.assertEqual([], _clock_spans(text))

    def test_supported_and_wrong_durations_reach_report_marks(self):
        for span, correct, wrong in (("오후 7시부터 8시 반까지", "90분", "60분"),
                                      ("오후 7시 반~8시", "30분", "60분")):
            source = f"센터는 {span} 운영한다."
            with self.subTest(span=span):
                self.assertEqual([], _absent_values(f"센터는 {correct} 운영한다.", source))
                self.assertEqual([wrong], _absent_values(f"센터는 {wrong} 운영한다.", source))
                for duration, mismatch in ((correct, False), (wrong, True)):
                    body = f"센터는 {duration} 운영한다 [S1]."
                    report = f"# 질문: 운영 시간\n\n## 답\n{body}\n\n## 출처\n- [S1] 센터"
                    marked, changes = mark_report_claims(report, {"S1": source}, "ko")
                    self.assertEqual(int(mismatch), len(changes["mismatch"]))
                    self.assertEqual(mismatch, "(출처 불일치)" in marked)


if __name__ == "__main__":
    unittest.main()
