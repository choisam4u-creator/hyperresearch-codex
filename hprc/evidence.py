"""최종 보고서의 주장 후보와 원문 근거 위치를 잇는 결정적 원장.

이 모듈은 사실성 판정기가 아니다. 보고서의 prose/list/table 항목을 빠짐없이
검토 후보로 만들고, 인용된 불변 노트에서 원문 구간을 골라 사람이 추적할 수
있게 한다. 지지/반박 관계는 문자열 겹침으로 추정하지 않는다.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable


_CITE = re.compile(r"\[S\d+\]")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
_LIST = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+")
_TABLE_SEPARATOR = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*$")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?。\]])\s+(?!\[S\d+\]|\((?:판단|judgment)\))", re.IGNORECASE)
_WORD = re.compile(r"[A-Za-z0-9가-힣]{2,}")
_QUOTE = re.compile(r'"[^"\n]+"|“[^”\n]+”')
_UNKNOWN = "unknown"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _source_heading(line: str) -> bool:
    heading = _HEADING.sub("", line).strip().lower()
    return heading in {"출처", "출처 목록", "출처 상세(자동 생성)", "sources", "source details (auto-generated)"}


def _iter_report_blocks(report: str) -> Iterable[tuple[str, int, int, int]]:
    """(구조, 시작, 끝, 행) 블록. 구간은 report 원문 기준이다."""
    lines = report.splitlines(keepends=True)
    offset = 0
    prose_start: int | None = None
    prose_line = 0
    prose_end = 0
    fenced = False
    in_sources = False

    def flush():
        nonlocal prose_start
        if prose_start is not None:
            value = ("prose", prose_start, prose_end, prose_line)
            prose_start = None
            return value
        return None

    for line_no, raw in enumerate(lines, 1):
        line_start, line_end = offset, offset + len(raw)
        offset = line_end
        stripped = raw.strip()
        if stripped.startswith(("```", "~~~")):
            block = flush()
            if block:
                yield block
            fenced = not fenced
            continue
        if fenced:
            continue
        if _HEADING.match(raw):
            block = flush()
            if block:
                yield block
            in_sources = _source_heading(raw)
            continue
        if in_sources:
            continue
        if not stripped or stripped.startswith("<!--"):
            block = flush()
            if block:
                yield block
            continue
        structure = "table" if stripped.startswith("|") else "list" if _LIST.match(raw) else "prose"
        if structure != "prose":
            block = flush()
            if block:
                yield block
            if structure == "table" and _TABLE_SEPARATOR.match(stripped):
                continue
            yield structure, line_start, line_end, line_no
            continue
        if prose_start is None:
            prose_start, prose_line = line_start, line_no
        prose_end = line_end
    block = flush()
    if block:
        yield block


def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    # citation_sampling의 원문 문장과 맞도록 들여쓰기/후행 공백은 보존하고
    # splitlines가 제거하는 행 종료 문자만 제외한다.
    while end > start and text[end - 1] in "\r\n":
        end -= 1
    return start, end


def _classification(statement: str, judgment_markers: tuple[str, ...]) -> str:
    if any(marker and marker in statement for marker in judgment_markers):
        return "judgment"
    if _QUOTE.search(statement):
        return "direct_quote"
    return "fact_candidate"


def _sentence_spans(block: str) -> list[tuple[int, int]]:
    starts = [0]
    ends = []
    for match in _SENTENCE_BREAK.finditer(block):
        ends.append(match.start())
        starts.append(match.end())
    ends.append(len(block))
    return list(zip(starts, ends))


def report_candidates(report: str, judgment_markers: tuple[str, ...] = ("(판단)", "(judgment)")) -> dict:
    """인용 유무와 관계없이 보고서의 검토 후보를 원문 구간과 함께 반환한다.

    분류는 보수적인 구조 휴리스틱이다. ``fact_candidate``는 사실 주장이라는
    의미 판정이 아니라 검토 대상이라는 뜻이다.
    """
    candidates: list[dict[str, Any]] = []
    for structure, block_start, block_end, line in _iter_report_blocks(report):
        block = report[block_start:block_end]
        spans = [(0, len(block))] if structure in {"list", "table"} else _sentence_spans(block)
        for local_start, local_end in spans:
            start, end = _trim_span(report, block_start + local_start, block_start + local_end)
            if start == end:
                continue
            statement = report[start:end]
            # 마크다운 장식/인용 표지만 남은 항목은 후보가 아니다.
            content = _CITE.sub("", statement)
            content = re.sub(r"[\s|*`_~>\-–—:]", "", content)
            if not content:
                continue
            cites = list(dict.fromkeys(_CITE.findall(statement)))
            candidates.append({
                "claim_id": f"R{len(candidates) + 1:04d}",
                "statement": statement,
                "statement_sha256": sha256_text(statement),
                "line": line + report[block_start:start].count("\n"),
                "char_start": start,
                "char_end": end,
                "structure": structure,
                "classification": _classification(statement, judgment_markers),
                "direct_quotes": [value[1:-1] for value in _QUOTE.findall(statement)],
                "citations": [cite[1:-1] for cite in cites],
                "applicability_conditions": {"status": _UNKNOWN, "items": []},
            })
    return {
        "candidates": candidates,
        "scope": {
            "inventory": "markdown_prose_list_table_candidates_v1",
            "includes_uncited": True,
            "semantic_extraction_complete": False,
        },
    }


def source_paragraphs(text: str) -> list[dict]:
    """원문을 바꾸지 않고 빈 줄 경계의 문단과 정확한 문자 구간을 반환한다."""
    paragraphs = []
    boundaries = [0]
    for separator in re.finditer(r"\n[ \t]*\n", text):
        boundaries.extend((separator.start(), separator.end()))
    boundaries.append(len(text))
    for index in range(0, len(boundaries) - 1, 2):
        start, end = boundaries[index], boundaries[index + 1]
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start == end:
            continue
        paragraph = text[start:end]
        paragraphs.append({
            "paragraph_id": f"P{len(paragraphs) + 1:04d}",
            "char_start": start,
            "char_end": end,
            "text": paragraph,
            "text_sha256": sha256_text(paragraph),
        })
    return paragraphs


def _terms(text: str) -> set[str]:
    return {term.lower() for term in _WORD.findall(_CITE.sub("", text))}


def _select_snippets(text: str, statement: str, limit: int = 2) -> list[dict]:
    """위치 후보만 고른다. 점수는 source relation 판정에 사용하지 않는다."""
    paragraphs = source_paragraphs(text)
    query = _terms(statement)
    quote_parts = [value[1:-1] for value in _QUOTE.findall(statement)]
    scored = []
    for index, paragraph in enumerate(paragraphs):
        para_text = paragraph["text"]
        overlap = len(query & _terms(para_text))
        exact_quote = any(quote in para_text for quote in quote_parts)
        numeric = len(set(re.findall(r"\d+(?:[.,]\d+)*", statement)) & set(re.findall(r"\d+(?:[.,]\d+)*", para_text)))
        scored.append((bool(exact_quote), numeric, overlap, -index, paragraph))
    useful = [item for item in scored if item[0] or item[1] or item[2]]
    if not useful:
        useful = [item for item in scored if len(item[4]["text"].strip()) >= 20][:1]
    return [dict(item[4], selection_basis="location_candidate_only")
            for item in sorted(useful, reverse=True, key=lambda item: item[:4])[:limit]]


def _normalized_source(source_alias: str, source: Any) -> dict:
    if isinstance(source, str):
        text, metadata = source, {}
    else:
        text = str(source.get("text", ""))
        metadata = dict(source.get("metadata", {}))
        for key, value in source.items():
            if key not in {"text", "metadata"}:
                metadata.setdefault(key, value)
    actual_hash = sha256_text(text)
    recorded_hash = metadata.get("sha256") or metadata.get("content_sha256")
    return {
        "source_alias": source_alias,
        "note_id": metadata.get("id") or metadata.get("note_id") or _UNKNOWN,
        "content_sha256": actual_hash,
        "recorded_content_sha256": recorded_hash or _UNKNOWN,
        "recorded_hash_matches": (recorded_hash == actual_hash) if recorded_hash else None,
        "text": text,
        "provenance": {
            "url": metadata.get("final_url") or metadata.get("url") or _UNKNOWN,
            "canonical_url": metadata.get("canonical") or _UNKNOWN,
            "title": metadata.get("title") or _UNKNOWN,
            "source_type": metadata.get("source_type") or _UNKNOWN,
            "content_scope": metadata.get("content_scope") or _UNKNOWN,
            "published_at": metadata.get("published") or metadata.get("published_at") or _UNKNOWN,
            "retrieved_at": metadata.get("fetched_at") or metadata.get("retrieved_at") or _UNKNOWN,
            "independence_group": metadata.get("cluster") or metadata.get("independence_group") or _UNKNOWN,
            "retraction_status": metadata.get("retraction_status") or _UNKNOWN,
            "correction_status": metadata.get("correction_status") or _UNKNOWN,
        },
    }


def _check_index(citation_record: dict | None) -> tuple[dict, dict]:
    info = {"status": "not_supplied", "snapshot_sha256": _UNKNOWN}
    if not citation_record:
        return {}, info
    checked_report = citation_record.get("report")
    expected_hash = citation_record.get("report_sha256")
    if not isinstance(checked_report, str) or not expected_hash:
        return {}, {"status": "snapshot_or_hash_missing", "snapshot_sha256": expected_hash or _UNKNOWN}
    actual_hash = sha256_text(checked_report)
    if actual_hash != expected_hash:
        return {}, {"status": "snapshot_hash_mismatch", "snapshot_sha256": expected_hash,
                    "actual_snapshot_sha256": actual_hash}
    original = report_candidates(checked_report)["candidates"]
    exact_candidates = {(item["statement"], frozenset(item["citations"])) for item in original}
    index = {}
    unmatched = 0
    for check in citation_record.get("checks", []):
        key = (check.get("sentence", ""), frozenset(check.get("cites", [])))
        if key not in exact_candidates or key in index:
            unmatched += 1
            continue
        verdict = check.get("verdict")
        if verdict not in {"supported", "contradicted", "insufficient", "unchecked"}:
            verdict = "supported" if check.get("supported") is True else "insufficient" if check.get("supported") is False else "unchecked"
        index[key] = {"status": verdict, "reason": check.get("reason") or _UNKNOWN,
                      "snapshot_sha256": actual_hash}
    return index, {"status": "matched", "snapshot_sha256": actual_hash, "unmatched_check_count": unmatched}


def build_evidence_ledger(report: str, sources: dict[str, Any], *, citation_record: dict | None = None) -> dict:
    """최종 보고서 후보 원장을 만든다. 모델 호출이나 의미 관계 추론은 하지 않는다."""
    inventory = report_candidates(report)
    normalized = {alias: _normalized_source(alias, source) for alias, source in sorted(sources.items())}
    checks, check_meta = _check_index(citation_record)
    claims = []
    for candidate in inventory["candidates"]:
        links = []
        for alias in candidate["citations"]:
            source = normalized.get(alias)
            if source is None:
                links.append({"source_alias": alias, "note_id": _UNKNOWN, "source_content_sha256": _UNKNOWN,
                              "relation": "unchecked", "relation_basis": "requires_adjudication", "snippets": []})
                continue
            links.append({
                "source_alias": alias,
                "note_id": source["note_id"],
                "source_content_sha256": source["content_sha256"],
                "relation": "unchecked",
                "relation_basis": "requires_adjudication",
                "snippets": _select_snippets(source["text"], candidate["statement"]),
            })
        key = (candidate["statement"], frozenset(candidate["citations"]))
        adjudication = checks.get(key, {"status": "unchecked", "reason": _UNKNOWN,
                                        "snapshot_sha256": check_meta.get("snapshot_sha256", _UNKNOWN)})
        complete_links = bool(links) and all(
            link["note_id"] != _UNKNOWN and link["snippets"]
            and normalized[link["source_alias"]]["recorded_hash_matches"] is not False
            for link in links if link["source_alias"] in normalized
        ) and all(link["source_alias"] in normalized for link in links)
        if candidate["classification"] == "judgment" and not candidate["citations"]:
            traceability = "not_applicable"
        elif not candidate["citations"]:
            traceability = "missing_citation"
        elif complete_links:
            traceability = "traceable"
        else:
            traceability = "incomplete"
        claims.append({**candidate, "traceability_status": traceability,
                       "verification": adjudication, "evidence_links": links})
    source_records = [{key: value for key, value in source.items() if key != "text"} for source in normalized.values()]
    return {
        "schema_version": 1,
        "report": {"sha256": sha256_text(report), "chars": len(report)},
        "scope": {**inventory["scope"], "source_relation_inferred_from_text": False,
                  "factual_accuracy_verified": False},
        "citation_record": check_meta,
        "sources": source_records,
        "claims": claims,
    }


def validate_evidence_ledger(ledger: dict, sources: dict[str, Any], report: str | None = None) -> list[dict]:
    """원장에 기록된 statement/snippet 구간과 해시가 실제 입력에 맞는지 검사한다."""
    issues = []
    normalized = {alias: _normalized_source(alias, source) for alias, source in sources.items()}
    if report is not None and ledger.get("report", {}).get("sha256") != sha256_text(report):
        issues.append({"kind": "report_hash_mismatch"})
    for claim in ledger.get("claims", []):
        if report is not None:
            start, end = claim.get("char_start"), claim.get("char_end")
            valid_bounds = isinstance(start, int) and isinstance(end, int) and 0 <= start <= end <= len(report)
            if not valid_bounds or report[start:end] != claim.get("statement"):
                issues.append({"kind": "statement_location_mismatch", "claim_id": claim.get("claim_id")})
            elif sha256_text(report[start:end]) != claim.get("statement_sha256"):
                issues.append({"kind": "statement_hash_mismatch", "claim_id": claim.get("claim_id")})
        for link in claim.get("evidence_links", []):
            alias = link.get("source_alias")
            source = normalized.get(alias)
            if source is None:
                if link.get("snippets"):
                    issues.append({"kind": "unknown_source_has_snippet", "claim_id": claim.get("claim_id"), "source_alias": alias})
                continue
            if link.get("source_content_sha256") != source["content_sha256"]:
                issues.append({"kind": "source_hash_mismatch", "claim_id": claim.get("claim_id"), "source_alias": alias})
            if link.get("note_id") != source["note_id"]:
                issues.append({"kind": "note_id_mismatch", "claim_id": claim.get("claim_id"), "source_alias": alias})
            if source["recorded_hash_matches"] is False:
                issues.append({"kind": "recorded_source_hash_mismatch", "claim_id": claim.get("claim_id"), "source_alias": alias})
            text = source["text"]
            for snippet in link.get("snippets", []):
                start, end = snippet.get("char_start"), snippet.get("char_end")
                valid_bounds = isinstance(start, int) and isinstance(end, int) and 0 <= start <= end <= len(text)
                if not valid_bounds or text[start:end] != snippet.get("text"):
                    issues.append({"kind": "snippet_location_mismatch", "claim_id": claim.get("claim_id"), "source_alias": alias})
                elif sha256_text(text[start:end]) != snippet.get("text_sha256"):
                    issues.append({"kind": "snippet_hash_mismatch", "claim_id": claim.get("claim_id"), "source_alias": alias})
    return issues
