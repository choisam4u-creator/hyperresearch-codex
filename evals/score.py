"""최종 보고서 품질 점수. 각 항목은 0~100이며 높을수록 좋다.

점수는 독자가 경고 없이 보게 되는 문제를 센다. 기준을 바꾸면 docs/QUALITY-LOG.md에
이유를 따로 적는다.
"""
import re
from pathlib import Path

CITE = re.compile(r"\[(S\d+)\]")
MARKERS = {"ko": ("(판단)", "(출처 없음)", "(출처 불일치)"), "en": ("(judgment)", "(no source)", "(source mismatch)")}
# 원문의 추정·잠정치를 확정 사실처럼 쓴 문장에 붙는 약한 경고(2026-10-06 기준 강화). 이 결함에만 경고로 인정한다.
ESTIMATE_MARK = {"ko": "(원문 추정치)", "en": "(source estimate)"}
HEAD = {
    "ko": {"question": "# 질문: ", "answer": "## 답", "evidence": "## 근거", "limits": ("## 반대 근거와 한계", "## 한계"),
           "sources": "## 출처", "next": "## 다음 행동", "end": "## 검증 상태"},
    "en": {"question": "# Question: ", "answer": "## Answer", "evidence": "## Evidence",
           "limits": ("## Counter-evidence and limits", "## Limits"), "sources": "## Sources", "next": "## Next actions",
           "end": "## Verification status"},
}
METRICS = ("citation_validity", "claim_source_match", "false_warnings", "duplicate_sources", "unmarked_unverified",
           "internal_consistency", "structure")
LABELS = {"citation_validity": "인용 유효성", "claim_source_match": "주장-출처 일치",
          "false_warnings": "잘못 붙은 경고 없음", "duplicate_sources": "중복 출처 없음",
          "unmarked_unverified": "표시 없는 미검증 주장 없음", "internal_consistency": "본문 내부 일관성",
          "structure": "보고서 구조"}


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
        out += [s.strip() for s in re.split(r"(?<=[.!?])(?<![Aa]pprox\.)\s+", line) if s.strip()]
    return out


def _plain(sentence: str, lang: str) -> str:
    # 인용 별칭과 파이프라인의 출처 주석 "(S3: …)"은 주장 내용이 아니므로 뺀다(2026-10-03 기준 변경, QUALITY-LOG 참조).
    text = CITE.sub("", sentence)
    text = re.sub(r"\(S\d+[:·][^)]*\)", "", text)
    text = re.sub(r"\bS\d+\b", "", text)
    for marker in MARKERS[lang] + (ESTIMATE_MARK[lang],):
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
    # "approx." 뒤에서는 끊지 않는다(2026-10-06 PR #16 리뷰 반영).
    return [s.strip() for s in re.split(r"(?<=[.!?])(?<![Aa]pprox\.)\s+|\n+", source_text) if s.strip()]


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


# 인과 단정과 기간 단위(2026-10-05 기준 강화, QUALITY-LOG 참조).
_CAUSAL = re.compile(r"\b(?:caus(?:e|es|ed|ing)|because|due to|led to|leads? to|result(?:s|ed)? in|thanks to|drove|driven by|"
                     r"attribut\w*|as a result)\b|덕분|때문|인해|탓에|탓으로|기여했|이끌었|낳았|결과로", re.I)
_CAUSAL_SOURCE = re.compile(_CAUSAL.pattern + r"|\b(?:effects?|impacts?|contribut\w*)\b|인과|영향|효과|기여", re.I)
_DISCLAIM = re.compile(r"\b(?:cannot|can't|could not|did not|does not|do not|not|unable to)\s+(?:\w+\s+){0,2}?"
                       r"(?:establish|determine|show|prove|isolate|distinguish|separate|attribute)\w*|\bobservational\b|"
                       r"\bcorrelation\b|인과[^.]*?(?:않|못|없)|(?:구분|확인|분석|판단|입증)하지\s*(?:않|못)|(?:구분|입증)할 수 없", re.I)
_PERIODS = {"day": r"하루|일평균|일일|매일|\bper day\b|\ba day\b|\bdaily\b|\beach day\b",
            "week": r"주당|매주|일주일|\bper week\b|\bweekly\b|\ba week\b",
            "month": r"한 달|월평균|매월|월간|\bper month\b|\bmonthly\b|\ba month\b",
            "year": r"연간|연평균|매년|해마다|\bper year\b|\ba year\b|\bannual(?:ly)?\b|\byearly\b|\beach year\b",
            "total": r"(?:^|\s)총\s?\d|누적|\bin total\b|\btotal\b|\bcumulative\b|\baltogether\b"}


def _periods(text: str) -> set[str]:
    return {k for k, pat in _PERIODS.items() if re.search(pat, text, re.I)}


def causal_unsupported(plain: str, source_text: str) -> bool:
    """주장이 인과를 단정하는데 인용 원문에 같은 대상(문맥 낱말 공유)의 인과를 말하는(부정·유보하지 않은) 문장이 없으면 True.

    2026-10-05 PR #14 리뷰 반영: 다른 대상의 인과 문장("비 때문에 한 곳이 문을 닫았다")은 근거로 치지 않는다."""
    if not _CAUSAL.search(plain) or _DISCLAIM.search(plain):
        return False
    terms = _content_terms(_CAUSAL_SOURCE.sub(" ", plain))
    return not any(_CAUSAL_SOURCE.search(s) and not _DISCLAIM.search(s)
                   and terms & _content_terms(_CAUSAL_SOURCE.sub(" ", s)) for s in _source_sentences(source_text))


