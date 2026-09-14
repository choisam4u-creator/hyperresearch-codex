"""Regression guards for provenance wording; no model backend is invoked."""
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hprc import cluster, pipeline  # noqa: E402


class ProvenanceBoundaryTests(unittest.TestCase):
    def test_host_skew_and_cluster_are_not_independence_or_publisher_decisions(self):
        sources = [
            {"id": "S1", "domain": "fixture.invalid", "canonical": "https://fixture.invalid/a", "cluster": "S1"},
            {"id": "S2", "domain": "fixture.invalid", "canonical": "https://fixture.invalid/b", "cluster": "S2"},
        ]
        assigned = cluster.cluster(sources, {"S1": "alpha " * 30, "S2": "beta " * 30})
        self.assertEqual({"S1": "S1", "S2": "S2"}, assigned)  # shared host remains two relationship groups

        run = pipeline.Run.__new__(pipeline.Run)
        run.sources = sources
        run.cfg = {"domain_skew_warn": 0.6}
        note = run.independence_md()
        self.assertIn("# 출처 관계와 중복 후보", note)
        self.assertIn("URL host 분포 경고", note)
        self.assertIn("동일 발행자·원문", note)
        self.assertIn("원문 게시일 부재를 판정할 수 없다", note)
        self.assertIn("URL 정본 일치 또는 본문 유사", note)
        self.assertNotIn("독립 근거 묶음", note)
        self.assertNotIn("다른 관점의 출처가 부족할 수 있다", note)

    def test_all_report_writers_receive_the_metadata_boundary(self):
        prompts = ROOT / "hprc" / "prompts"
        for name in ("writer.md", "draft.md", "synth.md"):
            ko = (prompts / "ko" / name).read_text(encoding="utf-8")
            en = (prompts / "en" / name).read_text(encoding="utf-8")
            self.assertIn("처리·관계 정보", ko, name)
            self.assertIn("원문이 직접 말할 때만 [S번호]", ko, name)
            self.assertIn("processing/relationship metadata", en, name)
            self.assertIn("only when a source directly says it, with [S#]", en, name)


if __name__ == "__main__":
    unittest.main()
