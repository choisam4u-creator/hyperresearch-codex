import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from hprc.blind_eval import prepare_blind_packet, prepare_claim_inventory, report_body, score_annotated_claims
from hprc.evaluation import load_benchmark


class BlindEvalTests(unittest.TestCase):
    def setUp(self):
        self.body = "Observed rate is 12%. [S1]\nA second claim needs review. [S2]\n"
        self.case = {"id": "case-1", "prompt": "Check the two claims.", "lang": "en", "sources": {"S1": "rate", "S2": "review"}}
        first = "Observed rate is 12%. [S1]"; second = "A second claim needs review. [S2]"
        self.candidates = [{"claim_id": "c1", "required": True, "statement": first, "start": self.body.index(first), "end": self.body.index(first) + len(first), "cites": ["S1"]},
                           {"claim_id": "c2", "required": True, "critical": True, "statement": second, "start": self.body.index(second), "end": self.body.index(second) + len(second), "cites": ["S2"]}]

    def _inventory(self, report=None):
        return prepare_claim_inventory(report or self.body, self.candidates)

    def _annotation(self, claim_id, statement, verdict="supported", cites=None, **extra):
        start = self.body.index(statement)
        return {"claim_id": claim_id, "statement": statement, "start": start, "end": start + len(statement),
                "cites": cites if cites is not None else ["S1" if claim_id == "c1" else "S2"], "verdict": verdict, **extra}

    def test_packet_uses_report_md_exactly_and_keeps_identity_separate(self):
        final = ("<!-- generator: model-x -->\n<!-- runtime: hidden -->\n\n" + self.body
                 + "## Verification status\n\nreview_required — hidden result\n\n"
                 + "## Citation sample check\n\nhidden result\n\n"
                 + "## Source details (auto-generated)\n\n| hidden |\n")
        packet, identity = prepare_blind_packet({"report_md": self.body, "final_report": final}, self.case, "opaque-A")
        self.assertEqual(self.body, packet["report"])
        self.assertIn("substantive report text", packet["blindness_note"])
        self.assertNotIn("case_id", packet)
        self.assertEqual("case-1", identity["case_id"])
        self.assertEqual(self.body, report_body(final))
        self.assertNotIn("Verification status", report_body(final))
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            (run / "report.md").write_text(self.body, encoding="utf-8")
            final_path = run / "final_report.md"
            final_path.write_text(final, encoding="utf-8")
            path_packet, path_identity = prepare_blind_packet(final_path, self.case, "opaque-B")
            self.assertEqual(self.body, path_packet["report"])
            self.assertEqual(hashlib.sha256(final.encode("utf-8")).hexdigest(), path_identity["original_report_sha256"])
            self.assertNotEqual(path_identity["original_report_sha256"], path_identity["blind_report_sha256"])

    def test_missing_or_invalid_annotation_is_unknown_not_pass(self):
        only_first = score_annotated_claims(self.body, self._inventory(), [self._annotation("c1", "Observed rate is 12%. [S1]")], self.case["sources"])
        self.assertEqual(["c2"], only_first["missing_annotation_ids"])
        self.assertIsNone(only_first["aggregate_quality"])
        self.assertFalse(only_first["full_report_inventory_complete"])
        wrong_offset = self._annotation("c1", "Observed rate is 12%. [S1]"); wrong_offset["start"] += 1
        result = score_annotated_claims(self.body, self._inventory(), [wrong_offset, self._annotation("c2", "A second claim needs review. [S2]")], self.case["sources"])
        self.assertEqual(1, result["invalid_annotation_count"])
        self.assertFalse(result["aggregate_quality"])

    def test_missing_field_and_extra_claim_rubric_are_visible(self):
        bad = self._annotation("c1", "Observed rate is 12%. [S1]"); del bad["cites"]
        with self.assertRaises(ValueError):
            score_annotated_claims(self.body, self._inventory(), [bad], self.case["sources"])
        extra_statement = "Extra claim. [S1]"
        report = self.body + extra_statement
        extra = {"claim_id": "extra", "statement": extra_statement, "start": len(self.body), "end": len(report), "cites": ["S1"], "verdict": "insufficient"}
        result = score_annotated_claims(report, prepare_claim_inventory(report, self.candidates),
                                        [self._annotation("c1", "Observed rate is 12%. [S1]"), self._annotation("c2", "A second claim needs review. [S2]"), extra], self.case["sources"])
        self.assertEqual((1, 1), (result["extra_claim_count"], result["unsupported_extra_claim_count"]))
        self.assertFalse(result["aggregate_quality"])
        invalid_extra = {**extra, "cites": ["S2"], "verdict": "supported"}
        result = score_annotated_claims(report, prepare_claim_inventory(report, self.candidates),
                                        [self._annotation("c1", "Observed rate is 12%. [S1]"), self._annotation("c2", "A second claim needs review. [S2]"), invalid_extra], self.case["sources"])
        self.assertEqual(1, result["invalid_annotation_count"])
        self.assertFalse(result["aggregate_quality"])

    def test_critical_factual_error_is_not_qualified(self):
        result = score_annotated_claims(self.body, self._inventory(),
                                        [self._annotation("c1", "Observed rate is 12%. [S1]"), self._annotation("c2", "A second claim needs review. [S2]", "contradicted")], self.case["sources"])
        self.assertEqual((1, 1), (result["factual_error_count"], result["critical_error_count"]))
        self.assertFalse(result["aggregate_quality"])

    def test_insufficient_and_partial_cites_do_not_qualify(self):
        insufficient = score_annotated_claims(self.body, self._inventory(),
                                               [self._annotation("c1", "Observed rate is 12%. [S1]", "insufficient"), self._annotation("c2", "A second claim needs review. [S2]")], self.case["sources"])
        self.assertEqual(1, insufficient["insufficient_required_count"])
        self.assertFalse(insufficient["aggregate_quality"])
        combined = "Observed rate is 12%. [S1][S2]"
        report = combined + "\nA second claim needs review. [S2]\n"
        candidates = [{"claim_id": "c1", "statement": combined, "start": 0, "end": len(combined), "cites": ["S1", "S2"]}]
        with self.assertRaises(ValueError):
            prepare_claim_inventory(report, [{**candidates[0], "cites": ["S1"]}])

    def test_empty_or_wrong_report_inventory_is_rejected(self):
        with self.assertRaises(ValueError):
            prepare_claim_inventory(self.body, [])
        with self.assertRaises(ValueError):
            score_annotated_claims(self.body, {"inventory_kind": "manual_full_report_candidate_inventory", "report_sha256": "wrong", "candidates": self.candidates}, [], self.case["sources"])

    def test_annotation_must_bind_to_the_frozen_candidate_span(self):
        repeated = self.body + "Observed rate is 12%. [S1]\n"
        inventory = prepare_claim_inventory(repeated, self.candidates)
        later = repeated.rindex("Observed rate is 12%. [S1]")
        moved = {"claim_id": "c1", "statement": "Observed rate is 12%. [S1]", "start": later,
                 "end": later + len("Observed rate is 12%. [S1]"), "cites": ["S1"], "verdict": "supported"}
        result = score_annotated_claims(repeated, inventory, [moved, self._annotation("c2", "A second claim needs review. [S2]")], self.case["sources"])
        self.assertEqual(1, result["invalid_annotation_count"])
        self.assertFalse(result["aggregate_quality"])

    def test_optional_candidates_cannot_hide_submitted_errors_or_make_vacuous_pass(self):
        candidates = [{**candidate, "required": False} for candidate in self.candidates]
        result = score_annotated_claims(self.body, prepare_claim_inventory(self.body, candidates), [], self.case["sources"])
        self.assertIsNone(result["aggregate_quality"])
        candidates[0]["required"] = True
        result = score_annotated_claims(self.body, prepare_claim_inventory(self.body, candidates),
            [self._annotation("c1", "Observed rate is 12%. [S1]"), self._annotation("c2", "A second claim needs review. [S2]", "contradicted")], self.case["sources"])
        self.assertFalse(result["aggregate_quality"])

    def test_realistic_fixture_has_separate_answers_and_long_replay_cases(self):
        fixtures = Path(__file__).parent / "fixtures"
        frozen, answers = load_benchmark(fixtures / "realistic_inputs.json", fixtures / "realistic_answers.json")
        self.assertEqual(6, len(frozen["cases"]))
        self.assertEqual({"dev": 4, "holdout": 2}, {split: sum(case["split"] == split for case in frozen["cases"]) for split in ("dev", "holdout")})
        self.assertFalse(any("answer" in json.dumps(case).lower() for case in frozen["cases"]))
        self.assertEqual({case["id"] for case in frozen["cases"]}, set(answers))
        sizes = {case["id"]: sum(len(text) for text in case["sources"].values()) for case in frozen["cases"]}
        self.assertGreater(sizes["real-ko-table"], 6000)
        self.assertGreater(sizes["real-en-long"], 6000)


if __name__ == "__main__":
    unittest.main()
