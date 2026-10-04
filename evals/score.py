"""최종 보고서 품질 점수. 각 항목은 0~100이며 높을수록 좋다.

점수는 독자가 경고 없이 보게 되는 문제를 센다. 기준을 바꾸면 docs/QUALITY-LOG.md에
이유를 따로 적는다.
"""
import re
from pathlib import Path

CITE = re.compile(r"\[(S\d+)\]")
MARKERS = {"ko": ("(판단)", "(출처 없음)", "(출처 불일치)"), "en": ("(judgment)", "(no source)", "(source mismatch)")}
HEAD = {
    "ko": {"question": "# 질문: ", "answer": "## 답", "evidence": "## 근거", "limits": ("## 반대 근거와 한계", "## 한계"),
           "sources": "## 출처", "next": "## 다음 행동", "end": "## 검증 상태"},
    "en": {"question": "# Question: ", "answer": "## Answer", "evidence": "## Evidence",
           "limits": ("## Counter-evidence and limits", "## Limits"), "sources": "## Sources", "next": "## Next actions",
           "end": "## Verification status"},
}
METRICS = ("citation_validity", "claim_source_match", "duplicate_sources", "unmarked_unverified", "structure")
LABELS = {"citation_validity": "인용 유효성", "claim_source_match": "주장-출처 일치", "duplicate_sources": "중복 출처 없음",
          "unmarked_unverified": "표시 없는 미검증 주장 없음", "structure": "보고서 구조"}


def model_report(final: str, lang: str) -> str:
    """머리 주석과 자동 생성 검증 절을 떼고 모델이 쓴 보고서 부분만 돌려준다."""
    h = HEAD[lang]
    start = final.find(h["question"])
    text = final[start:] if start >= 0 else final
    end = re.search(rf"(?m)^{re.escape(h['end'])}\s*$", text)
    return text[:end.start()] if end else text


def sections(report: str) -> dict[str, str]:
    out, name = {}, ""
    for line in report.splitlines():
        if line.startswith("## "):
            name = line.strip()
            out[name] = ""
        elif name:
            out[name] += line + "\n"
    return out


def sentences(block: str, lang: str) -> list[str]:
    """줄과 문장으로 나눈다. 마침표 뒤에 붙은 인용·표시는 앞 문장에 붙인다."""
    marks = "|".join(re.escape(m) for m in MARKERS[lang])
    out = []
    for line in block.splitlines():
        line = re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", line).strip()
        if not line or line.startswith("|"):
            continue
        line = re.sub(rf"([.!?])\s*((?:(?:\[S\d+\]|{marks})\s*)+)", lambda m: " " + m.group(2).strip() + m.group(1) + " ", line)
        out += [s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if s.strip()]
    return out


def _plain(sentence: str, lang: str) -> str:
    # 인용 별칭과 파이프라인의 출처 주석 "(S3: …)"은 주장 내용이 아니므로 뺀다(2026-10-03 기준 변경, QUALITY-LOG 참조).
    text = CITE.sub("", sentence)
    text = re.sub(r"\(S\d+[:·][^)]*\)", "", text)
    text = re.sub(r"\bS\d+\b", "", text)
    for marker in MARKERS[lang]:
        text = text.replace(marker, "")
    return text.strip()


def _bigrams(text: str) -> set[str]:
    compact = re.sub(r"[^0-9a-z가-힣]", "", text.lower())
    return {compact[i:i + 2] for i in range(len(compact) - 1)}


def _numbers(text: str) -> list[str]:
    return [n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]


# 방향 낱말과 문맥 낱말 비교(2026-10-04 2회차 기준 강화, QUALITY-LOG 참조). 영어는 낱말, 한국어는 어절 앞 두 글자로 본다.
_UP = re.compile(r"\b(?:increase[sd]?|increasing|rose|rises?|grew|grows?|higher)\b|증가|늘었|늘어|상승|많아", re.I)
_DOWN = re.compile(r"\b(?:decrease[sd]?|decreasing|fell|falls?|declined?|lower|reduced?|dropped)\b|감소|줄었|줄어|하락|적었|낮아|낮췄", re.I)
_EN_STOP = {"that", "with", "from", "this", "were", "have", "been", "than", "which", "about", "over", "after", "into", "their",
            "percent", "compared", "they", "said", "also", "only", "during", "under", "same", "year", "years", "median",
            "average"}


