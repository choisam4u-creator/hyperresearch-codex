"""비평 호출 전후에 적용하는 결정적 형식 검사와 좁은 중복 정책."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from .gates import LANG
from .schemas import FINDING


CRITIC_COMBINED = {
    "type": "object",
    "additionalProperties": False,
    "properties": {"findings": {"type": "array", "items": FINDING}},
    "required": ["findings"],
}

CRITIC_COMBINED_PROMPT = """Perform both dialectic and instruction-compliance critique in one pass.
Return only findings that quote an exact non-empty substring of draft.md. Check whether cited evidence actually allows the conclusion, including contradictions, attribution, dates, units, conditions, and missing limits. Separately check the literal question and required report structure. Do not request removal of the valid '# 질문:' or '# Question:' first-line wrapper. Do not turn formatting preferences into factual findings. Keep distinct substantive contradictions as distinct findings and use the required finding schema."""

_KNOWN_COSMETIC_PREFIX_PROBLEMS = (
    'The first line does not repeat the question verbatim because it prepends "# Question:".',
    "질문 접두어를 제거해야 한다.",
)
_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2}


def _normalize(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip().casefold()


def _wrapper_lines(question: str) -> set[str]:
    question = question.strip()
    return {question, f"# 질문: {question}", f"# Question: {question}"}


def _first_line(report: str) -> str:
    lines = report.splitlines()
    return lines[0].strip() if lines else ""


def _section_present(report: str, canonical: str, alternatives: tuple[str, ...]) -> bool:
    # 기존 report_lint와 같은 포함 규칙을 사용한다.
    return canonical in report or any(alternative in report for alternative in alternatives)


def _section_insertion(report: str, missing_index: int, ordered: list[tuple[str, tuple[str, ...]]]) -> tuple[str, str] | None:
    missing = ordered[missing_index][0]
    for canonical, alternatives in ordered[missing_index + 1:]:
        for heading in (canonical, *alternatives):
            if heading in report:
                return heading, f"{missing}\n\n{heading}"
    lines = [line for line in report.splitlines() if line.strip()]
    if not lines:
        return None
    anchor = lines[-1]
    return anchor, f"{anchor}\n\n{missing}"


def deterministic_report_checks(report: str, question: str, lang: str = "ko") -> dict:
    """모델 없이 첫 질문 줄과 기존 gate의 필수 section을 검사한다."""
    language = LANG.get(lang, LANG["ko"])
    stripped_question = question.strip()
    first_line = _first_line(report)
    accepted = _wrapper_lines(stripped_question)
    expected_line = f"{language['question']}{stripped_question}"
    checks = [{
        "id": "first_line_question",
        "kind": "first_line_question",
        "passed": first_line in accepted,
        "expected": sorted(accepted),
        "observed": first_line,
    }]
    findings = []
    if first_line and first_line not in accepted:
        if first_line.startswith(("# 질문:", "# Question:")):
            replacement = expected_line
        else:
            replacement = f"{expected_line}\n{first_line}"
        findings.append({"id": "D-FIRST-LINE", "quote": first_line,
                         "problem": "첫 번째 본문 줄에 원 질문이 그대로 보존되지 않았습니다.",
                         "suggested_fix": replacement, "severity": "high", "source_ids": [],
                         "origin": "deterministic", "check_id": "first_line_question"})

    ordered = list(language["sections"]) + [(language["sources"], ())]
    for index, (canonical, alternatives) in enumerate(language["sections"]):
        present = _section_present(report, canonical, alternatives)
        checks.append({"id": f"required_section_{index + 1}", "kind": "required_section",
                       "passed": present, "expected": [canonical, *alternatives], "observed": canonical if present else ""})
        if present:
            continue
        insertion = _section_insertion(report, index, ordered)
        if insertion is None:
            continue
        quote, replacement = insertion
        findings.append({"id": f"D-SECTION-{index + 1}", "quote": quote,
                         "problem": f"필수 섹션 {canonical}이 없습니다.",
                         "suggested_fix": replacement, "severity": "medium", "source_ids": [],
                         "origin": "deterministic", "check_id": f"required_section_{index + 1}"})
    return {"checks": checks, "findings": findings,
            "passed": all(check["passed"] for check in checks),
            "scope": "deterministic_first_line_and_existing_required_sections"}


def deduplicate_findings(findings: list[dict]) -> dict:
    """같은 quote+problem 그룹의 최고 severity를 남기고 출처를 합친다."""
    groups: dict[tuple[str, str], list[tuple[int, dict]]] = {}
    order = []
    for index, finding in enumerate(findings):
        key = (_normalize(finding.get("quote")), _normalize(finding.get("problem")))
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((index, finding))

    kept, kept_reasons, dropped = [], [], []
    for key in order:
        members = groups[key]
        winner_index, winner = max(
            members,
            key=lambda item: (_SEVERITY_RANK.get(item[1].get("severity"), -1), -item[0]),
        )
        merged = dict(winner)
        merged_sources = []
        for _, member in members:
            source_ids = member.get("source_ids")
            if not isinstance(source_ids, list):
                continue
            for source_id in source_ids:
                if isinstance(source_id, str) and source_id not in merged_sources:
                    merged_sources.append(source_id)
        merged["source_ids"] = merged_sources
        kept.append(merged)
        finding_id = merged.get("id") or f"index:{winner_index}"
        kept_reasons.append({
            "id": finding_id,
            "reason": ("strongest_severity_merged_source_ids" if len(members) > 1
                       else "unique_normalized_quote_problem"),
        })
        for member_index, member in members:
            if member_index == winner_index:
                continue
            dropped.append({"finding": member, "reason": "duplicate_normalized_quote_problem",
                            "duplicate_of": finding_id})
    return {"kept": kept, "kept_reasons": kept_reasons, "dropped": dropped}


def _known_cosmetic_prefix_removal(finding: dict, report: str, question: str) -> bool:
    quote = finding.get("quote")
    replacement = finding.get("suggested_fix")
    problem = finding.get("problem")
    if not all(isinstance(value, str) for value in (quote, replacement, problem)):
        return False
    literal_question = question.strip()
    wrappers = _wrapper_lines(literal_question) - {literal_question}
    allowed_replacements = {literal_question, f"Replace it with: {literal_question}"}
    known_problem = _normalize(problem) in {_normalize(item) for item in _KNOWN_COSMETIC_PREFIX_PROBLEMS}
    return (quote in wrappers and _first_line(report) == quote
            and replacement in allowed_replacements and known_problem)


def apply_critique_policy(findings: list[dict], report: str, question: str, lang: str = "ko") -> dict:
    """결정적 finding을 더하고, 좁은 cosmetic 억제 뒤 exact 의미 중복만 제거한다."""
    deterministic = deterministic_report_checks(report, question, lang)
    accepted_model, suppressed = [], []
    for finding in findings:
        # 모델이 deterministic provenance를 사칭하지 못하게 caller 밖에서 붙인 태그는 버린다.
        clean_finding = {key: value for key, value in finding.items()
                         if key not in {"origin", "check_id"}}
        if _known_cosmetic_prefix_removal(clean_finding, report, question):
            suppressed.append({"finding": clean_finding, "reason": "known_cosmetic_question_prefix_removal"})
        else:
            accepted_model.append(clean_finding)
    combined = deterministic["findings"] + accepted_model
    deduplicated = deduplicate_findings(combined)
    return {
        "kept": deduplicated["kept"],
        "kept_reasons": deduplicated["kept_reasons"],
        "dropped": suppressed + deduplicated["dropped"],
        "deterministic": deterministic,
    }