_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")
_CLAUSE = re.compile(r"[,;:()]")


def _number_periods(text: str) -> list[tuple[str, set[str]]]:
    """수치마다 그 수치가 든 절(쉼표 등으로 끊음)에서 가장 가까운 기간 단위 하나(PR #14 리뷰 반영)."""
    out = []
    for m in _NUM.finditer(text):
        start = max((b.end() for b in _CLAUSE.finditer(text, 0, m.start())), default=0)
        stop = next((b.start() for b in _CLAUSE.finditer(text, m.end())), len(text))
        found = [(abs(x.start() + start - m.start()), k) for k, pat in _PERIODS.items()
                 for x in re.finditer(pat, text[start:stop], re.I)]
        out.append((m.group(0).replace(",", ""), {min(found)[1]} if found else set()))
    return out


def period_mismatch(plain: str, source_text: str) -> bool:
    """주장 수치의 기간 단위(하루·한 달·연간·총계)가 원문에서 같은 수치가 나오는 자리마다의 기간 단위와 모두 다르면 True."""
    held_all = [x for s in _source_sentences(source_text) for x in _number_periods(s)]
    for n, claim_periods in _number_periods(plain):
        if not claim_periods:
            continue
        held = [p for m, p in held_all if m == n]
        if held and all(p and not (p & claim_periods) for p in held):
            return True
    return False


# 계획·추정의 실적화와 표본 범위의 일반화(2026-10-05 2회차 기준 강화, QUALITY-LOG 참조).
# 미래·계획형 유보만 본다. 추정(estimate·추정)을 떼는 것은 다른 결함 유형으로 백로그에 둔다(QUALITY-LOG 참조).
_HEDGE = re.compile(r"\b(?:plan(?:s|ned|ning)?|target(?:s|ed)?|aim(?:s|ed)?|goal|expect(?:s|ed)?|project(?:ed|ion|ions)|"
                    r"forecast\w*|propos\w*|intend\w*|will)\b|계획|목표|예정|전망|예상|방침", re.I)
_WIDE = re.compile(r"\b(?:nationwide|citywide|statewide|countrywide|across (?:the )?(?:entire )?(?:city|country|nation|state|region)|"
                   r"(?:all|every) (?:residents?|households?|schools?|districts?|neighbou?rhoods?|branches|users|citizens|"
                   r"workers|employees|cities|regions|counties))\b|전국|전\s?국민|시\s?전역|전역|전 지역|도시 전체|시 전체|"
                   r"모든\s?(?:시민|주민|가구|학교|지역|구|지점|사업장|이용자|노동자|직원)", re.I)
_NARROW = re.compile(r"\b(?:pilot|sample[sd]?|survey(?:ed)?|respondents?|participat\w*|selected)\b|"
                     r"\b(?:two|three|four|five|six|\d+) (?:districts?|neighbou?rhoods?|branches|schools|sites|cities|counties)\b|"
                     r"시범|표본|응답자|설문|참여한|참가한|선정된|\d+\s?(?:개|곳)\s?(?:구|동|지점|학교|단지|지역)", re.I)


_PROP = re.compile(r"\b(?:and|but|while|whereas)\b|그리고|했고|하고|됐고|되었고|였고|이었고|으며|이며|지만", re.I)


def _proposition_span(text: str, start: int, end: int) -> tuple[int, int]:
    """수치가 든 절에서 접속어로 한 번 더 끊은 명제의 범위(실적과 계획이 한 절에 이어질 때, PR #15 리뷰 반영)."""
    a = max((b.end() for b in _CLAUSE.finditer(text, 0, start)), default=0)
    a = max([a] + [m.end() for m in _PROP.finditer(text, a, start)])
    b = next((x.start() for x in _CLAUSE.finditer(text, end)), len(text))
    b = min([b] + [m.start() for m in _PROP.finditer(text, end, b)])
    return a, b


def _proposition(text: str, start: int, end: int) -> str:
    a, b = _proposition_span(text, start, end)
    return text[a:b]


def hedge_dropped(plain: str, source_text: str) -> bool:
    """주장 수치가 원문에서는 매번 계획·목표·추정을 말하는 절에만 나오는데 주장은 유보 없이 사실처럼 말하면 True."""
    if _HEDGE.search(plain):
        return False
    sents = _source_sentences(source_text)
    for m in _NUM.finditer(plain):
        n = m.group(0).replace(",", "")
        held = [_proposition(s, x.start(), x.end()) for s in sents for x in _NUM.finditer(s) if x.group(0).replace(",", "") == n]
        if held and all(_HEDGE.search(c) for c in held):
            return True
    return False


# 추정·잠정치의 확정화(2026-10-06 기준 강화, QUALITY-LOG 참조). 연도·월·일 수치는 날짜라 보지 않는다.
_ESTIMATE = re.compile(r"\b(?:estimat\w*|preliminary|provisional|unaudited|approximately|approx\.|roughly|nearly|almost|"
                       r"(?:about|around|some) (?=\d))|추정|추산|잠정|어림|대략|가량|안팎|내외|약\s?(?=\d)", re.I)
