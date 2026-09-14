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


class ClaimEvidenceSupplementTests(unittest.TestCase):
    def test_supplement_preserves_existing_context_and_source_sentences(self):
        import json
        from pathlib import Path
        case = next(c for c in json.loads((Path(__file__).parent/'fixtures/realistic_inputs.json').read_text())['cases'] if c['id']=='real-en-long')
        body = case['sources']['S2']
        claim = 'Staff logged 58 corrections: 21 after a sick call, 17 after a late-opening program, 12 after a ticket-printer restart, and 8 free-text descriptions.'
        before, _ = select(body, case['prompt'], 5000)
        after, clipped = select(body, case['prompt'], 5000, evidence_queries=(claim,))
        self.assertNotIn('21 followed a sick call', before)
        self.assertIn('21 followed a sick call', after)
        self.assertIn('excluded from the matching calculation', after)
        self.assertLessEqual(len(after), 5000)
        self.assertTrue(clipped)
        # 기존 발췌는 생략 표식만 제외하고 모두 그대로 남아야 한다.
        before_content = before.rsplit('\n\n[… 관련도 낮은',1)[0]
        for fragment in before_content.split('\n\n[…]\n\n'):
            self.assertIn(fragment, after)
        for fragment in after.rsplit('\n\n[… 관련도 낮은',1)[0].split('\n\n[…]\n\n'):
            self.assertIn(fragment, body)

    def test_irrelevant_claim_or_full_source_does_not_inject_claim_text(self):
        body = 'Original documented observation.\n\n' + 'Background description. ' * 100
        normal = select(body, 'documented observation', 300)
        self.assertEqual(normal, select(body, 'documented observation', 300, evidence_queries=('fabricated Jupiter unicorn',)))
        self.assertEqual(('short source',False),select('short source','query',100,evidence_queries=('invented assertion',)))

    def test_supplement_is_bounded_for_small_caps(self):
        body = 'intro ' * 30 + '\n\nMeasured capacity reached 31 units. Conditions exclude reserve units.\n\n' + 'background ' * 100
        for cap in (0,1,40,80,160,300):
            result, _ = select(body,'intro',cap,evidence_queries=('Measured capacity 31 units',))
            self.assertLessEqual(len(result),cap)

    def test_supplement_keeps_adjacent_condition_atomically(self):
        body = ('Overview of the evaluation.\n\n' + ('Alpha methodology and background. ' * 7)
                + '\n\nMeasured capacity reached 31 units. This applies only when cooling is enabled. It is not valid above 30 degrees. '
                + ('Unrelated archival background discussion. ' * 15))
        for cap in (370, 500):
            with self.subTest(cap=cap):
                result, _ = select(body, 'Alpha methodology', cap,
                                   evidence_queries=('Measured capacity reached 31 units',))
                if 'Measured capacity reached 31 units.' in result:
                    self.assertIn('This applies only when cooling is enabled.', result)
                    self.assertIn('It is not valid above 30 degrees.', result)
                self.assertLessEqual(len(result), cap)
        result, _ = select(body, 'Alpha methodology', 500,
                           evidence_queries=('Measured capacity reached 31 units',))
        self.assertIn('Measured capacity reached 31 units.', result)

    def test_condition_chain_crosses_internal_chunk_boundary(self):
        body = ('Overview of the evaluation.\n\n' + ('Alpha methodology and background. ' * 7)
                + '\n\n' + 'Archival records were retained. ' * 5
                + 'Measured capacity reached 31 units. This applies only when cooling is enabled. '
                + 'It is not valid above 30 degrees. ' + 'Unrelated archival background discussion. ' * 15)
        result, _ = select(body, 'Alpha methodology', 500,
                           evidence_queries=('Measured capacity reached 31 units',), supplemental_cap=1000)
        self.assertIn('Measured capacity reached 31 units.', result)
        self.assertIn('This applies only when cooling is enabled.', result)
        self.assertIn('It is not valid above 30 degrees.', result)
        self.assertLessEqual(len(result), 1000)


if __name__ == "__main__":
    unittest.main()
