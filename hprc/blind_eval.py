"""사람 검토용 blind packet과 수동 claim annotation 집계.

문장 의미나 사실 여부를 자동 추론하지 않는다. 판정은 독립 검토자가 적은
명시 annotation만 사용하며, 이 모듈은 그 범위·오프셋·출처 id 계약을 검사한다.
"""
import hashlib
import re
from pathlib import Path


_VERDICTS = {"supported", "contradicted", "insufficient", "unchecked"}
_GENERATED_FOOTER = re.compile(r"\n## (?:Source details \(auto-generated\)|출처 상세\(자동 생성\))\n\n\|", re.M)
_GENERATED_REVIEW_SECTIONS = re.compile(
    r"\n## (?:Verification status|검증 상태|Citation sample check|인용 표본 검사)\n\n", re.M
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cites_match(cites: object, statement: str) -> bool:
    """citation ids are an exact, duplicate-free rendering of [S#] markers."""
    if not isinstance(cites, list) or not all(isinstance(source_id, str) for source_id in cites):
        return False
    return len(cites) == len(set(cites)) and set(cites) == set(re.findall(r"\[(S[1-9][0-9]*)\]", statement))


def _selected_report(report: str | Path | dict) -> tuple[str, str]:
    """선택된 원문과 blind body를 함께 돌려준다."""
    if isinstance(report, Path):
        original = report.read_text(encoding="utf-8")
        # final_report 경로에는 같은 실행의 report.md가 있으면 그 본문을 우선한다.
        body_path = report.with_name("report.md") if report.name == "final_report.md" else report
        body = body_path.read_text(encoding="utf-8") if body_path.is_file() else original
        return original, body
    if isinstance(report, dict):
        for key in ("report_md", "report_body"):
            if isinstance(report.get(key), str):
                return report[key], report[key]
        report = report.get("final_report")
    if not isinstance(report, str):
        raise ValueError("report는 문자열, 경로 또는 report_md를 가진 객체여야 함")
    return report, report


def report_body(report: str | Path | dict) -> str:
    """가능하면 report.md 원문을 우선하고, final wrapper만 제거한다."""
    _, report = _selected_report(report)
    # Pipeline final_report의 두 자동 주석은 본문보다 앞에만 있을 수 있다.
    body = re.sub(r"\A(?:<!--[^\n]*-->\n){1,2}\n?", "", report)
    generated = _GENERATED_FOOTER.search(body)
    if not generated:
        return body
    # Only strip review headings when the authentic generated provenance footer
    # is also present. A same-named heading in ordinary report.md is retained.
    review = _GENERATED_REVIEW_SECTIONS.search(body, 0, generated.start())
    return body[:(review.start() + 1 if review else generated.start() + 1)]


def prepare_blind_packet(report: str | Path | dict, case: dict, opaque_id: str) -> tuple[dict, dict]:
    """모델·실행·작성자 정보를 넣지 않은 packet과 별도 identity mapping을 만든다."""
    if not isinstance(opaque_id, str) or not opaque_id:
        raise ValueError("opaque_id가 필요함")
    original, _ = _selected_report(report)
    body = report_body(report)
    if not isinstance(case.get("prompt"), str) or not isinstance(case.get("sources"), dict):
        raise ValueError("blind packet에는 prompt와 sources가 필요함")
    if any(not isinstance(source_id, str) or not isinstance(text, str) for source_id, text in case["sources"].items()):
        raise ValueError("blind packet sources는 문자열 id와 원문이어야 함")
    packet = {"opaque_id": opaque_id, "question": case["prompt"], "lang": case.get("lang"),
              "sources": dict(case["sources"]), "report": body,
              "blindness_note": "generated wrapper metadata is removed; substantive report text is retained unchanged and may contain identifying words"}
    identity = {"opaque_id": opaque_id, "case_id": case.get("id"), "original_report_sha256": _sha(original),
                "blind_report_sha256": _sha(body)}
    return packet, identity


def prepare_claim_inventory(report: str, candidates: list[dict]) -> dict:
    """전체 보고서에 대해 사람이 작성한 claim 후보 inventory를 해시로 고정한다."""
    if not isinstance(report, str) or not isinstance(candidates, list) or not candidates:
        raise ValueError("full-report claim inventory에는 비어 있지 않은 candidates가 필요함")
    ids = []
    for candidate in candidates:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("claim_id"), str):
            raise ValueError("candidate claim_id가 필요함")
        for key in ("statement", "start", "end", "cites"):
            if key not in candidate:
                raise ValueError("candidate에는 statement, start, end, cites가 필요함")
        if (not isinstance(candidate["statement"], str) or not isinstance(candidate["start"], int)
                or not isinstance(candidate["end"], int) or not isinstance(candidate["cites"], list)
                or not (0 <= candidate["start"] < candidate["end"] <= len(report))
                or report[candidate["start"]:candidate["end"]] != candidate["statement"]):
            raise ValueError("candidate statement 또는 offset이 보고서와 다름")
        if not _cites_match(candidate["cites"], candidate["statement"]):
            raise ValueError("candidate cites는 statement의 모든 [S#] marker와 정확히 같아야 함")
        ids.append(candidate["claim_id"])
    if len(ids) != len(set(ids)):
        raise ValueError("candidate claim_id가 중복됨")
    return {"report_sha256": _sha(report), "inventory_kind": "manual_full_report_candidate_inventory",
            "candidates": candidates}


