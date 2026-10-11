import json
import unittest
from pathlib import Path

from evals import labeled


class LabeledEvalTest(unittest.TestCase):
    def test_cases_have_unique_keys_and_valid_labels(self):
        cases = labeled.load_cases(which="all")
        self.assertGreaterEqual(len(labeled.load_cases(which="holdout")), 10)
        self.assertGreaterEqual(len(labeled.load_cases(which="holdout2")), 10)
        self.assertGreaterEqual(len(cases), 20)
        for c in cases:
            md = c["responses"]["writer"][0]["markdown"]
            for lab in c["labels"]:
                self.assertEqual(md.count(lab["key"]), 1, (c["id"], lab["key"]))
                self.assertIn(lab["label"], ("ok", "mismatch", "unverified"))

    def test_labeled_cases_do_not_overlap_fixed_cases(self):
        fixed = {json.loads(p.read_text(encoding="utf-8"))["id"] for p in (Path(labeled.__file__).parent / "cases").glob("*.json")}
        dev = {c["id"] for c in labeled.load_cases()}
        holdout = {c["id"] for c in labeled.load_cases(which="holdout")}
        holdout2 = {c["id"] for c in labeled.load_cases(which="holdout2")}
        self.assertFalse(fixed & (dev | holdout | holdout2))
        self.assertFalse(dev & holdout)
        self.assertFalse((dev | holdout) & holdout2)

    def test_prediction_reads_marks_after_sentence(self):
        report = "## Answer\nA fell from 9 to 5 (source mismatch) [S1]. B rose [S2].\n- C went up (no source).\n"
        self.assertEqual(labeled.predict(labeled.sentence_at(report, "A fell")), "mismatch")
        self.assertEqual(labeled.predict(labeled.sentence_at(report, "B rose")), "ok")
        self.assertEqual(labeled.predict(labeled.sentence_at(report, "C went")), "unverified")
        self.assertIsNone(labeled.sentence_at(report, "D"))

    def test_metrics_precision_recall(self):
        rows = [{"label": "mismatch", "pred": "mismatch"}, {"label": "mismatch", "pred": "ok"},
                {"label": "ok", "pred": "mismatch"}, {"label": "ok", "pred": "ok"}]
        m = labeled.metrics(rows)
        self.assertAlmostEqual(m["precision"], 50.0)
        self.assertAlmostEqual(m["recall"], 50.0)
        self.assertAlmostEqual(m["false_flag_rate"], 50.0)


if __name__ == "__main__":
    unittest.main()