# 연도는 달 이름·연도 전치사 바로 뒤의 네 자리 수만 본다(PR #16 리뷰 반영 — "found 2000 people"의 2000은 수량).
_DATE_NUM = re.compile(r"\d{1,2}\s?(?:월|일)(?![가-힣])|\d{4}\s?년")
_YEAR_LEAD = re.compile(r"(?:\b(?:January|February|March|April|May|June|July|August|September|October|November|December|"
                        r"in|by|since|until|till|from|through|to|during|before|after|of|year|fiscal|FY)|[-–—~])\s*$", re.I)


def estimate_dropped(plain: str, source_text: str) -> bool:
    """주장 수치가 원문에서는 매번 추정·잠정치를 말하는 명제에만 나오는데 주장은 그런 유보 없이 확정처럼 말하면 True."""
    dates = [m.span() for m in _DATE_NUM.finditer(plain)]
    sents = _source_sentences(source_text)
    for m in _NUM.finditer(plain):
        n = m.group(0).replace(",", "")
        if any(a <= m.start() < b for a, b in dates) or (
                re.fullmatch(r"(?:19|20)\d\d", n) and "," not in m.group(0) and _YEAR_LEAD.search(plain[:m.start()])):
            continue
        own = _proposition(plain, m.start(), m.end())   # 유보 낱말은 그 수치가 든 명제에서만 본다(PR #16 리뷰 반영)
        if _ESTIMATE.search(own) or _HEDGE.search(own):
            continue
        held = [_proposition(s, x.start(), x.end()) for s in sents for x in _NUM.finditer(s) if x.group(0).replace(",", "") == n]
        if held and all(_ESTIMATE.search(c) for c in held):
            return True
    return False


# 상한·범위 끝값의 대표값화(2026-10-08 기준 강화, QUALITY-LOG 참조). 원문이 "최대 30%"·"up to 25 percent"처럼 상한으로만,
# 또는 "10~20%"·"between 8 and 12 percent"처럼 범위의 끝값으로만 말한 수치를 주장이 상한·범위 표시 없이 쓰면 불일치.
# "from 9,000 to 14,000"·"10%에서 18%로"는 변화 전후 값이라 범위로 보지 않는다.
_BOUND = re.compile(r"\b(?:up to|as (?:much|many|high|low|few|little) as|at (?:most|least)|a (?:maximum|minimum) of|"
                    r"no (?:more|less|fewer) than|more than|less than|fewer than|over|under|peak(?:ed|ing)? (?:at|of)|"
                    r"between|range[sd]? from|ranging from)\s*$|(?:최대|최고|최소|많게는|적게는|최저)\s*$", re.I)
_RANGE_TAIL = re.compile(r"\s*(?:%|percent|퍼센트|명|원|가구|곳)?\s*(?:~|–|—|-|\bto\b|\band\b)\s*$", re.I)
_RANGE_HEAD = re.compile(r"\s*(?:%|percent|퍼센트|명|원|가구|곳)?\s*(?:~|–|—|-|\bto\b)\s*\d", re.I)
_BOUND_AFTER = re.compile(r"\s*(?:%|퍼센트|명|원|가구|곳)?\s*(?:이상|이하|미만|초과|까지|이내|안쪽)", re.I)


def _bounded_at(text: str, start: int, end: int) -> bool:
    """수치가 상한·하한 낱말 뒤에 있거나, 범위("10~20%", "8 and 12", "between …")의 끝값이면 True. "from X to Y"는 변화라 뺀다."""
    before = text[max(0, start - 40):start]
    if _BOUND.search(before) or _BOUND_AFTER.match(text, end):
        return True
    prev = re.search(r"(\d[\d,.]*)" + _RANGE_TAIL.pattern, before, re.I)
    if prev and not re.search(r"\bfrom\s*$", before[:prev.start()], re.I):
        return True
    return bool(_RANGE_HEAD.match(text, end)) and not re.search(r"\bfrom\s*$", before, re.I)


def bound_dropped(plain: str, source_text: str) -> bool:
    """주장 수치가 원문에서는 매번 상한·범위 끝값으로만 나오는데 주장은 그 수치를 상한·범위 표시 없이 말하면 True."""
    dates = [m.span() for m in _DATE_NUM.finditer(plain)]
    sents = _source_sentences(source_text)
    for m in _NUM.finditer(plain):
        n = m.group(0).replace(",", "")
        if any(a <= m.start() < b for a, b in dates) or re.fullmatch(r"(?:19|20)\d\d", n):
            continue
        if _bounded_at(plain, m.start(), m.end()):
            continue
        held = [(s, x) for s in sents for x in _NUM.finditer(s) if x.group(0).replace(",", "") == n]
        if held and all(_bounded_at(s, x.start(), x.end()) for s, x in held):
            return True
    return False


