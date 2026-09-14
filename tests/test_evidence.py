import copy
import unittest

from hprc.evidence import build_evidence_ledger, report_candidates, sha256_text, validate_evidence_ledger


class EvidenceInventoryTests(unittest.TestCase):
    def test_inventory_includes_uncited_prose_lists_and_tables_with_exact_offsets(self):
        report = (
            "# 질문\n"
            "인용 없는 설명이다. 인용된 사실이다. [S1]\n\n"
            "- 이 선택을 권한다. (판단)\n"
            "| 항목 | 값 |\n| --- | --- |\n| 속도 | 2초 [S1] |\n\n"
            '그는 “정확한 원문 인용입니다”라고 썼다. [S1]\n'
            "## 출처\n- S1 숨겨야 하는 출처 목록\n"
        )
        inventory = report_candidates(report)
        candidates = inventory["candidates"]

        self.assertEqual(["prose", "prose", "list", "table", "table", "prose"],
                         [candidate["structure"] for candidate in candidates])
        self.assertEqual(["fact_candidate", "fact_candidate", "judgment", "fact_candidate", "fact_candidate", "direct_quote"],
                         [candidate["classification"] for candidate in candidates])
        self.assertEqual([], candidates[0]["citations"])
        self.assertEqual(["S1"], candidates[1]["citations"])
        self.assertFalse(inventory["scope"]["semantic_extraction_complete"])
        for candidate in candidates:
            self.assertEqual(candidate["statement"], report[candidate["char_start"]:candidate["char_end"]])
            self.assertEqual(candidate["statement_sha256"], sha256_text(candidate["statement"]))
        self.assertFalse(any("숨겨야" in candidate["statement"] for candidate in candidates))

    def test_prose_judgment_marker_stays_attached_to_the_sentence(self):
        report = "이 선택을 추천한다. (판단) [S1]\n다음 사실이다. [S2]\n"
        candidates = report_candidates(report)["candidates"]
        self.assertEqual(2, len(candidates))
        self.assertEqual("judgment", candidates[0]["classification"])
        self.assertEqual("이 선택을 추천한다. (판단) [S1]", candidates[0]["statement"])
        self.assertEqual("fact_candidate", candidates[1]["classification"])

    def test_ledger_records_exact_note_snippets_and_unknown_provenance(self):
        report = "측정 지연은 2초였다. [S1]\n인용 없는 사실 후보다.\n"
        source_text = "개요 문단입니다.\n\n측정 조건은 저전력 모드였다. 측정 지연은 2000 ms였다."
        source = {"text": source_text, "metadata": {"id": "N-immutable", "sha256": sha256_text(source_text),
                                                       "published": "2026-09-14"}}
        ledger = build_evidence_ledger(report, {"S1": source})

        linked = ledger["claims"][0]
        self.assertEqual("traceable", linked["traceability_status"])
        self.assertEqual("unchecked", linked["verification"]["status"])
        self.assertEqual("unchecked", linked["evidence_links"][0]["relation"])
        self.assertEqual("requires_adjudication", linked["evidence_links"][0]["relation_basis"])
        snippet = linked["evidence_links"][0]["snippets"][0]
        self.assertEqual(snippet["text"], source_text[snippet["char_start"]:snippet["char_end"]])
        self.assertEqual("unknown", ledger["sources"][0]["provenance"]["source_type"])
        self.assertEqual("missing_citation", ledger["claims"][1]["traceability_status"])
        self.assertEqual([], validate_evidence_ledger(ledger, {"S1": source}, report))

    def test_source_paragraph_offsets_keep_table_header_unit_and_condition_together(self):
        text = "서문\n\n조건: 저전력 모드에서만 유효함\n| 지표 | 단위 |\n| --- | --- |\n| 지연 | 2초 |\n\n예외: 고성능 모드는 제외"
        ledger = build_evidence_ledger("저전력 모드 지연은 2초다. [S1]\n", {"S1": {"text": text, "metadata": {"id": "N-1"}}})
        snippets = ledger["claims"][0]["evidence_links"][0]["snippets"]
        selected = next(snippet for snippet in snippets if "2초" in snippet["text"])
        self.assertIn("조건: 저전력 모드", selected["text"])
        self.assertIn("| 지표 | 단위 |", selected["text"])
        self.assertEqual(selected["text"], text[selected["char_start"]:selected["char_end"]])

    def test_lexical_overlap_never_sets_source_support_or_contradiction(self):
        report = "비용은 20% 감소했다. [S1][S2]\n"
        sources = {"S1": {"text": "비용은 20% 감소했다.", "metadata": {"id": "N-1"}},
                   "S2": {"text": "비용은 20% 증가했다.", "metadata": {"id": "N-2"}}}
        ledger = build_evidence_ledger(report, sources)
        self.assertEqual({"unchecked"}, {link["relation"] for link in ledger["claims"][0]["evidence_links"]})

    def test_citation_check_requires_original_snapshot_hash_and_exact_unchanged_statement(self):
        checked = "첫 사실이다. [S1]\n둘째 사실이다. [S1]\n"
        current = "첫 사실이다. [S1]\n둘째 사실을 수정했다. [S1]\n"
        record = {"report": checked, "report_sha256": sha256_text(checked), "checks": [
            {"sentence": "첫 사실이다. [S1]", "cites": ["S1"], "supported": True, "reason": "직접 지지"},
            {"sentence": "둘째 사실이다. [S1]", "cites": ["S1"], "supported": True, "reason": "직접 지지"},
        ]}
        ledger = build_evidence_ledger(current, {"S1": {"text": "첫 사실이다. 둘째 사실이다.", "metadata": {"id": "N-1"}}},
                                       citation_record=record)
        self.assertEqual("supported", ledger["claims"][0]["verification"]["status"])
        self.assertEqual("unchecked", ledger["claims"][1]["verification"]["status"])

        bad_record = {**record, "report_sha256": "0" * 64}
        bad = build_evidence_ledger(checked, {"S1": "첫 사실이다."}, citation_record=bad_record)
        self.assertEqual("snapshot_hash_mismatch", bad["citation_record"]["status"])
        self.assertTrue(all(claim["verification"]["status"] == "unchecked" for claim in bad["claims"]))

    def test_validation_rejects_fabricated_snippet_location_and_hash(self):
        report = "근거 문장이다. [S1]\n"
        source = {"text": "원문 근거 문장이다.", "metadata": {"id": "N-1"}}
        ledger = build_evidence_ledger(report, {"S1": source})
        forged = copy.deepcopy(ledger)
        forged["claims"][0]["evidence_links"][0]["snippets"][0]["char_start"] = 1
        forged["claims"][0]["evidence_links"][0]["source_content_sha256"] = "bad"
        forged["claims"][0]["evidence_links"][0]["note_id"] = "N-forged"
        kinds = {issue["kind"] for issue in validate_evidence_ledger(forged, {"S1": source}, report)}
        self.assertEqual({"source_hash_mismatch", "note_id_mismatch", "snippet_location_mismatch"}, kinds)

    def test_recorded_source_hash_mismatch_is_not_traceable(self):
        report = "근거 문장이다. [S1]\n"
        source = {"text": "원문 근거 문장이다.", "metadata": {"id": "N-1", "sha256": "0" * 64}}
        ledger = build_evidence_ledger(report, {"S1": source})
        self.assertEqual("incomplete", ledger["claims"][0]["traceability_status"])
        self.assertEqual("recorded_source_hash_mismatch",
                         validate_evidence_ledger(ledger, {"S1": source}, report)[0]["kind"])


if __name__ == "__main__":
    unittest.main()
