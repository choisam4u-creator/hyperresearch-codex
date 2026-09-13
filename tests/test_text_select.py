import unittest

from hprc.text_select import paragraphs, select


class TextSelectTests(unittest.TestCase):
    def test_long_table_keeps_header_unit_and_exception_with_relevant_row(self):
        rows = [f"| metric-{index} | {index} ms | ordinary |" for index in range(45)]
        rows[31] = "| critical-latency | 240 ms | low-power only |"
        body = (
            "Overview of the benchmark.\n\n"
            "Condition: values apply to low-power mode only.\n"
            "| metric | unit | scope |\n| --- | --- | --- |\n" + "\n".join(rows) +
            "\nException: high-performance mode is excluded.\n\n"
            + "Unrelated appendix. " * 100
        )
        selected, truncated = select(body, "critical-latency 240 ms", 650)
        self.assertTrue(truncated)
        self.assertLessEqual(len(selected), 650)
        self.assertIn("| metric | unit | scope |", selected)
        self.assertIn("critical-latency | 240 ms", selected)
        self.assertIn("Condition: values apply to low-power mode only.", selected)
        self.assertIn("Exception: high-performance mode is excluded.", selected)

    def test_condition_neighbor_is_kept_when_it_fits(self):
        body = ("Intro. " * 40 + "\n\n" +
                "Measured latency is 2 seconds in the test fixture.\n\n" +
                "Exception: the result does not apply when caching is disabled.\n\n" +
                "Appendix. " * 100)
        selected, _ = select(body, "measured latency test fixture", 520)
        self.assertLessEqual(len(selected), 520)
        self.assertIn("Measured latency is 2 seconds", selected)
        self.assertIn("Exception: the result does not apply", selected)

    def test_multilingual_no_overlap_fallback_is_substantive_and_bounded(self):
        body = ("Short title.\n\n" +
                "This English paragraph gives enough detail about the source material and its limitations. " * 3 + "\n\n" +
                "A second English paragraph records a condition and an exception for readers. " * 3)
        selected, truncated = select(body, "한국어 질의와 영어 본문 사이에 겹치는 낱말이 없음", 360)
        self.assertTrue(truncated)
        self.assertLessEqual(len(selected), 360)
        self.assertIn("This English paragraph", selected)
        self.assertIn("생략", selected)

    def test_tiny_and_zero_caps_remain_bounded(self):
        for cap in (0, 1, 12, 40):
            selected, truncated = select("long body " * 100, "query", cap)
            self.assertTrue(truncated)
            self.assertLessEqual(len(selected), cap)

    def test_short_body_is_unchanged(self):
        body = "짧은 원문"
        self.assertEqual((body, False), select(body, "질의", 100))

    def test_paragraphs_split_long_table_without_orphaning_header(self):
        body = "| item | unit |\n| --- | --- |\n" + "\n".join(f"| row-{i} | {i} ms |" for i in range(50))
        chunks = paragraphs(body, 220)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all("| item | unit |" in chunk and "| --- | --- |" in chunk for chunk in chunks))

    def test_single_oversized_table_row_never_creates_headerless_fragments(self):
        long_row = "| payload | " + ("ordinary-data " * 45) + "critical-tail-value |"
        body = "Condition: values use milliseconds.\n| item | unit |\n| --- | --- |\n" + long_row
        chunks = paragraphs(body, 220)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 220 for chunk in chunks))
        self.assertTrue(all("| item | unit |" in chunk and "| --- | --- |" in chunk for chunk in chunks))
        selected, _ = select(body + "\n\n" + "appendix " * 100, "critical-tail-value", 500)
        self.assertLessEqual(len(selected), 500)
        self.assertIn("| item | unit |", selected)
        self.assertIn("critical-tail-value", selected)

    def test_oversized_table_context_omits_row_without_emitting_headerless_text(self):
        body = (("Condition text " * 40) + "\n| item | unit |\n| --- | --- |\n| payload | " +
                ("very-long-value " * 40) + "|")
        chunks = paragraphs(body, 120)
        self.assertEqual(["| item | unit |\n| --- | --- |"], chunks)


if __name__ == "__main__":
    unittest.main()