# 대상 바꿈(2026-10-08 2회차 기준 강화, QUALITY-LOG 참조). 원문이 "심야버스 이용객 18%, 지하철 막차 이용객 4%"처럼 같은 종류
# 수치를 여러 대상에 나란히 말할 때, 주장이 한 대상의 수치를 다른 대상의 값으로 옮겨 쓰면 불일치. 수치의 대상 낱말은 그 수치가 든
# 명제에서 앞 수치 뒤부터 그 수치까지(한국어·영어 모두 대상이 수치 앞에 온다)로 근사한다. 영어 낱말은 3글자 이상("bus")을 본다.
_LABEL_STOP = {"the", "and", "for", "was", "are", "its", "has", "had", "not", "but", "all", "per", "new", "one", "two", "who",
               "percent", "rose", "fell", "grew", "dropped", "declined", "에서", "에는", "에도", "으로", "부터", "까지", "에게"}
_KIND = re.compile(r"\s*(%\s?p\b|%\s?포인트|퍼센트\s?포인트|percentage[- ]points?\b|%|퍼센트|percent\b|[가-힣]+|[A-Za-z]+)?", re.I)
# 다른 낱말에 붙은 숫자("S1")와 한국어 복합 표기의 토막("1억 2천만"의 1·2)은 대상 비교에서 뺀다.
_QNUM = re.compile(r"(?<![A-Za-z0-9.,])\d[\d,]*(?:\.\d+)?(?![천백십만억조]\s?\d)(?<![천백십만억조]\s\d)")
# 앞 수치와 변화·범위로 이어진 수치("10%에서 18%로", "from 9,000 to 14,000", "10~20%")는 앞 수치와 같은 대상이다.
_LINKED = re.compile(r"^\s*(?:%|퍼센트|percent|[가-힣]{1,2})?(?:\s*[가-힣A-Za-z]{1,4}){0,2}\s*(?:에서|부터|~|–|-|\bto\b|\band\b)"
                     r"(?:\s+[가-힣A-Za-z]{1,4}){0,2}\s*$", re.I)


def _label(text: str, start: int, end: int) -> set[str]:
    a, _ = _proposition_span(text, start, end)
    cut = start
    for prev in reversed([x for x in _QNUM.finditer(text, a, start) if x.end() <= start]):
        if not _LINKED.match(text[prev.end():cut]):
            a = prev.end()
            a += len(re.match(r"\S*", text[a:cut]).group(0))   # 앞 수치에 붙은 단위·조사("2025년에는")는 대상이 아니다
            break
        cut = prev.start()
    head = _UP.sub(" ", _DOWN.sub(" ", text[a:cut]))
    words = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", head)} - _EN_STOP - _LABEL_STOP
    return words | ({w[:2] for w in re.findall(r"[가-힣]{2,}", head)} - _LABEL_STOP)


def _kind(text: str, end: int) -> str:
    m = _KIND.match(text, end)
    k = (m.group(1) or "").lower() if m else ""
    return "pct" if k in ("%", "퍼센트", "percent") else "pp" if k and ("p" in k[1:2] or "포인트" in k or "point" in k) else k[:2]


def subject_swapped(plain: str, source_text: str) -> bool:
    """주장 수치가 원문에서 나오는 자리마다, 그 자리 대상 낱말은 주장에 없고 같은 종류의 다른 수치 자리 대상 낱말이 주장에 더 많으면 True."""
    dates = [m.span() for m in _DATE_NUM.finditer(plain)]
    sents = _source_sentences(source_text)
    spots = [(s, x) for s in sents for x in _QNUM.finditer(s)]
    for m in _QNUM.finditer(plain):
        n = m.group(0).replace(",", "")
        if any(a <= m.start() < b for a, b in dates) or re.fullmatch(r"(?:19|20)\d\d", n):
            continue
        mine = _label(plain, m.start(), m.end())
        kind = _kind(plain, m.end())
        held = [(s, x) for s, x in spots if x.group(0).replace(",", "") == n]
        if not mine or not held:
            continue

        def moved(s: str, x: re.Match) -> bool:
            own = _label(s, x.start(), x.end())
            for s2, y in spots:
                if y.group(0).replace(",", "") == n or _kind(s2, y.end()) != kind:
                    continue
                other = _label(s2, y.start(), y.end())
                if own - other and mine & (other - own) and len(mine & (other - own)) > len(mine & (own - other)):
                    return True
            return False
        if all(moved(s, x) for s, x in held):
            return True
    return False


def scope_widened(plain: str, source_text: str) -> bool:
    """주장이 전역·전체 범위를 말하는데, 주장 수치가 든 원문 문장은 모두 시범·표본 범위만 말하고 전역 낱말은 없으면 True."""
    if not _WIDE.search(plain):
        return False
    numbers = set(_numbers(plain))
    sents = _source_sentences(source_text)
    if numbers:
        held = [s for s in sents if numbers & set(_numbers(s))]
    else:   # 수치 없는 일반화는 같은 대상(문맥 낱말 2개 이상 공유) 원문 문장으로 본다(PR #15 리뷰 반영)
        terms = _content_terms(_NARROW.sub(" ", _WIDE.sub(" ", plain)))
        held = [s for s in sents if len(terms & _content_terms(_NARROW.sub(" ", _WIDE.sub(" ", s)))) >= 2]
    return bool(held) and all(_NARROW.search(s) and not _WIDE.search(s) for s in held)


