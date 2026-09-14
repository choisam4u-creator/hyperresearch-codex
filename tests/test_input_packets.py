import json
import unittest

from hprc.input_packets import claims_evidence_packet, evidence_packet, inline_input_prompt, input_profile, make_packet, prepare_writer
from hprc.untrusted import wrap_source


class InputPacketTests(unittest.TestCase):
    def test_profile_is_utf8_based_and_keeps_no_body(self):
        inputs = {"b.md": "가", "a.md": "same", "copy.md": "same"}
        profile = input_profile(inputs)
        self.assertEqual("prepared_not_actual_tokens", profile["scope"])
        self.assertEqual(3, profile["files"]["b.md"]["bytes"])
        self.assertEqual(4 + 4 + 3, profile["total_bytes"])
        self.assertEqual(4, profile["within_call_exact_duplicate_bytes"])
        self.assertNotIn("body", profile["files"]["a.md"])
        self.assertEqual(64, len(profile["files"]["a.md"]["sha256"]))

    def test_profile_prior_match_uses_only_fingerprint_and_ignores_malformed_records(self):
        first = input_profile({"source.md": "same", "other.md": "old"})
        later = input_profile({"again.md": "same", "new.md": "new"}, [first, {"files": {"bad": {"bytes": "4"}}}])
        self.assertEqual(4, later["repeated_from_prior_bytes"])
        self.assertEqual(0, later["within_call_exact_duplicate_bytes"])

    def test_packet_is_deterministic_and_preserves_wrapped_source_metadata_and_negative_condition(self):
        source = wrap_source("published: 2026-09-14\nResult applies unless caching is disabled.", "https://example.test/a")
        inputs = {"S1-note.md": source, "question.txt": "What is the limit?"}
        first = make_packet(inputs)
        second = make_packet(dict(reversed(list(inputs.items()))))
        self.assertEqual(first, second)
        packet = first["_input_packet.md"]
        self.assertIn("## Virtual file: S1-note.md", packet)
        self.assertIn("## Virtual file: question.txt", packet)
        self.assertLess(packet.index("## Virtual file: S1-note.md"), packet.index("## Virtual file: question.txt"))
        self.assertIn(source, packet)
        self.assertIn("unless caching is disabled", packet)

    def test_packet_omits_audit_fingerprints_but_profile_retains_them(self):
        inputs = {"a.md": "first source", "b.md": "두 번째 source"}
        packet = make_packet(inputs)["_input_packet.md"]
        profile = input_profile(inputs)
        self.assertNotIn("<!-- utf8_bytes=", packet)
        for name, body in inputs.items():
            self.assertIn(f"## Virtual file: {name}\n{body}\n<!-- End virtual file: {name} -->", packet)
            self.assertEqual(len(body.encode("utf-8")), profile["files"][name]["bytes"])
            self.assertEqual(64, len(profile["files"][name]["sha256"]))

    def test_inline_prompt_preserves_same_virtual_files_without_shell_contract_loss(self):
        source = wrap_source("Condition remains unless caching is disabled.", "https://example.test/a")
        inputs = {"S1-note.md": source, "question.txt": "What is the limit?"}
        inline = inline_input_prompt(inputs)
        self.assertIn("INLINE INPUT CONTRACT", inline)
        self.assertIn("Do not use shell commands", inline)
        self.assertIn("## Virtual file: S1-note.md", inline)
        self.assertIn("## Virtual file: question.txt", inline)
        self.assertIn(source, inline)

    def test_supplemental_selection_is_recorded_and_bound(self):
        body = 'Measured capacity reached 31 units. Only valid with cooling.'
        first = claims_evidence_packet(body, ['overview'], 500,
                                       supplemental_queries=(' capacity  31 ', 'capacity 31'))
        second = claims_evidence_packet(body, ['overview'], 500,
                                        supplemental_queries=('capacity 32',))
        self.assertEqual(['capacity 31'], first['supplemental_queries'])
        self.assertNotEqual(first['selection_queries_sha256'], second['selection_queries_sha256'])
        self.assertEqual('supplemental', first['claim_coverage'][1]['query_kind'])
        self.assertEqual('capacity 31', first['claim_coverage'][1]['query'])
        self.assertTrue(first['claim_coverage'][1]['candidate_exact_spans'])

    def test_packet_rejects_ambiguous_filename_and_non_string_body(self):
        with self.assertRaises(ValueError):
            make_packet({"bad\nname": "body"})
        with self.assertRaises(TypeError):
            input_profile({"a.md": 3})

    def test_prepare_writer_removes_digest_only_for_complete_claim_structure(self):
        claims = json.dumps({"claims": [], "contradictions": [], "gaps": []})
        inputs = {"claims.json": claims, "_digest.md": "# 주장 요약", "_independence.md": "clusters", "S1-note.md": "source metadata"}
        prepared = prepare_writer(inputs)
        self.assertNotIn("_digest.md", prepared)
        self.assertEqual(claims, prepared["claims.json"])
        self.assertEqual("source metadata", prepared["S1-note.md"])
        malformed = prepare_writer({"claims.json": "{}", "_digest.md": "needed fallback"})
        self.assertEqual("needed fallback", malformed["_digest.md"])
        no_source_context = prepare_writer({"claims.json": claims, "_digest.md": "source list only lives here"})
        self.assertEqual("source list only lives here", no_source_context["_digest.md"])

    def test_evidence_packet_uses_context_aware_selection_and_reports_exact_source_spans(self):
        body = (
            "Overview. " * 30 + "\n\n"
            "Measured latency is 2 seconds in the test fixture.\n\n"
            "Exception: the result does not apply when caching is disabled.\n\n"
            + "Appendix. " * 100
        )
        packet = evidence_packet(body, "measured latency test fixture", 520)
        self.assertTrue(packet["truncated"])
        self.assertIn("Measured latency is 2 seconds", packet["excerpt"])
        self.assertIn("Exception: the result does not apply", packet["excerpt"])
        self.assertGreater(packet["omitted_chars"], 0)
        self.assertTrue(packet["exact_spans"])
        for span in packet["exact_spans"]:
            self.assertEqual(packet["excerpt"].find(body[span["char_start"]:span["char_end"]]) >= 0, True)
        self.assertFalse(packet["scope"]["semantic_support_or_contradiction_determined"])
        self.assertTrue(packet["scope"]["omitted_context_is_not_evidence_of_absence"])

    def test_evidence_packet_keeps_an_independent_counter_evidence_paragraph_when_it_fits(self):
        body = (
            "Intro. " * 35 + "\n\n"
            "Measured latency is 2 seconds in the test fixture.\n\n"
            "Counter-evidence: a cold-cache run took 7 seconds.\n\n"
            + "Appendix. " * 90
        )
        packet = evidence_packet(body, "measured latency test fixture", 520)
        self.assertIn("Measured latency is 2 seconds", packet["excerpt"])
        self.assertIn("Counter-evidence: a cold-cache run took 7 seconds", packet["excerpt"])

    def test_evidence_packet_never_invents_position_for_generated_table_context(self):
        body = "| item | unit |\n| --- | --- |\n" + "\n".join(f"| row-{i} | {i} ms |" for i in range(50))
        packet = evidence_packet(body, "row-31 31 ms", 180)
        self.assertTrue(packet["truncated"])
        self.assertGreaterEqual(packet["scope"]["unlocated_selected_chars"], 0)
        self.assertTrue(packet["scope"]["positions_are_only_for_exact_source_substrings"])

    def test_claims_evidence_packet_bounds_a_shared_excerpt_and_marks_term_coverage_only(self):
        body = (
            "Intro. " * 35 + "\n\n"
            "Measured latency is 2 seconds in the test fixture.\n\n"
            "Counter-evidence: a cold-cache run took 7 seconds.\n\n"
            + "Appendix. " * 90
        )
        packet = claims_evidence_packet(body, [" measured latency ", "cold-cache run", "measured latency"], 520)
        self.assertLessEqual(len(packet["excerpt"]), 520)
        self.assertEqual(["measured latency", "cold-cache run"], [row["query"] for row in packet["claim_coverage"]])
        self.assertTrue(all(row["has_selected_query_term"] for row in packet["claim_coverage"]))
        self.assertTrue(all(row["selection_is_not_semantic_support"] for row in packet["claim_coverage"]))
        self.assertTrue(packet["scope"]["claim_coverage_is_term_presence_not_support"])
        for row in packet["claim_coverage"]:
            for span in row["candidate_exact_spans"]:
                self.assertIn(body[span["char_start"]:span["char_end"]], packet["excerpt"])

    def test_claims_evidence_packet_rejects_non_list_queries(self):
        with self.assertRaises(TypeError):
            claims_evidence_packet("body", "not a list", 100)


if __name__ == "__main__":
    unittest.main()
