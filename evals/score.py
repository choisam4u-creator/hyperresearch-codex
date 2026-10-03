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
    text = CITE.sub("", sentence)
    for marker in MARKERS[lang]:
        text = text.replace(marker, "")
    return text.strip()


def _bigrams(text: str) -> set[str]:
    compact = re.sub(r"[^0-9a-z가-힣]", "", text.lower())
    return {compact[i:i + 2] for i in range(len(compact) - 1)}


def _numbers(text: str) -> list[str]:
    return [n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]


def supported(sentence: str, source_text: str, lang: str) -> bool:
    """숫자는 전부 원문에 있어야 하고, 글자 2-gram의 절반 이상이 원문에 있어야 한다."""
    plain = _plain(sentence, lang)
    source_numbers = set(_numbers(source_text))
    if any(n not in source_numbers for n in _numbers(plain)):
        return False
    grams = _bigrams(plain)
    return not grams or len(grams & _bigrams(source_text)) / len(grams) >= 0.5


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
    same_cluster = [s for s in multi
                    if len({sources.get(c, {}).get("cluster", c) for c in set(CITE.findall(s))}) == 1]
    dup = (len(rows) - len(set(rows))) + len(same_cluster)
    detail["duplicate_rows"] = len(rows) - len(set(rows))
    detail["same_cluster_cocites"] = same_cluster
    denom = len(rows) + len(multi)
    duplicate_sources = 1 - dup / denom if denom else 1.0

    unmarked = [s for s in claims if not CITE.search(s) and not any(m in s for m in MARKERS[lang])
                and len(re.sub(r"\W", "", s)) >= 8]
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
