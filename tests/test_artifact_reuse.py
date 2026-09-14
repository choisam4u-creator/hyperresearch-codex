import json
import os
import tempfile
import unittest
from pathlib import Path

from hprc import artifact_reuse


class ArtifactReuseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.context = {
            "question": "고정 질문",
            "lang": "ko",
            "as_of": "2026-09-14",
            "config": {"preset": "lean"},
            "model": {"name": "fixture", "effort": "low"},
            "prompt_sha256": "1" * 64,
            "schema_sha256": "2" * 64,
            "runtime": {"code_sha256": "3" * 64},
            "source_hashes": {"S1": "4" * 64},
        }
        self.inputs = {"question.txt": "고정 질문", "S1-note.md": "근거 본문"}

    def tearDown(self):
        self.tmp.cleanup()

    def test_key_is_order_stable_and_every_exact_value_matters(self):
        key = artifact_reuse.make_key(self.context, self.inputs)
        reordered = artifact_reuse.make_key(dict(reversed(list(self.context.items()))),
                                              dict(reversed(list(self.inputs.items()))))
        self.assertEqual(key, reordered)
        self.assertNotEqual(key, artifact_reuse.make_key({**self.context, "lang": "en"}, self.inputs))
        self.assertNotEqual(key, artifact_reuse.make_key(self.context,
                                                         {**self.inputs, "S1-note.md": "바뀐 근거"}))

    def test_save_and_load_preserve_result_and_provenance_without_invented_usage(self):
        key = artifact_reuse.make_key(self.context, self.inputs)
        result = {"claims": [{"id": "C1", "text": "사실", "sources": ["S1"]}],
                  "contradictions": [], "gaps": []}
        provenance = {"source_run_id": "run-old", "usage": {"input_tokens": 123}}
        artifact_reuse.save(self.root, key, result, provenance)

        loaded = artifact_reuse.load(self.root, key)
        self.assertEqual(result, loaded["result"])
        self.assertEqual(provenance, loaded["provenance"])
        self.assertNotIn("tokens_saved", loaded["provenance"])
        self.assertEqual([], list((self.root / "research" / "artifact-cache").glob(".hpr-artifact-*")))

    def test_corrupt_tampered_and_unknown_schema_entries_fail_closed(self):
        key = artifact_reuse.make_key(self.context, self.inputs)
        artifact_reuse.save(self.root, key, {"claims": []}, {"source_run_id": "r1"})
        path = self.root / "research" / "artifact-cache" / f"{key}.json"
        envelope = json.loads(path.read_text(encoding="utf-8"))
        envelope["result"]["claims"].append({"id": "forged"})
        path.write_text(json.dumps(envelope), encoding="utf-8")
        self.assertIsNone(artifact_reuse.load(self.root, key))

        envelope["schema_version"] = 999
        path.write_text(json.dumps(envelope), encoding="utf-8")
        self.assertIsNone(artifact_reuse.load(self.root, key))
        path.write_text("{broken", encoding="utf-8")
        self.assertIsNone(artifact_reuse.load(self.root, key))

    def test_changed_config_uses_a_different_file_and_cannot_hit(self):
        key = artifact_reuse.make_key(self.context, self.inputs)
        artifact_reuse.save(self.root, key, {"claims": []}, {"source_run_id": "r1"})
        changed = artifact_reuse.make_key({**self.context, "config": {"preset": "standard"}}, self.inputs)
        self.assertNotEqual(key, changed)
        self.assertIsNone(artifact_reuse.load(self.root, changed))

    def test_invalid_key_is_rejected_without_path_creation(self):
        self.assertIsNone(artifact_reuse.load(self.root, "../outside"))
        with self.assertRaises(ValueError):
            artifact_reuse.save(self.root, "../outside", {}, {})
        self.assertFalse((self.root / "outside.json").exists())

    @unittest.skipIf(os.name == "nt", "Windows CI에서 symlink 권한이 보장되지 않음")
    def test_symlinked_cache_directory_is_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        research = self.root / "research"
        research.mkdir()
        (research / "artifact-cache").symlink_to(outside, target_is_directory=True)
        key = artifact_reuse.make_key(self.context, self.inputs)
        self.assertIsNone(artifact_reuse.load(self.root, key))
        with self.assertRaises(ValueError):
            artifact_reuse.save(self.root, key, {}, {})
        self.assertEqual([], list(outside.iterdir()))


if __name__ == "__main__":
    unittest.main()