def _source_sentences(source_text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", source_text) if s.strip()]


def _direction(text: str) -> str:
    up, down = bool(_UP.search(text)), bool(_DOWN.search(text))
    return "up" if up and not down else "down" if down and not up else ""


def _content_terms(text: str) -> set[str]:
    text = re.sub(r"\d[\d,.]*", " ", text)
    text = _UP.sub(" ", _DOWN.sub(" ", text))
    words = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", text)} - _EN_STOP
    return words | {w[:2] for w in re.findall(r"[가-힣]{2,}", text)}


def _shares_context(claim: str, source_sentence: str) -> bool:
    terms = _content_terms(claim)
    lowered = source_sentence.lower()
    return not terms or any(t in lowered for t in terms)


def supported(sentence: str, source_text: str, lang: str) -> bool:
    """숫자는 전부 원문에 있어야 하고, 글자 2-gram의 절반 이상이 원문에 있어야 한다.

    2026-10-04 2회차 기준 강화: 숫자가 든 원문 문장 중 하나는 주장과 문맥 낱말을 공유해야 하고,
    주장과 가장 가까운 원문 문장(숫자가 있으면 그 숫자가 든 문장)과 증감 방향이 반대면 안 된다."""
    plain = _plain(sentence, lang)
    source_numbers = set(_numbers(source_text))
    numbers = _numbers(plain)
    if any(n not in source_numbers for n in numbers):
        return False
    grams = _bigrams(plain)
    if grams and len(grams & _bigrams(source_text)) / len(grams) < 0.5:
        return False
    sents = _source_sentences(source_text)
    anchored = [s for s in sents if any(n in _numbers(s) for n in numbers)]
    for n in numbers:
        holders = [s for s in sents if n in _numbers(s)]
        if holders and not any(_shares_context(plain, s) for s in holders):
            return False
    nearest = anchored or ([max(sents, key=lambda s: len(grams & _bigrams(s)))] if sents and grams else [])
    claim_dir = _direction(plain)
    if claim_dir and nearest and all(_direction(s) not in ("", claim_dir) for s in nearest):
        return False
    return True


def score(final: str | None, lang: str, prompt: str, sources: dict[str, dict]) -> dict:
    """sources: id → {"text": 원문, "cluster": 관계 묶음}. final이 None이면 실행 실패로 전부 0."""
    if final is None:
        return {m: 0.0 for m in METRICS} | {"failed": True, "detail": {}}
    h = HEAD[lang]
    report = model_report(final, lang)
    parts = sections(report)
    src_heading = next((k for k in parts if k == h["sources"]), None)
    body = report.split("\n" + h["sources"], 1)[0]
    detail: dict = {}

    cites = CITE.findall(body)
    valid = [c for c in cites if c in sources and sources[c]["text"].strip()]
    detail["invalid_cites"] = sorted(set(cites) - set(valid))
    citation_validity = len(valid) / len(cites) if cites else 0.0

    claim_parts = [v for k, v in parts.items() if k in (h["answer"], h["evidence"], *h["limits"])]
    claims = [s for block in claim_parts for s in sentences(block, lang)]
    cited = [s for s in claims if CITE.search(s)]
    mismatched = []
    for s in cited:
        ids = [c for c in CITE.findall(s) if c in sources]
        text = "\n".join(sources[c]["text"] for c in ids)
        flagged = MARKERS[lang][2] in s
        if not flagged and not (ids and supported(s, text, lang)):
            mismatched.append(s)
    detail["mismatched"] = mismatched
    claim_source_match = 1 - len(mismatched) / len(cited) if cited else 0.0

    rows = CITE.findall(parts.get(src_heading, "")) if src_heading else []
    multi = [s for s in cited if len(set(CITE.findall(s))) >= 2]
    # 독자에게 '독립 출처가 아닐 수 있음'을 알린 겹침 인용은 감점하지 않는다(2026-10-03 기준 변경, QUALITY-LOG 참조).
    warned = ("독립 출처가 아닐 수 있음", "may not be independent")
    same_cluster = [s for s in multi if not any(w in s for w in warned)
                    and len({sources.get(c, {}).get("cluster", c) for c in set(CITE.findall(s))}) == 1]
    dup = (len(rows) - len(set(rows))) + len(same_cluster)
    detail["duplicate_rows"] = len(rows) - len(set(rows))
    detail["same_cluster_cocites"] = same_cluster
    denom = len(rows) + len(multi)
    duplicate_sources = 1 - dup / denom if denom else 1.0

    # '(판단)'만 붙은 문장이 어떤 출처에도 없는 수치를 담으면 판단이 아니라 표시 없는 사실로 본다(2026-10-04 2회차 기준 강화).
    all_numbers = {n for v in sources.values() for n in _numbers(v["text"])}
    unmarked = [s for s in claims if not CITE.search(s) and len(re.sub(r"\W", "", s)) >= 8
                and (not any(m in s for m in MARKERS[lang])
                     or (MARKERS[lang][0] in s and not any(m in s for m in MARKERS[lang][1:])
                         and any(n not in all_numbers for n in _numbers(_plain(s, lang)))))]
    detail["unmarked"] = unmarked
    unmarked_unverified = 1 - len(unmarked) / len(claims) if claims else 0.0

    def filled(name: str) -> bool:   # 제목만 있고 내용이 빈 절은 구조로 치지 않는다
        return bool(parts.get(name, "").strip())
    checks = [h["question"] + prompt.strip() in report, filled(h["answer"]), filled(h["evidence"]),
              any(filled(x) for x in h["limits"]), src_heading is not None and filled(src_heading), filled(h["next"])]
    detail["structure_missing"] = [n for n, ok in zip(("question", "answer", "evidence", "limits", "sources", "next"), checks) if not ok]
    structure = sum(checks) / len(checks)

    return {"citation_validity": round(100 * citation_validity, 1), "claim_source_match": round(100 * claim_source_match, 1),
            "duplicate_sources": round(100 * duplicate_sources, 1), "unmarked_unverified": round(100 * unmarked_unverified, 1),
            "structure": round(100 * structure, 1), "failed": False, "detail": detail}
