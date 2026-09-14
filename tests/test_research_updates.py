import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from hprc import research_updates, vault


class ResearchUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.notes = self.root / "research" / "notes"
        self.runs = self.root / "research" / "runs"
        self.notes.mkdir(parents=True)
        self.runs.mkdir()
        self.context = {
            "question": "어떤 사실이 바뀌었나?",
            "lang": "ko",
            "as_of": "2026-09-14",
            "analysis_runtime": {
                "config_hash": "config-v1",
                "prompt_hash": "prompt-v1",
                "code_hash": "code-v1",
                "model": {"model": "fixture", "effort": "low"},
            },
        }

    def tearDown(self):
        self.tmp.cleanup()

    def source(self, source_id, url, text):
        page = {
            "url": url, "final_url": url, "title": f"title {source_id}", "domain": "example.test",
            "via": "fixture", "official": True, "published": "2026-09-01",
            "published_source": "fixture", "modified": "", "modified_source": "",
            "canonical": url, "text": text, "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "fetched_at": "2026-09-14T00:00:00+00:00",
        }
        path = vault.write_note(self.notes, source_id, page)
        return {"id": source_id, "note_id": vault.read_front(path)["id"], "path": str(path),
                "url": url, "title": page["title"]}

    def write_run(self, name, sources, claims, *, context=None):
        run = self.runs / name
        run.mkdir()
        ctx = context or self.context
        runtime = ctx["analysis_runtime"]
        manifest = {
            "run_id": name, "prompt": ctx["question"], "lang": ctx["lang"], "as_of": ctx["as_of"],
            "runtime": {"config_hash": runtime["config_hash"], "prompt_hash": runtime["prompt_hash"],
                        "code_hash": runtime["code_hash"], "models": {"analyst": runtime["model"]}},
        }
        (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (run / "sources.json").write_text(json.dumps({"sources": sources}), encoding="utf-8")
        (run / "claims.json").write_text(json.dumps({"claims": claims, "contradictions": [], "gaps": []}), encoding="utf-8")
        return run

    def test_missing_runtime_does_not_certify_unchanged_context(self):
        source=self.source('S1','https://example.test/a','stable source')
        claims=[{'id':'C1','text':'claim','sources':['S1'],'confidence':'high'}]
        before=self.write_run('before',[source],claims);after=self.write_run('after',[source],claims)
        for directory in (before,after):
            p=directory/'manifest.json';data=json.loads(p.read_text());data['runtime']={};p.write_text(json.dumps(data))
        result=research_updates.compare_runs(before,after)
        self.assertFalse(result['comparison_valid']);self.assertTrue(result['requires_full_analysis'])

    def test_identical_immutable_sources_compare_unchanged_despite_alias_remap(self):
        old_source = self.source("S1", "https://example.test/a", "동일한 본문")
        current_source = {**old_source, "id": "S7"}
        previous = self.write_run("previous", [old_source],
                                  [{"id": "C1", "text": "같은 주장", "sources": ["S1"], "confidence": "high"}])
        current = self.write_run("current", [current_source],
                                 [{"id": "C1", "text": "같은 주장", "sources": ["S7"], "confidence": "high"}])

        result = research_updates.compare_runs(previous, current)
        self.assertEqual("unchanged", result["status"])
        self.assertTrue(result["comparison_valid"])
        self.assertFalse(result["freshness_certified"])
        self.assertEqual("S7", result["unchanged_sources"][0]["current_id"])
        self.assertEqual(["C1"], result["claim_diff"]["unchanged"])

        plan = research_updates.plan_incremental_analysis(previous, [current_source], self.context)
        self.assertEqual("unchanged", plan["mode"])
        self.assertTrue(plan["whole_analysis_cache_eligible"])
        self.assertEqual({"S1": "S7"}, plan["source_id_map"])
        self.assertEqual(["S7"], plan["retained_claims"][0]["sources"])
        self.assertEqual([], plan["analysis_source_ids"])

    def test_changed_and_added_sources_make_bounded_incremental_plan(self):
        old_a = self.source("S1", "https://example.test/a", "이전 A 본문")
        stable_b = self.source("S2", "https://example.test/b", "동일 B 본문")
        previous = self.write_run("previous", [old_a, stable_b], [
            {"id": "C1", "text": "A와 B를 함께 쓴 주장", "sources": ["S1", "S2"], "confidence": "high"},
            {"id": "C2", "text": "B만 쓴 주장", "sources": ["S2"], "confidence": "high"},
        ])
        new_a = self.source("N1", "https://example.test/a", "변경된 A 본문")
        current_b = {**stable_b, "id": "N2"}
        added_c = self.source("N3", "https://example.test/c", "새 C 본문")
        current = self.write_run("current", [new_a, current_b, added_c], [
            {"id": "C1", "text": "A와 B를 함께 쓴 주장", "sources": ["N1", "N2"], "confidence": "medium"},
            {"id": "C2", "text": "B만 쓴 주장", "sources": ["N2"], "confidence": "high"},
            {"id": "C3", "text": "C의 새 주장", "sources": ["N3"], "confidence": "high"},
        ])

        result = research_updates.compare_runs(previous, current)
        self.assertEqual("changed", result["status"])
        self.assertEqual(["C1"], result["affected_claim_ids"]["previous"])
        self.assertEqual(["C1", "C3"], result["affected_claim_ids"]["current"])
        self.assertEqual(["C3"], result["claim_diff"]["added"])
        self.assertEqual(["C1"], result["claim_diff"]["changed"])

        plan = research_updates.plan_incremental_analysis(previous, [new_a, current_b, added_c], self.context)
        self.assertEqual("incremental", plan["mode"])
        self.assertFalse(plan["requires_full_analysis"])
        self.assertEqual(["C1"], plan["invalidated_claim_ids"])
        self.assertEqual(["C2"], [claim["id"] for claim in plan["retained_claims"]])
        self.assertEqual(["N2"], plan["retained_claims"][0]["sources"])
        self.assertEqual(["N1", "N3"], plan["changed_source_ids"])
        self.assertEqual(["N1", "N2", "N3"], plan["analysis_source_ids"])
        self.assertEqual(["contradictions", "gaps"], plan["recompute"])

    def test_changed_analysis_context_requires_full_analysis(self):
        source = self.source("S1", "https://example.test/a", "본문")
        previous = self.write_run("previous", [source],
                                  [{"id": "C1", "text": "주장", "sources": ["S1"], "confidence": "high"}])
        changed_context = {**self.context, "analysis_runtime": {**self.context["analysis_runtime"],
                                                                 "config_hash": "config-v2"}}
        plan = research_updates.plan_incremental_analysis(previous, [source], changed_context)
        self.assertEqual("full", plan["mode"])
        self.assertTrue(plan["requires_full_analysis"])
        self.assertEqual(["analysis_runtime"], plan["context_diff"])
        self.assertIn("analysis_context_changed", plan["reasons"])

        current = self.write_run("current", [source],
                                 [{"id": "C1", "text": "주장", "sources": ["S1"], "confidence": "high"}],
                                 context=changed_context)
        compared = research_updates.compare_runs(previous, current)
        self.assertEqual("changed", compared["status"])
        self.assertEqual(["analysis_runtime"], compared["context_diff"])
        self.assertTrue(compared["comparison_valid"])
        self.assertTrue(compared["requires_full_analysis"])

    def test_tampered_or_missing_hash_is_unknown_and_invalidates_reuse(self):
        source = self.source("S1", "https://example.test/a", "원래 본문")
        previous = self.write_run("previous", [source],
                                  [{"id": "C1", "text": "주장", "sources": ["S1"], "confidence": "high"}])
        path = Path(source["path"])
        path.write_text(path.read_text(encoding="utf-8").replace("원래 본문", "변조 본문"), encoding="utf-8")
        plan = research_updates.plan_incremental_analysis(previous, [source], self.context)
        self.assertTrue(plan["requires_full_analysis"])
        self.assertIn("source_identity_unknown", plan["reasons"])

        current = self.write_run("current", [{"id": "S1", "url": "https://example.test/a"}],
                                 [{"id": "C1", "text": "주장", "sources": ["S1"], "confidence": "high"}])
        compared = research_updates.compare_runs(previous, current)
        self.assertEqual("unknown", compared["status"])
        self.assertTrue(compared["requires_full_analysis"])
        self.assertFalse(compared["freshness_certified"])

    def test_missing_previous_run_fails_closed_to_full(self):
        plan = research_updates.plan_incremental_analysis(self.runs / "missing", [], self.context)
        self.assertEqual("full", plan["mode"])
        self.assertTrue(plan["requires_full_analysis"])
        self.assertTrue(plan["reasons"])


if __name__ == "__main__":
    unittest.main()
