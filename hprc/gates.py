"""파이썬 게이트: 모델 출력을 믿지 않고 검사한다. 통과 못 하면 다음 단계로 안 간다."""
import difflib
import re

CITE = re.compile(r"\[(S\d+)\]")


class GateError(ValueError):
    pass


def require_keys(obj: dict, keys: list[str], where: str) -> None:
    missing = [k for k in keys if k not in obj]
    if missing:
        raise GateError(f"{where}: 필수 키 없음 {missing}")


def cites_resolve(text: str, known: set[str]) -> list[str]:
    """본문 안의 [Sn] 인용이 전부 실제 출처인지. 모르는 인용 목록을 돌려준다."""
    return sorted({c for c in CITE.findall(text) if c not in known})


def verbatim_prompt(text: str, prompt: str) -> bool:
    return prompt.strip() in text


def critic_quotes_exist(findings: list[dict], draft: str) -> tuple[list[dict], list[dict]]:
    """비평가가 인용한 문장이 실제 초안에 있어야 한다. 없는 건 버린다(지어낸 비평 방지)."""
    kept, dropped = [], []
    for f in findings:
        quote = (f.get("quote") or "").strip()
        if quote and quote in draft:
            kept.append(f)
        else:
            dropped.append(f)
    return kept, dropped


def defer_excerpt_absence_findings(findings: list[dict]) -> tuple[list[dict], list[dict]]:
    """critic이 명시적으로 excerpt_insufficient로 분류한 finding만 검토로 보낸다."""
    actionable, deferred = [], []
    for finding in findings:
        if finding.get("critic") != "instruction" and finding.get("evidence_status") == "excerpt_insufficient":
            deferred.append({**finding, "patch_action": "deferred",
                             "deferral_reason": "excerpt_absence_is_not_source_absence"})
        else:
            actionable.append(finding)
    return actionable, deferred


def apply_hunks(draft: str, hunks: list[dict], max_ratio: float, hunk_max: int,
                preserve_judgment_lang: str | None = None,
                applied_hunks: list[dict] | None = None) -> tuple[str, list[dict]]:
    """find→replace 덩어리를 정확히 일치할 때만 적용. 총 변경 비율이 상한을 넘으면 전부 거부."""
    text, applied, rejected = draft, [], []
    for h in hunks:
        find, repl = h.get("find", ""), h.get("replace", "")
        if not find or find not in text or len(find) > hunk_max or len(repl) > hunk_max:
            rejected.append({**h, "reason": "not_found_or_too_big"})
            continue
        candidate = text.replace(find, repl, 1)
        if preserve_judgment_lang is not None and judgment_sentences(candidate, preserve_judgment_lang) < judgment_sentences(text, preserve_judgment_lang):
            rejected.append({**h, "reason": "judgment_marker_removed"})
            continue
        text = candidate
        applied.append(h)
    ratio = 1 - difflib.SequenceMatcher(None, draft, text).ratio()
    if ratio > max_ratio:
        raise GateError(f"수정 비율 {ratio:.0%} 이 상한 {max_ratio:.0%} 을 넘음 → 전면 재작성으로 보고 거부")
    if applied_hunks is not None:
        applied_hunks.extend(applied)
    return text, rejected


LANG = {
    "ko": {"sections": (("## 답", ()), ("## 근거", ()), ("## 한계", ("## 반대 근거와 한계",))), "sources": "## 출처",
           "judgment": "(판단)", "no_source": "(출처 없음)", "question": "# 질문: "},
    "en": {"sections": (("## Answer", ()), ("## Evidence", ()), ("## Counter-evidence and limits", ("## Limits",))), "sources": "## Sources",
           "judgment": "(judgment)", "no_source": "(no source)", "question": "# Question: "},
}


def report_lint(text: str, prompt: str, known: set[str], lang: str = "ko") -> list[str]:
    L = LANG.get(lang, LANG["ko"])
    problems = []
    if not verbatim_prompt(text, prompt):
        problems.append("verbatim_prompt_missing")
    unknown = cites_resolve(text, known)
    if unknown:
        problems.append("unknown_cites:" + ",".join(unknown))
    if not CITE.search(text):
        problems.append("no_citations")
    for section, alts in L["sections"]:
        if section not in text and not any(a in text for a in alts):
            problems.append(f"section_missing:{section}")
    if re.search(r"https?://", text) and L["sources"] not in text:
        problems.append("bare_url_outside_sources")
    return problems


JUDGMENT = "(판단)"


def judgment_sentences(text: str, lang: str = "ko") -> int:
    return text.count(LANG.get(lang, LANG["ko"])["judgment"])


_BRACKET = re.compile(r"\[([^\[\]]{1,200})\]")


def clean_internal_cites(text: str, lang: str = "ko") -> tuple[str, int]:
    """모델이 [_digest.md; interim/L1.md; S6] 처럼 내부 파일이나 주장 id 를 출처처럼 인용한 것을 [S6] 로 정리한다.
    S 가 하나도 없으면 '(출처 없음)' 표시로 바꾼다. 반환: (정리된 본문, 고친 개수)."""
    no_source = LANG.get(lang, LANG["ko"])["no_source"]
    fixed = 0

    def repl(m):
        nonlocal fixed
        inner = m.group(1)
        if re.fullmatch(r"S\d+", inner):
            return m.group(0)
        if not re.search(r"\.md|interim|_digest|_independence|\bC\d+|gaps|claims", inner):
            return m.group(0)
        ids = re.findall(r"\bS\d+\b", inner)
        fixed += 1
        return "".join(f"[{i}]" for i in dict.fromkeys(ids)) if ids else no_source
    return _BRACKET.sub(repl, text), fixed