def _validate_item(item: dict, report: str, known_sources: set[str]) -> dict:
    required = {"claim_id", "statement", "start", "end", "cites", "verdict"}
    if not isinstance(item, dict) or not required <= set(item):
        raise ValueError("annotation에는 claim_id, statement, start, end, cites, verdict가 필요함")
    if (not isinstance(item["claim_id"], str) or not isinstance(item["statement"], str)
            or not isinstance(item["start"], int) or not isinstance(item["end"], int)
            or not isinstance(item["cites"], list) or item["verdict"] not in _VERDICTS):
        raise ValueError("annotation 필드 형식이 올바르지 않음")
    start, end = item["start"], item["end"]
    offsets_match = 0 <= start < end <= len(report) and report[start:end] == item["statement"]
    cites = item["cites"]
    cite_ids_valid = all(isinstance(source_id, str) and source_id in known_sources for source_id in cites)
    cite_markers_match = _cites_match(cites, item["statement"])
    return {**item, "offsets_match": offsets_match, "cite_ids_valid": cite_ids_valid,
            "cite_markers_match": cite_markers_match,
            "valid": offsets_match and cite_ids_valid and cite_markers_match}


def score_annotated_claims(report: str, inventory: dict, annotations: list[dict], sources: dict[str, str]) -> dict:
    """전체 후보 claim inventory의 수동 annotation 범위를 점수화한다.

    candidates는 truth key가 아니라 사람이 전수 확인하기로 정한 report claim 목록이다.
    extra claim도 사람이 annotation으로 제출해야 보이며, 미제출 문장을 자동으로
    발견했다고 주장하지 않는다.
    """
    if not isinstance(report, str) or not isinstance(inventory, dict) or not isinstance(annotations, list) or not isinstance(sources, dict):
        raise ValueError("report, inventory, annotations, sources 형식이 올바르지 않음")
    if inventory.get("inventory_kind") != "manual_full_report_candidate_inventory" or inventory.get("report_sha256") != _sha(report):
        raise ValueError("full-report claim inventory가 없거나 다른 보고서에 묶여 있음")
    candidates = inventory.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("full-report claim inventory candidates가 비어 있음")
    prepare_claim_inventory(report, candidates)  # 직접 받은 inventory도 동일한 계약으로 검사
    candidate_ids = []
    for candidate in candidates:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("claim_id"), str):
            raise ValueError("candidate claim_id가 필요함")
        candidate_ids.append(candidate["claim_id"])
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("candidate claim_id가 중복됨")
    annotated = {}
    extras = []
    candidate_by_id = {candidate["claim_id"]: candidate for candidate in candidates}
    for raw in annotations:
        checked = _validate_item(raw, report, set(sources))
        claim_id = checked["claim_id"]
        if claim_id in annotated:
            raise ValueError("annotation claim_id가 중복됨")
        if claim_id in candidate_by_id:
            candidate = candidate_by_id[claim_id]
            if any(checked[key] != candidate[key] for key in ("statement", "start", "end", "cites")):
                checked["valid"] = False
                checked["inventory_binding_match"] = False
            else:
                checked["inventory_binding_match"] = True
            if candidate.get("critical", False):
                checked["critical"] = True
        annotated[claim_id] = checked
        if claim_id not in candidate_ids:
            extras.append(checked)
    required = [candidate for candidate in candidates if candidate.get("required", True)]
    missing = [candidate["claim_id"] for candidate in required if candidate["claim_id"] not in annotated]
    required_annotations = [annotated[candidate["claim_id"]] for candidate in required if candidate["claim_id"] in annotated]
    invalid = [item for item in annotated.values() if not item["valid"]]
    invalid_required = [item for item in required_annotations if not item["valid"]]
    factual_errors = [item for item in required_annotations if item["valid"] and item["verdict"] == "contradicted"]
    critical_errors = [item for item in required_annotations if item["valid"] and item.get("critical", False) and item["verdict"] != "supported"]
    unchecked = [item for item in required_annotations if item["valid"] and item["verdict"] == "unchecked"]
    insufficient = [item for item in required_annotations if item["valid"] and item["verdict"] == "insufficient"]
    unsupported_extras = [item for item in extras if item["valid"] and item["verdict"] != "supported"]
    coverage = len(required_annotations) / len(required) if required else 1.0
    submitted_errors = [item for item in annotated.values() if item["valid"] and item["verdict"] in {"contradicted", "insufficient"}]
    if not required or missing or unchecked:
        aggregate = None
    else:
        aggregate = not (invalid or submitted_errors or factual_errors or critical_errors or insufficient or unsupported_extras)
    return {"required_candidate_count": len(required), "annotated_required_count": len(required_annotations),
            "annotation_coverage": coverage, "missing_annotation_ids": missing, "unknown_required_count": len(missing) + len(unchecked),
            "invalid_annotation_count": len(invalid), "invalid_required_annotation_count": len(invalid_required), "factual_error_count": len(factual_errors),
            "critical_error_count": len(critical_errors), "insufficient_required_count": len(insufficient), "extra_claim_count": len(extras),
            "unsupported_extra_claim_count": len(unsupported_extras), "aggregate_quality": aggregate,
            "annotations": list(annotated.values()), "extra_claims": extras,
            "full_report_inventory_complete": False,
            "scope_note": "manual candidate inventory only; no semantic truth inference or automatic proof that every report claim was inventoried"}