# 기준 연도와 퍼센트·퍼센트포인트(2026-10-06 2회차 기준 강화, QUALITY-LOG 참조).
# 연도는 '2025년'이나 연도 전치사(between 포함)·달 이름 바로 뒤의 네 자리 수로 본다. 수치의 연도는 그 수치가 든 명제에
# 연도가 하나뿐이면 그것, 명제에 없으면 문장 전체에 연도가 하나뿐일 때 그것이다. 둘 이상이거나 없으면 모른다고 본다.
_YEAR_TOKEN = re.compile(r"(?<![\d,.])((?:19|20)\d\d)(?!\d|,\d|\.\d)")
_YEAR_AFTER = re.compile(r"\band\s*$", re.I)


def _year_spans(text: str) -> list[tuple[str, int, int]]:
    out: list[tuple[str, int, int]] = []
    for m in _YEAR_TOKEN.finditer(text):
        before = text[:m.start()]
        # 'between'은 늘 연도 자리, 'and'는 앞에 연도가 이미 있을 때만("between 2022 and 2025")
        # 문장 첫머리의 네 자리 수("2023 enrollment reached …")도 연도로 본다(PR #17 리뷰 반영).
        if (re.match(r"\s?년|\s*[~–—-]\s*(?:19|20)\d\d\s*년", text[m.end():]) or _YEAR_LEAD.search(before)
                or re.search(r"\bbetween\s*$", before, re.I)
                or (re.search(r"(?:^|[.!?]\s+)\s*$", before) and re.match(r"\s+[A-Za-z]", text[m.end():]))
                or (out and _YEAR_AFTER.search(before))):
            out.append((m.group(1), m.start(), m.end()))
    return out


def _value_years(text: str) -> list[tuple[str, str | None]]:
    """연도가 아닌 수치마다 (수치, 그 수치의 기준 연도 또는 None)."""
    years = _year_spans(text)
    spans = [(a, b) for _, a, b in years] + [m.span() for m in re.finditer(r"\d{1,2}\s?(?:월|일)(?![가-힣])", text)]
    out = []
    for m in _NUM.finditer(text):
        if any(a <= m.start() < b for a, b in spans):
            continue
        lo, hi = _proposition_span(text, m.start(), m.end())
        mine = {y for y, a, _ in years if lo <= a < hi}
        if not mine:
            mine = {y for y, _, _ in years}
        out.append((m.group(0).replace(",", ""), next(iter(mine)) if len(mine) == 1 else None))
    return out


def year_moved(plain: str, source_text: str) -> bool:
    """주장 수치의 기준 연도가 원문에서 같은 수치가 나오는 자리마다의 기준 연도(모두 알려짐)와 하나도 같지 않으면 True."""
    held_all = [x for s in _source_sentences(source_text) for x in _value_years(s)]
    for n, year in _value_years(plain):
        if year is None:
            continue
        held = [y for m, y in held_all if m == n]
        if held and all(y is not None and y != year for y in held):
            return True
    return False


_PP = re.compile(r"\s*(?:%\s?p\b|%\s?포인트|퍼센트\s?포인트|%\s?points?\b|percentage[- ]points?\b|pp\b)", re.I)
_PCT = re.compile(r"\s*(?:%|퍼센트|percent\b|per cent\b)", re.I)


def _percent_kinds(text: str) -> list[tuple[str, str]]:
    out = []
    for m in _NUM.finditer(text):
        rest = text[m.end():]
        out.append((m.group(0).replace(",", ""), "pp" if _PP.match(rest) else "pct" if _PCT.match(rest) else ""))
    return out


def percent_point_swapped(plain: str, source_text: str) -> bool:
    """주장이 퍼센트(%)로 말한 수치를 원문은 매번 퍼센트포인트로만 말하거나, 그 반대면 True(상대 변화와 차이는 다른 값이다)."""
    held_all = _percent_kinds(source_text)
    for n, kind in _percent_kinds(plain):
        if not kind:
            continue
        held = [k for m, k in held_all if m == n]
        if held and all(k and k != kind for k in held):
            return True
    return False


def magnitude_gap(a: str, b: str) -> bool:
    """같은 방향 두 문장이 퍼센트(또는 퍼센트포인트) 수치를 하나씩만 말하고, 같은 종류인데 큰 값이 작은 값의 2배 이상이면 True.

    같은 대상의 증감 폭을 출처마다 크게 다르게 말하는 경우(2026-10-06 2회차 추가)다. 2배는 집계 범위·방법이 다를 때
    생기는 차이로 보고, 반올림 정도의 작은 차이는 세지 않으려는 문턱이다."""
    ya, yb = {y for y, _, _ in _year_spans(a)}, {y for y, _, _ in _year_spans(b)}
    if ya and yb and not ya & yb:   # 서로 다른 해의 증감 폭은 상충이 아니다(PR #17 리뷰 반영)
        return False
    pa = [(float(n), k) for n, k in _percent_kinds(a) if k]
    pb = [(float(n), k) for n, k in _percent_kinds(b) if k]
    if len(pa) != 1 or len(pb) != 1 or pa[0][1] != pb[0][1]:
        return False
    lo, hi = sorted((pa[0][0], pb[0][0]))
    return lo > 0 and hi >= 2 * lo


