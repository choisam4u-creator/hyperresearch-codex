"""선택형 의미 citecheck 응답의 구조·원문 결속을 검증한다.

모델이 제안한 atom 분해와 verdict를 받아들이기 전에, 보고서 표본과 실제로
checker에 보낸 출처 발췌의 정확한 문자열에 묶는다. 이 검사는 분해 완전성이나
사실 정확성을 판정하지 않는다.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any


_VERDICTS = {"supported", "contradicted", "insufficient"}
_RELATIONS = {"supports", "contradicts"}
_CITATION = re.compile(r"\[S\d+\]")
_NON_SUBSTANTIVE_WORD = re.compile(r"\b(?:and|or|but)\b|(?:그리고|및|또는|그러나|하지만)", re.IGNORECASE)
_SEMANTIC_SYMBOLS = frozenset("<>=≤≥≠≈±−-+/%‰‱°℃℉×÷$€£¥₩")
_MARKDOWN_LINE_PREFIX = re.compile(r"(?m)^[ \t]{0,3}(?:#{1,6}[ \t]+|[-+>][ \t]+)")

_EVIDENCE_ITEM = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "source_id": {"type": "string"},
        "quote": {"type": "string"},
        "relation": {"type": "string", "enum": sorted(_RELATIONS)},
    },
    "required": ["source_id", "quote", "relation"],
}

_ATOM = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "quote": {"type": "string"},
        "verdict": {"type": "string", "enum": sorted(_VERDICTS)},
        "evidence": {"type": "array", "items": _EVIDENCE_ITEM},
        "conditions": {"type": "string"},
        "limitations": {"type": "string"},
    },
    "required": ["quote", "verdict", "evidence", "conditions", "limitations"],
}

SEMANTIC_CITECHECK = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "checks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "sentence": {"type": "string"},
                    "cites": {"type": "array", "items": {"type": "string"}},
                    "supported": {"type": "boolean"},
                    "reason": {"type": "string"},
                    "atoms": {"type": "array", "items": _ATOM},
                },
                "required": ["sentence", "cites", "supported", "reason", "atoms"],
            },
        },
    },
    "required": ["checks"],
}


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _issue(kind: str, message: str, *, check_index: int | None = None,
           atom_index: int | None = None, evidence_index: int | None = None) -> dict:
    issue = {"kind": kind, "message": message}
    if check_index is not None:
        issue["check_index"] = check_index
    if atom_index is not None:
        issue["atom_index"] = atom_index
    if evidence_index is not None:
        issue["evidence_index"] = evidence_index
    return issue


def _exact_span(parent: str, quote: Any) -> dict | None:
    if not isinstance(quote, str) or not quote.strip():
        return None
    start = parent.find(quote)
    if start < 0:
        return None
    return {
        "char_start": start,
        "char_end": start + len(quote),
        "quote_sha256": _sha256(quote),
        "occurrence_count": parent.count(quote),
    }


def _substantive_indices(sentence: str) -> set[int]:
    """Return lexical and meaning-bearing symbol positions, excluding Markdown syntax.

    Emphasis/link delimiters and line prefixes are presentation syntax. Comparison,
    range, arithmetic, percent, temperature, and currency symbols are retained so an
    atom cannot silently omit ``<`` from ``x < 2`` or ``%`` from a numeric claim.
    """
    excluded = set()
    for pattern in (_CITATION, _NON_SUBSTANTIVE_WORD):
        for match in pattern.finditer(sentence):
            excluded.update(range(match.start(), match.end()))
    for match in _MARKDOWN_LINE_PREFIX.finditer(sentence):
        excluded.update(range(match.start(), match.end()))

    required = set()
    for index, char in enumerate(sentence):
        if index in excluded:
            continue
        if char.isalnum() or char in _SEMANTIC_SYMBOLS:
            required.add(index)
            continue
        # Numeric separators carry meaning, while ordinary sentence punctuation does not.
        if (char in ".,:" and 0 < index < len(sentence) - 1
                and sentence[index - 1].isdigit() and sentence[index + 1].isdigit()):
            required.add(index)
    return required


def _uncovered_fragments(sentence: str, uncovered: set[int]) -> list[str]:
    if not uncovered:
        return []
    fragments, start, previous = [], None, None
    for index in sorted(uncovered):
        if start is None:
            start = previous = index
        elif index == previous + 1:
            previous = index
        else:
            fragments.append(sentence[start:previous + 1])
            start = previous = index
    fragments.append(sentence[start:previous + 1])
    return fragments


def _validate_atom(atom: Any, sentence: str, parent_cites: set[str], sources: dict[str, str],
                   original_sources: dict[str, str] | None, check_index: int,
                   atom_index: int) -> tuple[dict | None, list[dict]]:
    issues = []
    if not isinstance(atom, dict):
        return None, [_issue("atom_not_object", "atom은 객체여야 합니다.", check_index=check_index, atom_index=atom_index)]
    expected_atom_keys = {"quote", "verdict", "evidence", "conditions", "limitations"}
    if set(atom) != expected_atom_keys:
        issues.append(_issue("atom_fields_invalid", "atom 필드는 strict schema와 정확히 일치해야 합니다.",
                             check_index=check_index, atom_index=atom_index))
    quote = atom.get("quote")
    atom_span = _exact_span(sentence, quote)
    if atom_span is None:
        issues.append(_issue("atom_not_exact_substring", "atom quote가 부모 문장의 비어 있지 않은 정확한 부분 문자열이 아닙니다.",
                             check_index=check_index, atom_index=atom_index))
    verdict = atom.get("verdict")
    if verdict not in _VERDICTS:
        issues.append(_issue("unknown_atom_verdict", "허용되지 않은 atom verdict입니다.",
                             check_index=check_index, atom_index=atom_index))
    if not isinstance(atom.get("conditions"), str) or not isinstance(atom.get("limitations"), str):
        issues.append(_issue("atom_context_not_string", "conditions와 limitations는 문자열이어야 합니다.",
                             check_index=check_index, atom_index=atom_index))
    raw_evidence = atom.get("evidence")
    if not isinstance(raw_evidence, list):
        issues.append(_issue("evidence_not_array", "evidence는 배열이어야 합니다.",
                             check_index=check_index, atom_index=atom_index))
        raw_evidence = []

    evidence = []
    evidence_seen = set()
    for evidence_index, item in enumerate(raw_evidence):
        if not isinstance(item, dict):
            issues.append(_issue("evidence_not_object", "evidence 항목은 객체여야 합니다.",
                                 check_index=check_index, atom_index=atom_index, evidence_index=evidence_index))
            continue
        if set(item) != {"source_id", "quote", "relation"}:
            issues.append(_issue("evidence_fields_invalid", "evidence 필드는 strict schema와 정확히 일치해야 합니다.",
                                 check_index=check_index, atom_index=atom_index, evidence_index=evidence_index))
            continue
        source_id, evidence_quote, relation = item.get("source_id"), item.get("quote"), item.get("relation")
        if not isinstance(source_id, str) or not isinstance(evidence_quote, str) or not isinstance(relation, str):
            issues.append(_issue("evidence_field_types_invalid", "source_id, quote, relation은 문자열이어야 합니다.",
                                 check_index=check_index, atom_index=atom_index, evidence_index=evidence_index))
            continue
        key = (source_id, evidence_quote, relation)
        if key in evidence_seen:
            issues.append(_issue("duplicate_evidence", "같은 evidence 항목이 중복됐습니다.",
                                 check_index=check_index, atom_index=atom_index, evidence_index=evidence_index))
            continue
        evidence_seen.add(key)
        if source_id not in parent_cites:
            issues.append(_issue("evidence_source_not_parent_cite", "evidence source_id가 부모 문장의 인용에 없습니다.",
                                 check_index=check_index, atom_index=atom_index, evidence_index=evidence_index))
            continue
        source_text = sources.get(source_id)
        if source_text is None:
            issues.append(_issue("evidence_source_not_sent", "checker에 실제 전송되지 않은 source_id입니다.",
                                 check_index=check_index, atom_index=atom_index, evidence_index=evidence_index))
            continue
        if relation not in _RELATIONS:
            issues.append(_issue("unknown_evidence_relation", "허용되지 않은 evidence relation입니다.",
                                 check_index=check_index, atom_index=atom_index, evidence_index=evidence_index))
            continue
        source_span = _exact_span(source_text, evidence_quote)
        if source_span is None:
            issues.append(_issue("evidence_quote_not_exact_substring", "evidence quote가 전송한 출처 발췌의 비어 있지 않은 정확한 부분 문자열이 아닙니다.",
                                 check_index=check_index, atom_index=atom_index, evidence_index=evidence_index))
            continue
        bound_evidence = {
            "source_id": source_id,
            "quote": evidence_quote,
            "relation": relation,
            "source_sha256": _sha256(source_text),
            **source_span,
        }
        if original_sources is not None:
            original_text = original_sources.get(source_id)
            if original_text is None:
                issues.append(_issue("evidence_original_source_missing", "전송 발췌에 대응하는 원본 source가 없습니다.",
                                     check_index=check_index, atom_index=atom_index, evidence_index=evidence_index))
                continue
            original_span = _exact_span(original_text, evidence_quote)
            if original_span is None:
                issues.append(_issue("evidence_quote_not_in_original", "evidence quote가 전송 발췌에는 있지만 원본 source에는 없습니다.",
                                     check_index=check_index, atom_index=atom_index, evidence_index=evidence_index))
                continue
            bound_evidence.update({
                "original_source_sha256": _sha256(original_text),
                "original_char_start": original_span["char_start"],
                "original_char_end": original_span["char_end"],
                "original_occurrence_count": original_span["occurrence_count"],
            })
        evidence.append(bound_evidence)

    relations = {item["relation"] for item in evidence}
    if verdict == "supported" and ("supports" not in relations or "contradicts" in relations):
        issues.append(_issue("supported_atom_without_clean_support", "supported atom에는 support가 필요하며 contradict evidence가 없어야 합니다.",
                             check_index=check_index, atom_index=atom_index))
    elif verdict == "contradicted" and ("contradicts" not in relations or "supports" in relations):
        issues.append(_issue("contradicted_atom_without_clean_contradiction", "contradicted atom에는 contradiction이 필요하며 support evidence가 없어야 합니다.",
                             check_index=check_index, atom_index=atom_index))

    if issues:
        return None, issues
    return {
        "quote": quote,
        "verdict": verdict,
        "evidence": evidence,
        "conditions": atom["conditions"],
        "limitations": atom["limitations"],
        "sentence_sha256": _sha256(sentence),
        **atom_span,
    }, []


def validate_semantic_checks(response: Any, samples: list[dict], sources: dict[str, str], *,
                             original_sources: dict[str, str] | None = None) -> dict:
    """엄격한 원문 결속을 통과한 의미 check만 legacy bool check로 돌려준다.

    ``sources``에는 전체 노트가 아니라 해당 citecheck 호출에 실제로 보낸 문자열만
    넣어야 한다. 누락되거나 잘못된 record는 ``semantic.records``에 unchecked로
    남으며 ``checks``에 들어가지 않는다.
    """
    global_issues = []
    valid_sources = {}
    for source_id, text in sources.items():
        if not isinstance(source_id, str) or not isinstance(text, str):
            global_issues.append(_issue("source_input_invalid", "sources의 key와 raw text는 문자열이어야 합니다."))
            continue
        valid_sources[source_id] = text
    valid_original_sources = None
    if original_sources is not None:
        valid_original_sources = {}
        for source_id, text in original_sources.items():
            if not isinstance(source_id, str) or not isinstance(text, str):
                global_issues.append(_issue("original_source_input_invalid", "original_sources의 key와 raw text는 문자열이어야 합니다."))
                continue
            valid_original_sources[source_id] = text
    source_inputs = {source_id: {"sha256": _sha256(text), "chars": len(text)}
                     for source_id, text in sorted(valid_sources.items())}
    sample_by_key = {}
    invalid_sample_indices = set()
    for sample_index, sample in enumerate(samples):
        if (not isinstance(sample, dict) or not isinstance(sample.get("sentence"), str)
                or not isinstance(sample.get("cites"), list)
                or not all(isinstance(item, str) for item in sample.get("cites", []))):
            invalid_sample_indices.add(sample_index)
            global_issues.append(_issue("sample_invalid", "표본 sentence는 문자열, cites는 문자열 배열이어야 합니다."))
            continue
        key = (sample["sentence"], frozenset(sample["cites"]))
        if key in sample_by_key:
            global_issues.append(_issue("duplicate_sample", "입력 표본의 sentence+cites가 중복됐습니다."))
            continue
        sample_by_key[key] = (sample_index, sample)

    raw_checks = response.get("checks") if isinstance(response, dict) else None
    if not isinstance(raw_checks, list):
        raw_checks = []
        global_issues.append(_issue("response_checks_missing", "응답 checks 배열이 없습니다."))

    response_by_key = {}
    duplicate_check_keys = set()
    for check_index, check in enumerate(raw_checks):
        if not isinstance(check, dict):
            global_issues.append(_issue("check_not_object", "check는 객체여야 합니다.", check_index=check_index))
            continue
        cites, sentence = check.get("cites"), check.get("sentence")
        if not isinstance(sentence, str) or not isinstance(cites, list) or not all(isinstance(item, str) for item in cites):
            global_issues.append(_issue("check_identity_invalid", "check sentence는 문자열, cites는 문자열 배열이어야 합니다.", check_index=check_index))
            continue
        key = (sentence, frozenset(cites))
        if key not in sample_by_key:
            global_issues.append(_issue("check_not_exact_sample", "check의 sentence+cites가 표본과 정확히 일치하지 않습니다.", check_index=check_index))
            continue
        if key in response_by_key:
            global_issues.append(_issue("duplicate_check", "같은 표본에 대한 check가 중복됐습니다.", check_index=check_index))
            duplicate_check_keys.add(key)
            response_by_key.pop(key, None)
            continue
        if key in duplicate_check_keys:
            global_issues.append(_issue("duplicate_check", "같은 표본에 대한 check가 중복됐습니다.", check_index=check_index))
            continue
        response_by_key[key] = (check_index, check)

    legacy_checks = []
    records = []
    for sample_index, sample in enumerate(samples):
        if sample_index in invalid_sample_indices:
            records.append({"sample_index": sample_index, "sentence": "", "cites": [], "status": "unchecked",
                            "issues": [_issue("sample_invalid", "잘못된 표본은 검증할 수 없습니다.")]})
            continue
        key = (sample.get("sentence", ""), frozenset(sample.get("cites", [])))
        if key in duplicate_check_keys:
            records.append({"sample_index": sample_index, "sentence": sample["sentence"],
                            "cites": sample.get("cites", []), "status": "unchecked",
                            "issues": [_issue("duplicate_check", "중복된 check가 있어 어느 판정도 채택하지 않았습니다.")]})
            continue
        response_item = response_by_key.get(key)
        if response_item is None:
            records.append({"sample_index": sample_index, "sentence": sample.get("sentence", ""),
                            "cites": sample.get("cites", []), "status": "unchecked",
                            "issues": [_issue("semantic_check_missing", "이 표본의 의미 check가 없습니다.")]})
            continue
        check_index, check = response_item
        check_issues = []
        if set(check) != {"sentence", "cites", "supported", "reason", "atoms"}:
            check_issues.append(_issue("check_fields_invalid", "check 필드는 strict schema와 정확히 일치해야 합니다.",
                                       check_index=check_index))
        if len(check.get("cites", [])) != len(set(check.get("cites", []))):
            check_issues.append(_issue("duplicate_parent_cite", "부모 check의 cites가 중복됐습니다.", check_index=check_index))
        if not isinstance(check.get("supported"), bool) or not isinstance(check.get("reason"), str):
            check_issues.append(_issue("legacy_fields_invalid", "supported는 bool, reason은 문자열이어야 합니다.",
                                       check_index=check_index))
        raw_atoms = check.get("atoms")
        if not isinstance(raw_atoms, list) or not raw_atoms:
            check_issues.append(_issue("atoms_missing", "비어 있지 않은 atoms 배열이 필요합니다. 누락된 분해는 unchecked입니다.",
                                       check_index=check_index))
            raw_atoms = []
        atom_quotes = set()
        validated_atoms = []
        for atom_index, atom in enumerate(raw_atoms):
            quote = atom.get("quote") if isinstance(atom, dict) else None
            if isinstance(quote, str) and quote in atom_quotes:
                check_issues.append(_issue("duplicate_atom", "같은 atom quote가 중복됐습니다.",
                                           check_index=check_index, atom_index=atom_index))
                continue
            if isinstance(quote, str):
                atom_quotes.add(quote)
            validated, atom_issues = _validate_atom(atom, sample["sentence"], set(sample.get("cites", [])), valid_sources,
                                                     valid_original_sources, check_index, atom_index)
            check_issues.extend(atom_issues)
            if validated is not None:
                validated_atoms.append(validated)

        if check_issues or len(validated_atoms) != len(raw_atoms):
            records.append({"sample_index": sample_index, "sentence": sample["sentence"], "cites": sample.get("cites", []),
                            "status": "unchecked", "model_asserted_atom_count": len(raw_atoms),
                            "validated_atoms": validated_atoms, "issues": check_issues})
            continue

        verdicts = {atom["verdict"] for atom in validated_atoms}
        required = _substantive_indices(sample["sentence"])
        covered = set()
        for atom_value in validated_atoms:
            covered.update(range(atom_value["char_start"], atom_value["char_end"]))
        covered_substantive = required & covered
        uncovered = required - covered
        coverage_complete = bool(required) and not uncovered
        if "contradicted" in verdicts:
            overall_verdict = "contradicted"
        elif "insufficient" in verdicts or check["supported"] is False or not coverage_complete:
            overall_verdict = "insufficient"
        else:
            overall_verdict = "supported"
        safe_supported = bool(check["supported"] and overall_verdict == "supported"
                              and coverage_complete and validated_atoms
                              and all(atom["verdict"] == "supported" for atom in validated_atoms))
        record_issues = []
        if not coverage_complete:
            record_issues.append(_issue("substantive_coverage_incomplete",
                                        "atom exact spans가 부모 문장의 모든 실질 문자를 덮지 않아 overall을 insufficient로 낮췄습니다."))
        legacy = {"sentence": sample["sentence"], "cites": sample.get("cites", []),
                  "supported": safe_supported, "reason": check["reason"]}
        if "line" in sample:
            legacy["line"] = sample["line"]
        legacy_checks.append(legacy)
        records.append({
            "sample_index": sample_index,
            "sentence": sample["sentence"],
            "cites": sample.get("cites", []),
            "status": "validated",
            "overall_verdict": overall_verdict,
            "legacy_supported": safe_supported,
            "model_asserted_atom_count": len(validated_atoms),
            "validated_atoms": validated_atoms,
            "deterministic_character_coverage": {
                "covered_substantive_chars": len(covered_substantive),
                "required_substantive_chars": len(required),
                "ratio": len(covered_substantive) / max(1, len(required)),
                "complete": coverage_complete,
                "uncovered_fragments": _uncovered_fragments(sample["sentence"], uncovered),
                "is_semantic_coverage": False,
                "markdown_syntax_excluded": True,
                "meaning_bearing_symbols_required": "comparison_range_arithmetic_unit_symbols",
            },
            "issues": record_issues,
        })

    validated_count = sum(record["status"] == "validated" for record in records)
    return {
        "checks": legacy_checks,
        "semantic": {
            "records": records,
            "issues": global_issues,
            "source_inputs": source_inputs,
            "original_source_inputs": ({source_id: {"sha256": _sha256(text), "chars": len(text)}
                                         for source_id, text in sorted(valid_original_sources.items())}
                                        if valid_original_sources is not None else None),
            "sample_count": len(samples),
            "validated_count": validated_count,
            "unchecked_count": len(samples) - validated_count,
            "scope": {
                "mode": "opt_in_same_call_adapter",
                "source_text_scope": "exact_checker_inputs_only",
                "original_source_binding": original_sources is not None,
                "atom_decomposition": "model_asserted",
                "semantic_decomposition_complete": False,
                "factual_accuracy_truth_guarantee": False,
                "mock_outputs_are_real_judgments": False,
                "deterministic_validation": "exact_ids_substrings_hashes_offsets",
            },
        },
    }