# 자릿수 낱말(2026-10-07 기준 강화, QUALITY-LOG 참조). "420억 원"을 "420만 원"으로, "4.2 million"을 "4.2 billion"으로
# 바꿔도 숫자 글자는 같아 옛 기준이 통과시켰다. 값은 숫자×자릿수로 비교하고, 같은 값을 다르게 쓴 것("1.6 million"↔
# "1,600,000", "12만"↔"120,000")은 같은 수치로 본다.
# 2026-10-07 2회차: 약어(M·bn·mn·k, 통화 기호 뒤 m·b)와 한국어 복합 표기("1억 2천만", "4천5백만", "3만 5천")도 값으로 읽는다.
# 바꾼 약어("4.6 million"→"$4.6bn")는 불일치, 같은 값("$3.8M"↔"3.8 million", "1억 2천만"↔"1.2억")은 일치.
_MAG_WORDS = {"천": 10**3, "만": 10**4, "십만": 10**5, "백만": 10**6, "천만": 10**7, "억": 10**8, "십억": 10**9, "백억": 10**10,
              "천억": 10**11, "조": 10**12, "thousand": 10**3, "million": 10**6, "billion": 10**9, "trillion": 10**12,
              "k": 10**3, "m": 10**6, "mn": 10**6, "mln": 10**6, "b": 10**9, "bn": 10**9, "tn": 10**12}
_MAG = re.compile(r"\s*(십만|백만|천만|십억|백억|천억|천|만|억|조)(?!큼|에(?![가-힣]))|\s+(thousand|million|billion|trillion)(?![A-Za-z])|"
                  r"(\s?(?:bn|mn|mln|tn)|[KMBk])(?![A-Za-z])", re.I)
# 한국어 복합 표기: 숫자+자릿수 토막이 둘 이상 이어진 것. 큰 자릿수(조·억·만)는 내림차순으로만 잇는다.
_KO_COMPOUND = re.compile(r"\d[\d,]*(?:\.\d+)?(?:[천백십](?:\d[\d,]*(?:\.\d+)?[천백십])*)?[조억만]?"
                          r"(?:\s?\d[\d,]*(?:\.\d+)?(?:[천백십](?:\d[\d,]*(?:\.\d+)?[천백십])*)?[조억만]?)*")


def _ko_compound_value(raw: str) -> float | None:
    """"1억 2천만"·"4천5백만"·"3만 5천" 같은 복합 표기의 값. 토막이 하나뿐이거나 순서가 맞지 않으면 None."""
    parts = re.findall(r"(\d[\d,]*(?:\.\d+)?)([천백십]?)|([조억만])", raw.replace(" ", ""))
    total, group, last_big, pieces = 0.0, 0.0, 10**13, 0
    for num, small, big in parts:
        if big:
            if group == 0 or _MAG_WORDS[big] >= last_big:
                return None
            total, group, last_big = total + group * _MAG_WORDS[big], 0.0, _MAG_WORDS[big]
            pieces += 1
        else:
            group += float(num.replace(",", "")) * ({"천": 1000, "백": 100, "십": 10}[small] if small else 1)
            pieces += 1 if small else 0
    return round(total + group, 6) if pieces >= 2 else None


def _scaled(text: str) -> list[tuple[str, int, float]]:
    """수치마다 (숫자 글자, 자릿수 배율, 값). 한국어 복합 표기는 (표기 전체, 1, 값) 하나로 센다."""
    out, pos = [], 0
    while (m := _NUM.search(text, pos)):
        compound = _KO_COMPOUND.match(text, m.start())
        value = _ko_compound_value(compound.group(0)) if compound and not re.match(r"큼|에(?![가-힣])", text[compound.end():]) else None
        if value is not None:
            out.append((compound.group(0).replace(" ", ""), 1, value))
            pos = compound.end()
            continue
        mag = _MAG.match(text, m.end())
        word = (mag.group(1) or mag.group(2) or mag.group(3)).strip() if mag else ""
        if word in ("K", "k", "M", "B") or word.lower() in ("bn", "mn", "mln", "tn"):
            word = word.lower()
        elif word and word not in _MAG_WORDS and word.lower() not in _MAG_WORDS:
            word = ""
        if not word and re.search(r"[$€£₩]\s?$", text[:m.start()]) and re.match(r"[mb](?![A-Za-z])", text[m.end():]):
            word = text[m.end()]
        factor = _MAG_WORDS[word.lower()] if word else 1
        digits = m.group(0).replace(",", "")
        out.append((digits, factor, round(float(digits) * factor, 6)))
        pos = m.end()
    return out


def magnitude_swapped(plain: str, source_text: str) -> bool:
    """주장 수치의 숫자 글자는 원문에 있는데 자릿수 낱말이 원문의 같은 숫자 자리마다 다르고, 같은 값도 원문에 없으면 True."""
    held_all = _scaled(source_text)
    values = {v for _, _, v in held_all}
    for n, factor, value in _scaled(plain):
        held = [f for m, f, _ in held_all if m == n]
        if held and all(f != factor for f in held) and value not in values:
            return True
    return False


def supported(sentence: str, source_text: str, lang: str) -> bool:
    """숫자는 전부 원문에 있어야 하고, 글자 2-gram의 절반 이상이 원문에 있어야 한다.

    2026-10-04 2회차 기준 강화: 숫자가 든 원문 문장 중 하나는 주장과 문맥 낱말을 공유해야 하고,
    주장과 가장 가까운 원문 문장(숫자가 있으면 그 숫자가 든 문장)과 증감 방향이 반대면 안 된다."""
    plain = _plain(sentence, lang)
    source_numbers = set(_numbers(source_text))
    # 문맥 대조에 쓰는 숫자 글자. 한국어 복합 표기("1억 2천만")는 값으로 이미 대조했으므로 토막 숫자(1·2)로 원문 문장을 찾지 않는다.
    numbers = [n for n, _, _ in _scaled(plain) if re.fullmatch(r"[\d.]+", n)]
    source_values = {v for _, _, v in _scaled(source_text)}
    if any(n not in source_numbers and v not in source_values for n, _, v in _scaled(plain)):
        return False
    # 2026-10-07 기준 강화: 숫자는 같아도 자릿수 낱말(만·억·million·billion)이 원문과 다르면 불일치.
    if magnitude_swapped(plain, source_text):
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
    # 2026-10-05 기준 강화: 원문이 유보한 인과를 단정하거나, 같은 수치를 다른 기간 단위로 말하면 불일치.
    if causal_unsupported(plain, source_text) or period_mismatch(plain, source_text):
        return False
    # 2026-10-05 2회차 기준 강화: 원문의 계획·추정을 실적처럼, 시범·표본 결과를 전역 결과처럼 말하면 불일치.
    if hedge_dropped(plain, source_text) or scope_widened(plain, source_text):
        return False
    # 2026-10-06 기준 강화: 원문의 추정·잠정치를 유보 없이 확정 사실처럼 말하면 불일치('(원문 추정치)' 표시는 경고로 인정).
    if ESTIMATE_MARK[lang] not in sentence and estimate_dropped(plain, source_text):
        return False
    # 2026-10-06 2회차 기준 강화: 원문 수치를 다른 기준 연도의 값으로 옮기거나, 퍼센트포인트를 퍼센트로(또는 반대로) 말하면 불일치.
    if year_moved(plain, source_text) or percent_point_swapped(plain, source_text):
        return False
    # 2026-10-08 기준 강화: 원문이 상한·범위 끝값으로만 말한 수치를 상한·범위 표시 없이 대표값처럼 말하면 불일치.
    if bound_dropped(plain, source_text):
        return False
    # 2026-10-08 2회차 기준 강화: 원문이 한 대상의 값으로 말한 수치를 같은 종류 수치가 나란히 나오는 다른 대상의 값으로 옮기면 불일치.
    if subject_swapped(plain, source_text):
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

    # 잘못 붙은 경고(2026-10-07 2회차 추가): '(출처 불일치)'·'(원문 추정치)'가 붙은 인용 문장이 표시를 떼고도 이 점수기의
    # 엄격한 대조를 모두 통과하면, 맞는 문장에 경고를 붙여 독자의 신뢰를 깎은 것으로 본다. 위 일치 항목은 경고가 붙은 문장을
    # 통과로 세므로 경고를 남발해도 점수가 오르던 맹점을 막는다. 점수기 대조가 엄격하므로 이 수는 오표시의 하한이다.
    warn_marks = (MARKERS[lang][2], ESTIMATE_MARK[lang])
    false_warned = []
    for s in cited:
        if not any(m in s for m in warn_marks):
            continue
        ids = [c for c in CITE.findall(s) if c in sources]
        # 같은 관계 묶음 출처만 함께 인용한 문장의 경고는 '독립 출처' 주장 때문일 수 있고, 이 점수기의 대조는 독립성을 보지
        # 않으므로(중복 출처 항목이 본다) 세지 않는다(en-library-hours의 independence_conflict는 맞는 경고다).
        if len(set(ids)) >= 2 and len({sources[c].get("cluster", c) for c in ids}) == 1:
            continue
        bare = s
        for m in warn_marks:
            bare = bare.replace(m, "")
        if ids and supported(bare, "\n".join(sources[c]["text"] for c in ids), lang):
            false_warned.append(s)

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
    # 출처에 있는 수치라도 원문과 다른 기간 단위로 말하면 같은 취급(2026-10-05 기준 강화).
    all_numbers = {n for v in sources.values() for n in _numbers(v["text"])}
    all_text = "\n".join(v["text"] for v in sources.values())
    unmarked = [s for s in claims if not CITE.search(s) and len(re.sub(r"\W", "", s)) >= 8
                and (not any(m in s for m in MARKERS[lang])
                     or (MARKERS[lang][0] in s and not any(m in s for m in MARKERS[lang][1:])
                         and (any(n not in all_numbers for n in _numbers(_plain(s, lang)))
                              or period_mismatch(_plain(s, lang), all_text))))]
    detail["unmarked"] = unmarked
    unmarked_unverified = 1 - len(unmarked) / len(claims) if claims else 0.0

    # 본문 내부 일관성(2026-10-05 추가): 인용 없는 문장(판단 등)이 같은 대상을 말하는 인용 문장과 반대 증감 방향이면
    # 감점한다. 두 문장 중 하나에 '(출처 불일치)'가 붙어 있으면 독자에게 경고된 것으로 본다. 같은 대상은 문맥 낱말 2개 이상 공유.
    def _terms(x: str) -> set[str]:
        x = _UP.sub(" ", _DOWN.sub(" ", re.sub(r"\d[\d,.]*", " ", _plain(x, lang))))
        return ({w.lower() for w in re.findall(r"[A-Za-z]{4,}", x)} - _EN_STOP) | {w[:2] for w in re.findall(r"[가-힣]{2,}", x)}
    contradictions = []
    for s in claims:
        if CITE.search(s) or MARKERS[lang][2] in s or not _direction(_plain(s, lang)):
            continue
        for c in cited:
            if (MARKERS[lang][2] not in c and _direction(_plain(c, lang)) not in ("", _direction(_plain(s, lang)))
                    and len(_terms(s) & _terms(c)) >= 2):
                contradictions.append(s)
                break
    detail["contradictions"] = contradictions

    # 잘못 붙은 경고의 범위 확장(2026-10-08): 인용 없는 문장(판단 포함)의 '(출처 불일치)'는 같은 대상의 인용 문장과 반대
    # 방향이거나(위 내부 일관성 대조) 출처 수치를 다른 기간으로 말할 때만 맞는 경고다. '(판단)' 문장의 '(출처 없음)'은 어떤 출처에도
    # 없는 수치를 담거나 기간을 바꿀 때만 맞다. 표시를 떼고 이 대조를 모두 통과하면 잘못 붙은 경고로 센다. 판단 표시 없는
    # 인용 없는 문장의 '(출처 없음)'은 정의상 맞는 표시라 세지 않는다. 분모는 인용 문장에서 답·근거·한계 절 문장 전체로 넓혔다.
    for s in claims:
        if CITE.search(s):
            continue
        bare = s.replace(MARKERS[lang][2], "").replace(MARKERS[lang][1], "")
        plain = _plain(bare, lang)
        judged_no_source = MARKERS[lang][0] in s and MARKERS[lang][1] in s
        if MARKERS[lang][2] not in s and not judged_no_source:
            continue
        opposite = _direction(plain) and any(
            MARKERS[lang][2] not in c and _direction(_plain(c, lang)) not in ("", _direction(plain))
            and len(_terms(bare) & _terms(c)) >= 2 for c in cited)
        absent = any(n not in all_numbers for n in _numbers(plain))
        if not (opposite or period_mismatch(plain, all_text) or (judged_no_source and absent)
                or (MARKERS[lang][2] in s and absent)):
            false_warned.append(s)
    detail["false_warnings"] = false_warned
    false_warnings = 1 - len(false_warned) / len(claims) if claims else 1.0
    # 출처끼리 상충(2026-10-06 추가): 서로 다른 출처만 인용한 두 문장이 같은 대상(문맥 낱말 2개 이상)을 반대 증감 방향으로
    # 말하는데 한계 절의 어느 한 줄도 두 출처를 함께 언급하지 않으면, 독자가 상충을 모른 채 읽는다고 보고 감점한다.
    # 같은 방향이라도 증감 폭(퍼센트 하나씩)이 2배 이상 다르면 같은 상충으로 본다(2026-10-06 2회차 추가).
    limit_lines = "\n".join(parts.get(x, "") for x in h["limits"]).splitlines()
    trusted = [(c, set(CITE.findall(c))) for c in cited if MARKERS[lang][2] not in c and c not in mismatched
               and _direction(_plain(c, lang))]
    unacknowledged, seen_pairs = [], set()
    for i, (a, ids_a) in enumerate(trusted):
        for b, ids_b in trusted[i + 1:]:
            if (ids_a & ids_b or len(_terms(a) & _terms(b)) < 2
                    or (_direction(_plain(a, lang)) == _direction(_plain(b, lang))
                        and not magnitude_gap(_plain(a, lang), _plain(b, lang)))):
                continue
            pair = (min(ids_a, key=lambda x: int(x[1:])), min(ids_b, key=lambda x: int(x[1:])))
            pair = tuple(sorted(pair, key=lambda x: int(x[1:])))
            if pair in seen_pairs:   # 같은 출처 쌍은 문장이 반복돼도 한 번만 센다(PR #16 리뷰 반영)
                continue
            if not any(all(re.search(rf"(?<![A-Za-z0-9]){x}(?!\d)", row) for x in pair) for row in limit_lines):
                seen_pairs.add(pair)
                unacknowledged.append(f"{a} <> {b}")
    detail["unacknowledged_source_conflicts"] = unacknowledged
    internal_consistency = 1 - min(len(claims), len(contradictions) + len(unacknowledged)) / len(claims) if claims else 0.0

    def filled(name: str) -> bool:   # 제목만 있고 내용이 빈 절은 구조로 치지 않는다
        return bool(parts.get(name, "").strip())
    checks = [h["question"] + prompt.strip() in report, filled(h["answer"]), filled(h["evidence"]),
              any(filled(x) for x in h["limits"]), src_heading is not None and filled(src_heading), filled(h["next"])]
    detail["structure_missing"] = [n for n, ok in zip(("question", "answer", "evidence", "limits", "sources", "next"), checks) if not ok]
    structure = sum(checks) / len(checks)

    return {"citation_validity": round(100 * citation_validity, 1), "claim_source_match": round(100 * claim_source_match, 1),
            "false_warnings": round(100 * false_warnings, 1),
            "duplicate_sources": round(100 * duplicate_sources, 1), "unmarked_unverified": round(100 * unmarked_unverified, 1),
            "internal_consistency": round(100 * internal_consistency, 1), "structure": round(100 * structure, 1), "failed": False, "detail": detail}
