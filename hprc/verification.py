"""모델 호출 없이 보고서의 남은 검토 신호를 모은다. 전체 사실성 판정기는 아니다."""
import datetime as dt
import re
import unicodedata
from decimal import Decimal, InvalidOperation

from .citation_sampling import select_samples


_DOUBLE_QUOTE = re.compile(r'"([^"\n]{12,})"|“([^”\n]{12,})”')
_MONTHS = {name.lower(): index for index, name in enumerate(
    ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"), 1)}
_MONTH_PATTERN = "|".join(_MONTHS)
_DATE_PATTERNS = (
    re.compile(r"(?<!\d)(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)"),
    re.compile(r"(?<!\d)(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일"),
    re.compile(rf"\b({_MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", re.IGNORECASE),
)
_KOREAN_YEAR_RANGE = re.compile(
    r"(?<!\d)(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})(?:\s*일)?\s*(?:~|[-–—]|부터)\s*(\d{1,2})\s*일(?:까지)?"
)
# 날짜 표기는 수치 근거 검사의 대상이 아니다. 다만 연도가 없거나 달력상
# 해석할 수 없는 표기는 _date_values에서 확정값으로 만들지 않아 별도 검토를 남긴다.
_KOREAN_DATE_LIKE = re.compile(
    r"(?<!\d)(?:(?:\d{4})\s*년\s*)?\d{1,2}\s*월\s*\d{1,2}(?:\s*일)?(?:\s*(?:~|[-–—]|부터)\s*\d{1,2}\s*일(?:까지)?)?"
)
_KOREAN_PARTIAL_DATE = re.compile(r"(?<!\d)(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_PARALLEL_DATE_CONNECTOR = re.compile(r"\s*(?:와|과|및|,)\s*")
_UNITS = ("percent", "milliseconds", "millisecond", "seconds", "second", "minutes", "minute", "hours", "hour",
          "mWh", "mW", "kWh", "Wh", "kW", "W", "GB", "MB", "TB", "KRW", "USD", "km", "kg", "ms", "%", "개소", "년", "월", "일", "명", "건", "곳", "대", "회", "종", "개", "배",
          "원", "달러", "초", "분", "시간", "m", "g", "s")
_QUANTITY = re.compile(r"(?<![A-Za-z0-9])[-+]?\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:" +
                       "|".join(re.escape(unit) for unit in _UNITS) + r"))?(?![A-Za-z0-9])", re.IGNORECASE)
_CONTEXT_WORD = re.compile(r"[A-Za-z가-힣]{2,}")
_CONTEXT_STOP = {"the", "and", "for", "with", "that", "this", "from", "was", "were", "are", "is", "to", "of", "in", "on", "by",
                 "이다", "있다", "한다", "된다", "그리고", "또는", "대한", "따른", "measured",
                 "increase", "increased", "increases", "higher", "rose", "rise", "decrease", "decreased",
                 "decreases", "lower", "fell", "fall", "reduced", "reduce", "증가", "상승", "감소", "하락"}
_DIRECTIONS = ({"increase", "increased", "increases", "higher", "rose", "rise", "증가", "늘", "상승"},
               {"decrease", "decreased", "decreases", "lower", "fell", "fall", "reduced", "reduce", "감소", "줄", "하락"})
_UNVERIFIED_SCOPE = re.compile(
    r"\b(?:not|never)\s+(?:yet\s+)?(?:been\s+)?(?:validated|verified|measured|confirmed)\b|\b(?:unvalidated|unverified|unmeasured|unknown)\b|"
    r"(?:검증|확인|측정)(?:되지|하지|하지 못|할 수 없)|(?:미검증|미확인|미측정)|(?:근거|자료|데이터)(?:가|는)?\s*(?:없|부족)",
    re.IGNORECASE,
)
_UNIT_SCALE = {
    "ms": ("time", Decimal("0.001")), "millisecond": ("time", Decimal("0.001")), "milliseconds": ("time", Decimal("0.001")),
    "s": ("time", Decimal("1")), "second": ("time", Decimal("1")), "seconds": ("time", Decimal("1")), "초": ("time", Decimal("1")),
    "minute": ("time", Decimal("60")), "minutes": ("time", Decimal("60")), "분": ("time", Decimal("60")),
    "hour": ("time", Decimal("3600")), "hours": ("time", Decimal("3600")), "시간": ("time", Decimal("3600")),
    "m": ("length", Decimal("1")), "km": ("length", Decimal("1000")),
    "g": ("mass", Decimal("1")), "kg": ("mass", Decimal("1000")),
    "w": ("power", Decimal("1")), "kw": ("power", Decimal("1000")),
    "wh": ("energy", Decimal("1")), "kwh": ("energy", Decimal("1000")),
    "개": ("count_item", Decimal("1")), "곳": ("count_place", Decimal("1")), "개소": ("count_place", Decimal("1")),
    "대": ("count_vehicle", Decimal("1")), "회": ("count_occurrence", Decimal("1")), "종": ("count_type", Decimal("1")),
    "%": ("percent", Decimal("1")), "percent": ("percent", Decimal("1")), "gb": ("data_decimal", Decimal("1000")), "mb": ("data_decimal", Decimal("1")),
    "tb": ("data_decimal", Decimal("1000000")), "usd": ("USD", Decimal("1")), "달러": ("USD", Decimal("1")),
    "krw": ("KRW", Decimal("1")), "원": ("KRW", Decimal("1")),
}


def _issue(kind: str, severity: str, line: int | None, message: str) -> dict:
    return {"kind": kind, "severity": severity, "line": line, "message": message}


def _cited_claims(report: str) -> list[dict]:
    return select_samples(report, 1_000_000, "")["samples"]


def _claim_keys(claims: list[dict]) -> set[tuple[str, frozenset]]:
    """행 번호는 다듬기 뒤 비인용 문장이 늘어도 바뀔 수 있어 비교에서 뺀다."""
    return {(claim["sentence"], frozenset(claim["cites"])) for claim in claims}


def _quote_text(value: str) -> str:
    """유니코드 인용부호·공백 표현 차이만 정규화한다. 의역은 일치시키지 않는다."""
    value = unicodedata.normalize("NFKC", value)
    value = value.translate(str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "\u00ad": ""}))
    return re.sub(r"\s+", " ", value).strip()


def _date_values(text: str) -> list[dict]:
    values = []
    year_anchors = []
    ranges = list(_KOREAN_YEAR_RANGE.finditer(text))
    for pattern_index, pattern in enumerate(_DATE_PATTERNS):
        for match in pattern.finditer(text):
            if any(r.start() <= match.start() < r.end() for r in ranges):
                continue
            try:
                if pattern_index == 2:
                    year, month, day = int(match.group(3)), _MONTHS[match.group(1).lower()], int(match.group(2))
                else:
                    year, month, day = map(int, match.groups())
                value = dt.date(year, month, day).isoformat()
            except (ValueError, KeyError):
                continue
            values.append({"raw": match.group(0), "value": value, "start": match.start(), "end": match.end()})
            year_anchors.append((year, match.end()))
    for match in ranges:
        try:
            year, month, first_day, last_day = map(int, match.groups())
            if first_day > last_day:
                continue
            first = dt.date(year, month, first_day).isoformat()
            last = dt.date(year, month, last_day).isoformat()
        except ValueError:
            continue
        values.extend((
            {"raw": match.group(0), "value": first, "start": match.start(), "end": match.end()},
            {"raw": match.group(0), "value": last, "start": match.start(), "end": match.end()},
        ))
        year_anchors.append((year, match.end()))
    # 생략 연도는 같은 줄에서 명시 연도 뒤를 와/과/및/,로 병렬 연결한 경우에만
    # 복원한다. 출처 사이 줄바꿈, 현재 연도, 메타데이터는 근거가 아니다.
    for match in _KOREAN_PARTIAL_DATE.finditer(text):
        if re.match(r"\s*(?:부터|[~–—-])", text[match.end():]):
            continue
        if any(value["start"] <= match.start() < value["end"] for value in values):
            continue
        # 범위의 첫 날짜처럼 더 긴 날짜 표기 안에 든 부분값은 독립 날짜가 아니다.
        # 예: "8월 6일부터 2일"은 잘못된 범위이며 8월 6일만 상속해 통과시키지 않는다.
        if any(span.start() <= match.start() and match.end() <= span.end()
               and (span.start(), span.end()) != (match.start(), match.end())
               for span in _KOREAN_DATE_LIKE.finditer(text)):
            continue
        candidates = [(year, end) for year, end in year_anchors if end <= match.start()
                      and "\n" not in text[end:match.start()]
                      and _PARALLEL_DATE_CONNECTOR.fullmatch(text[end:match.start()])]
        if not candidates:
            continue
        year, _ = candidates[-1]
        try:
            value = dt.date(year, int(match.group(1)), int(match.group(2))).isoformat()
        except ValueError:
            continue
        values.append({"raw": match.group(0), "value": value, "start": match.start(), "end": match.end()})
    return sorted(values, key=lambda item: item["start"])


def _date_like_spans(text: str) -> list[dict]:
    spans = {(match.start(), match.end(), match.group(0)) for pattern in (*_DATE_PATTERNS, _KOREAN_DATE_LIKE)
             for match in pattern.finditer(text)}
    return [{"raw": raw, "start": start, "end": end} for start, end, raw in sorted(spans)]


def _quantity_values(text: str, excluded: list[dict]) -> list[dict]:
    values = []
    excluded_spans = [(item["start"], item["end"]) for item in excluded]
    for match in _QUANTITY.finditer(text):
        if any(start <= match.start() < end for start, end in excluded_spans):
            continue
        raw = match.group(0)
        split = re.match(r"([-+]?\d+(?:,\d{3})*(?:\.\d+)?)(.*)", raw)
        if not split:
            continue
        try:
            number = Decimal(split.group(1).replace(",", ""))
        except InvalidOperation:
            continue
        unit = split.group(2).strip().lower()
        dimension, scale = _UNIT_SCALE.get(unit, (unit or "unitless", Decimal("1")))
        item = {"raw": raw, "value": number * scale, "dimension": dimension,
                "start": match.start(), "end": match.end()}
        # mW/MW는 대소문자에 따라 배율이 달라 지원하지 않는다.
        # 공백 유무와 관계없이 추출하되 근거 일치에는 사용하지 않는다.
        if unit in {"mw", "mwh"}:
            item["unsupported_unit"] = split.group(2).strip()
        values.append(item)
    return values


def _context_terms(text: str, start: int, end: int) -> set[str]:
    window = text[max(0, start - 90):min(len(text), end + 90)].lower()
    terms = set()
    for word in _CONTEXT_WORD.findall(window):
        if word in _CONTEXT_STOP:
            continue
        # 흔한 한국어 조사만 제거한다. 의미 어간을 추정하는 분석기는 아니다.
        for suffix in ("에서", "으로", "에게", "까지", "부터", "은", "는", "이", "가", "을", "를", "의", "에", "로", "와", "과", "도", "만"):
            if len(word) > len(suffix) + 1 and word.endswith(suffix):
                word = word[:-len(suffix)]
                break
        terms.add(word)
    return terms


def _signal(text: str, signals: set[str]) -> bool:
    lowered = text.lower()
    return any((re.search(rf"\b{re.escape(signal)}\b", lowered) is not None) if signal.isascii()
               else signal in lowered for signal in signals)


def _scripts(text: str) -> set[str]:
    text = re.sub(r"\[S\d+\]", "", text)
    scripts = set()
    if re.search(r"[가-힣]", text):
        scripts.add("ko")
    if re.search(r"[A-Za-z]", text):
        scripts.add("latin")
    return scripts


def _near_negation(text: str, value: dict) -> bool:
    """값 자체를 제한하는 가까운 부정만 찾고 출처 귀속 문구의 부정은 뺀다."""
    before = text[max(0, value["start"] - 28):value["start"]].lower()
    after = text[value["end"]:min(len(text), value["end"] + 20)].lower()
    english_before = re.search(r"\b(?:not|never|no)\b[^,;:.]{0,18}$", before) is not None
    english_after = re.match(r"[^,;:.]{0,10}\b(?:not|never)\b", after) is not None
    korean_before = re.search(r"(?:없|않|아니|못)[^,;:.。]{0,12}$", before) is not None
    korean_after = re.match(r"[^,;:.。]{0,10}(?:없|않|아니|못)", after) is not None
    return english_before or english_after or korean_before or korean_after


def _context_compatible(claim_text: str, claim: dict, source_text: str, source: dict) -> bool:
    claim_window = claim_text[max(0, claim["start"] - 90):min(len(claim_text), claim["end"] + 90)]
    source_window = source_text[max(0, source["start"] - 90):min(len(source_text), source["end"] + 90)]
    claim_terms = _context_terms(claim_text, claim["start"], claim["end"])
    source_terms = _context_terms(source_text, source["start"], source["end"])
    claim_window_scripts = _scripts(claim_window)
    source_window_scripts = _scripts(source_window)
    # 서로 다른 언어의 동의어를 단순 낱말 비교로 불일치라고 판정하지 않는다.
    if (claim_terms and source_terms and claim_window_scripts & source_window_scripts
            and not claim_terms & source_terms):
        return False
    directions = [(_signal(claim_window, group), _signal(source_window, group)) for group in _DIRECTIONS]
    if (directions[0][0] and directions[1][1]) or (directions[1][0] and directions[0][1]):
        return False
    if _near_negation(claim_text, claim) != _near_negation(source_text, source):
        return False
    return True


def _check_structured_values(claim: dict, cited_text: str, issues: list[dict]) -> None:
    claim_dates = _date_values(claim["sentence"])
    source_dates = _date_values(cited_text)
    claim_date_spans = _date_like_spans(claim["sentence"])
    source_date_spans = _date_like_spans(cited_text)
    reported_date_spans = set()
    for value in claim_dates:
        span_key = (value["start"], value["end"], value["raw"])
        matches = [candidate for candidate in source_dates if candidate["value"] == value["value"]]
        if not matches:
            if span_key not in reported_date_spans:
                issues.append(_issue("date_evidence_unclear", "medium", claim["line"],
                                     f"날짜 {value['raw']}의 원문 근거가 명확하지 않아 검토가 필요합니다."))
                reported_date_spans.add(span_key)
        elif not any(_context_compatible(claim["sentence"], value, cited_text, candidate) for candidate in matches):
            if span_key not in reported_date_spans:
                issues.append(_issue("date_context_unclear", "medium", claim["line"],
                                     f"날짜 {value['raw']}가 원문과 다른 문맥일 수 있어 검토가 필요합니다."))
                reported_date_spans.add(span_key)

    # 연도가 생략된 월·일 및 잘못된 달력 날짜는 수치로 통과시키지 않는다.
    # _date_values가 확정한 값으로 덮이지 않은 span은 보수적으로 날짜 검토를 남긴다.
    for span in claim_date_spans:
        span_key = (span["start"], span["end"], span["raw"])
        if (span_key not in reported_date_spans
                and not any(value["start"] <= span["start"] and span["end"] <= value["end"] for value in claim_dates)):
            issues.append(_issue("date_evidence_unclear", "medium", claim["line"],
                                 f"날짜 {span['raw']}의 원문 근거가 명확하지 않아 검토가 필요합니다."))
            reported_date_spans.add(span_key)

    # 값이 사실이라고 주장하지 않고 미검증·미측정 범위를 명시한 문장은
    # 그 숫자를 원문 수치 주장으로 승격하지 않는다.
    if _UNVERIFIED_SCOPE.search(claim["sentence"]):
        return
    claim_quantities = _quantity_values(claim["sentence"], claim_date_spans)
    source_quantities = _quantity_values(cited_text, source_date_spans)
    for value in claim_quantities:
        if value.get("unsupported_unit"):
            issues.append(_issue("numeric_evidence_unclear", "medium", claim["line"],
                                 f"수치·단위 {value['raw']} {value['unsupported_unit']}의 원문 근거가 명확하지 않아 검토가 필요합니다."))
            continue
        matches = [candidate for candidate in source_quantities
                   if not candidate.get("unsupported_unit")
                   and candidate["dimension"] == value["dimension"] and candidate["value"] == value["value"]]
        if not matches:
            signed = [candidate for candidate in source_quantities
                      if not candidate.get("unsupported_unit")
                      and candidate["dimension"] == value["dimension"]
                      and candidate["value"] == -value["value"]]
            if signed:
                issues.append(_issue("numeric_sign_context_unclear", "medium", claim["line"],
                                     f"수치·단위 {value['raw']}와 원문의 부호가 반대인 값이 있어 감소량 표현과의 관계를 의미 검토해야 합니다."))
            else:
                issues.append(_issue("numeric_evidence_unclear", "medium", claim["line"],
                                     f"수치·단위 {value['raw']}의 원문 근거가 명확하지 않아 검토가 필요합니다."))
        elif not any(_context_compatible(claim["sentence"], value, cited_text, candidate) for candidate in matches):
            issues.append(_issue("numeric_context_unclear", "medium", claim["line"],
                                 f"수치·단위 {value['raw']}가 원문과 다른 문맥일 수 있어 검토가 필요합니다."))


def verify_report(report: str, source_texts: dict[str, str], citation_checks: list[dict], sampling: dict | None,
                  checked_report: str | None, findings: list[dict], unresolved_finding_ids: list[str]) -> dict:
    """검토가 필요한 근거만 반환한다. 통과는 전체 보고서의 사실성 보증이 아니다."""
    issues = []
    if sampling is None:
        issues.append(_issue("sampling_metadata_missing", "medium", None, "이전 실행이라 인용 표본 범위와 판정 수가 기록되지 않았습니다."))
        scope = {"sampling": "legacy_unknown", "full_report_verification": False, "automatic_model_calls": False}
    else:
        selected = sampling.get("selected_count", len(sampling.get("samples", [])))
        checked = sampling.get("checked_count", len(citation_checks))
        unmatched = sampling.get("unmatched_count", 0)
        if checked < selected:
            issues.append(_issue("citation_sample_missing", "medium", None, f"인용 표본 {selected}개 중 {checked}개만 판정되었습니다."))
        if unmatched:
            issues.append(_issue("citation_check_unmatched", "medium", None, f"표본과 일치하지 않거나 중복된 판정 결과 {unmatched}개가 제외되었습니다."))
        scope = {"sampling": sampling.get("scope", "sample_only"), "eligible_count": sampling.get("eligible_count"),
                 "selected_count": selected, "checked_count": checked, "full_report_verification": False,
                 "automatic_model_calls": False}

    for check in citation_checks:
        if check.get("supported") is False:
            issues.append(_issue("citation_unsupported", "high", check.get("line"),
                                 f"인용 표본이 뒷받침되지 않음: {check.get('reason', '사유 미기록')}"))

    by_id = {finding.get("id"): finding for finding in findings}
    for finding_id in sorted(set(unresolved_finding_ids)):
        finding = by_id.get(finding_id, {})
        if finding.get("severity") == "high":
            issues.append(_issue("high_finding_unresolved", "high", None, f"고위험 지적 {finding_id}이 해결되지 않았습니다."))

    claims = _cited_claims(report)
    if checked_report is not None and _claim_keys(_cited_claims(checked_report)) != _claim_keys(claims):
        issues.append(_issue("cited_claim_changed_after_check", "medium", None,
                             "인용 검사 스냅샷 뒤 보고서의 인용 문장이 바뀌었습니다."))

    for claim in claims:
        cited_text = "\n".join(source_texts.get(source_id, "") for source_id in claim["cites"])
        # 작은따옴표는 영어 축약형(It's 등)과 구분하기 어려워 검사 범위에서 뺀다.
        for match in _DOUBLE_QUOTE.findall(claim["sentence"]):
            quoted = next(part for part in match if part)
            if cited_text and _quote_text(quoted) not in _quote_text(cited_text):
                issues.append(_issue("direct_quote_not_found", "high", claim["line"],
                                     "12자 이상 직접 인용이 인용 출처 원문에서 확인되지 않았습니다."))
            elif not cited_text:
                issues.append(_issue("direct_quote_unverified", "medium", claim["line"],
                                     "직접 인용의 출처 원문이 없어 확인하지 못했습니다."))
        _check_structured_values(claim, cited_text, issues)

    issues.sort(key=lambda item: (item["line"] is None, item["line"] or 0, item["kind"], item["message"]))
    return {"status": "review_required" if issues else "passed", "issues": issues, "scope": scope}


_MARKS = {"ko": {"judgment": "(판단)", "no_source": "(출처 없음)", "mismatch": "(출처 불일치)", "sources": "## 출처",
                 "claims": ("## 답", "## 근거", "## 반대 근거와 한계", "## 한계")},
          "en": {"judgment": "(judgment)", "no_source": "(no source)", "mismatch": "(source mismatch)", "sources": "## Sources",
                 "claims": ("## Answer", "## Evidence", "## Counter-evidence and limits", "## Limits")}}
_MARK_SPLIT = re.compile(r"(?<=[.!?。])(\s+)(?!\[S\d+\]|\((?:판단|출처 없음|출처 불일치|judgment|no source|source mismatch)\))")
_CITE_ID = re.compile(r"\[(S\d+)\]")


def _absent_values(sentence: str, cited_text: str) -> list[str]:
    """정규화한 날짜·수치가 인용 원문에 아예 없는 것만 돌려준다.

    검증 절의 *_evidence_unclear는 지원하지 않는 단위(MW 등)·연도 없는 날짜 같은 모호함도
    포함하므로 본문 표시에 쓰지 않는다. 모호한 값, 미검증 범위 문장, 문맥·부호 차이는
    검증 절의 검토로만 남긴다."""
    claim_spans = _date_like_spans(sentence)
    source_dates = {value["value"] for value in _date_values(cited_text)}
    absent = [value["raw"] for value in _date_values(sentence) if value["value"] not in source_dates]
    if _UNVERIFIED_SCOPE.search(sentence):
        return absent
    source = [value for value in _quantity_values(cited_text, _date_like_spans(cited_text)) if not value.get("unsupported_unit")]
    for value in _quantity_values(sentence, claim_spans):
        if value.get("unsupported_unit"):
            continue
        if not any(c["dimension"] == value["dimension"] and abs(c["value"]) == abs(value["value"]) for c in source):
            absent.append(value["raw"])
    return absent


# 본문 표시용 증감 낱말은 검증 절의 _DIRECTIONS보다 좁게 둔다('늘'·'줄'은 '오늘'·'줄곧'에도 걸린다).
_UP_MARK = re.compile(r"\b(?:increase[sd]?|increasing|rose|rises?|grew|grows?|higher)\b|증가|늘었|늘어|늘렸|상승", re.I)
_DOWN_MARK = re.compile(r"\b(?:decrease[sd]?|decreasing|fell|falls?|declined?|reduced?|dropped)\b|감소|줄었|줄어|줄였|하락|낮췄|낮아", re.I)
_SOURCE_SPLIT = re.compile(r"(?<=[.!?。])\s+|\n+")
_EN_CONTEXT_STOP = {"that", "with", "from", "this", "were", "have", "been", "than", "which", "about", "over", "after", "into",
                    "their", "percent", "compared", "they", "said", "also", "only", "during", "under", "same", "year",
                    "years", "median", "average", "report", "reports", "notes", "source"}


def _plain_claim(sentence: str) -> str:
    text = _CITE_ID.sub("", sentence)
    text = re.sub(r"\((?:S\d+[:·][^)]*|판단|출처 없음|출처 불일치|judgment|no source|source mismatch)\)", "", text)
    return text.strip()


def _direction_of(text: str) -> str:
    up, down = bool(_UP_MARK.search(text)), bool(_DOWN_MARK.search(text))
    return "up" if up and not down else "down" if down and not up else ""


def _content_stems(text: str) -> set[str]:
    """문맥 비교용 낱말. 영어는 4글자 이상 낱말, 한국어는 어절 앞 두 글자(조사 차이를 넘기려는 근사)."""
    text = _UP_MARK.sub(" ", _DOWN_MARK.sub(" ", re.sub(r"\d[\d,.]*", " ", text)))
    return ({w.lower() for w in re.findall(r"[A-Za-z]{4,}", text)} - _EN_CONTEXT_STOP) | {w[:2] for w in re.findall(r"[가-힣]{2,}", text)}


def _char_bigrams(text: str) -> set[str]:
    compact = re.sub(r"[^0-9a-z가-힣]", "", text.lower())
    return {compact[i:i + 2] for i in range(len(compact) - 1)}


def _value_conflicts(sentence: str, cited_text: str) -> list[str]:
    """원문에 같은 값이 있어도 독자를 오도하는 경우만 돌려준다(확정에 가까운 신호만).

    - direction: 같은 값이 든 원문 문장(값이 없으면 2-gram 60% 이상 겹치는 가장 가까운 문장)이
      모두 주장과 반대 증감 방향만 말한다.
    - context: 주장의 수치가 든 원문 문장 어디에도 주장의 문맥 낱말이 하나도 없다(같은 문자 체계일 때만;
      번역 인용을 낱말 비교로 불일치라 단정하지 않는다).
    - causal: 원문이 유보·부정한 인과를 주장이 단정한다.
    - period: 같은 수치를 원문과 다른 기간 단위(하루·한 달·연간·총계)로 말한다.
    - plan: 원문이 계획·목표·전망으로만 말한 수치를 유보 없이 말한다(계획을 실적처럼).
    - scope: 원문의 시범·표본 범위 수치를 전역·전체 결과로 말한다."""
    plain = _plain_claim(sentence)
    sents = [s.strip() for s in _SOURCE_SPLIT.split(cited_text) if s.strip()]
    if not plain or not sents:
        return []
    claim_values = [v for v in _quantity_values(plain, _date_like_spans(plain)) if not v.get("unsupported_unit")]

    def holders(value: dict) -> list[str]:
        return [s for s in sents if any(c["dimension"] == value["dimension"] and abs(c["value"]) == abs(value["value"])
                                        for c in _quantity_values(s, _date_like_spans(s)) if not c.get("unsupported_unit"))]

    found = []
    claim_dir = _direction_of(plain)
    if claim_dir:
        anchored = list(dict.fromkeys(s for v in claim_values for s in holders(v)))
        if not anchored:
            grams = _char_bigrams(plain)
            best = max(sents, key=lambda s: len(grams & _char_bigrams(s)))
            if grams and len(grams & _char_bigrams(best)) / len(grams) >= 0.6:
                anchored = [best]
        if anchored and all(_direction_of(s) not in ("", claim_dir) for s in anchored):
            found.append("direction")
    stems = _content_stems(plain)
    if stems and not _UNVERIFIED_SCOPE.search(plain):
        for value in claim_values:
            held = holders(value)
            if (held and all(_scripts(s) == _scripts(plain) for s in held)
                    and not any(any(t in s.lower() for t in stems) for s in held)):
                found.append("context")
                break
    if _causal_overclaim(plain, sents):
        found.append("causal")
    if _period_conflict(plain, sents):
        found.append("period")
    if _plan_overclaim(plain, sents):
        found.append("plan")
    if _scope_overclaim(plain, sents):
        found.append("scope")
    return found


# 인과 단정: 원문이 인과를 명시적으로 유보·부정할 때만 본문에 표시한다(인과 낱말이 없을 뿐인 원문은 표시하지 않음 —
# 바꿔 말한 인과 서술을 낱말 목록으로 단정하지 않으려는 보수적 선택).
_CAUSAL_CLAIM = re.compile(r"\b(?:caus(?:e|es|ed|ing)|because|due to|led to|leads? to|result(?:s|ed)? in|thanks to|drove|"
                           r"driven by|attribut\w*|as a result)\b|덕분|때문|인해|탓에|탓으로|기여했|이끌었|낳았|결과로", re.I)
_CAUSAL_ANY = re.compile(_CAUSAL_CLAIM.pattern + r"|\b(?:effects?|impacts?|contribut\w*)\b|인과|영향|효과|기여", re.I)
_CAUSAL_DISCLAIM = re.compile(
    r"\b(?:cannot|can't|could not|did not|does not|do not|not|unable to)\s+(?:\w+\s+){0,2}?"
    r"(?:establish|determine|show|prove|isolate|distinguish|separate|attribute)\w*|\bobservational\b|\bcorrelation\b|"
    r"인과[^.]*?(?:않|못|없)|(?:구분|확인|분석|판단|입증)하지\s*(?:않|못)|(?:구분|입증)할 수 없", re.I)
# 기간 단위: 같은 수치를 원문과 다른 기간(하루·주·한 달·연간·총계)으로 말하는지 본다.
_PERIOD_WORDS = {"day": r"하루|일평균|일일|매일|\bper day\b|\ba day\b|\bdaily\b|\beach day\b",
                 "week": r"주당|매주|일주일|\bper week\b|\bweekly\b|\ba week\b",
                 "month": r"한 달|월평균|매월|월간|\bper month\b|\bmonthly\b|\ba month\b",
                 "year": r"연간|연평균|매년|해마다|\bper year\b|\ba year\b|\bannual(?:ly)?\b|\byearly\b|\beach year\b",
                 "total": r"(?:^|\s)총\s?\d|누적|\bin total\b|\btotal\b|\bcumulative\b|\baltogether\b"}


_CLAUSE_BREAK = re.compile(r"[,;:()]|(?<=[.!?。])\s")


def _clause_around(text: str, value: dict) -> tuple[int, str]:
    """수치가 든 절(쉼표·쌍반점·괄호 등으로 끊음)의 시작 위치와 내용."""
    start = max((m.end() for m in _CLAUSE_BREAK.finditer(text, 0, value["start"])), default=0)
    stop = next((m.start() for m in _CLAUSE_BREAK.finditer(text, value["end"])), len(text))
    return start, text[start:stop]


def _periods_of(text: str) -> set[str]:
    return {name for name, pattern in _PERIOD_WORDS.items() if re.search(pattern, text, re.I)}


def _value_period(text: str, value: dict) -> set[str]:
    """수치가 든 절(쉼표·쌍반점 등으로 끊음)의 기간 단위. 한 절에 여러 개면 수치에 가장 가까운 것 하나만 본다.

    한 문장에 '하루 평균 100명, 총 3,000명'처럼 기간이 다른 수치가 같이 있어도 값마다 제 기간을 붙이려는 것이다
    (PR #14 Codex 리뷰 반영)."""
    start, clause = _clause_around(text, value)
    found = [(min(abs(m.start() + start - value["start"]), abs(m.end() + start - value["end"])), name)
             for name, pattern in _PERIOD_WORDS.items() for m in re.finditer(pattern, clause, re.I)]
    return {min(found)[1]} if found else set()


def _causal_overclaim(plain: str, sents: list[str]) -> bool:
    """주장이 인과를 단정하는데, 인용 원문이 인과를 유보·부정하는 문장을 담고 인과를 긍정하는 문장은 없으면 True."""
    if not _CAUSAL_CLAIM.search(plain) or _CAUSAL_DISCLAIM.search(plain):
        return False
    # 인과를 긍정하는 원문 문장은 주장과 같은 대상(문맥 낱말 공유)을 말할 때만 근거로 친다(PR #14 Codex 리뷰 반영).
    stems = _causal_stems(plain)
    return (any(_CAUSAL_DISCLAIM.search(s) for s in sents)
            and not any(_CAUSAL_ANY.search(s) and not _CAUSAL_DISCLAIM.search(s) and stems & _causal_stems(s)
                        for s in sents))


def _causal_stems(text: str) -> set[str]:
    return _content_stems(_CAUSAL_ANY.sub(" ", text))


def _period_conflict(plain: str, sents: list[str]) -> bool:
    """주장 수치의 기간 단위가 같은 값이 나오는 원문 자리마다의 기간 단위와 하나도 겹치지 않으면 True(값마다 제 절의 기간)."""
    for value in _quantity_values(plain, _date_like_spans(plain)):
        claim_periods = _value_period(plain, value)
        if value.get("unsupported_unit") or not claim_periods:
            continue
        held = [_value_period(s, c) for s in sents for c in _quantity_values(s, _date_like_spans(s))
                if not c.get("unsupported_unit") and c["dimension"] == value["dimension"]
                and abs(c["value"]) == abs(value["value"])]
        if held and all(p and not (p & claim_periods) for p in held):
            return True
    return False


# 계획·목표의 실적화: 원문이 앞으로의 계획·목표·전망으로만 말한 수치를 유보 없이 이룬 것처럼 쓰는지 본다.
# 추정(estimate·추정)을 떼는 경우는 오표시 위험이 커서 아직 표시하지 않는다(백로그).
_PLAN_WORDS = re.compile(r"\b(?:plan(?:s|ned|ning)?|target(?:s|ed)?|aim(?:s|ed)?|goal|expect(?:s|ed)?|project(?:ed|ion|ions)|"
                         r"forecast\w*|propos\w*|intend\w*|will)\b|계획|목표|예정|전망|예상|방침", re.I)
# 범위 일반화: 시범·표본 범위 결과를 전역·전체 결과로 쓰는지 본다.
_WIDE_SCOPE = re.compile(
    r"\b(?:nationwide|citywide|statewide|countrywide|across (?:the )?(?:entire )?(?:city|country|nation|state|region)|"
    r"(?:all|every) (?:residents?|households?|schools?|districts?|neighbou?rhoods?|branches|users|citizens|workers|employees|"
    r"cities|regions|counties))\b|전국|전\s?국민|시\s?전역|전역|전 지역|도시 전체|시 전체|"
    r"모든\s?(?:시민|주민|가구|학교|지역|구|지점|사업장|이용자|노동자|직원)", re.I)
_NARROW_SCOPE = re.compile(
    r"\b(?:pilot|sample[sd]?|survey(?:ed)?|respondents?|participat\w*|selected)\b|"
    r"\b(?:two|three|four|five|six|\d+) (?:districts?|neighbou?rhoods?|branches|schools|sites|cities|counties)\b|"
    r"시범|표본|응답자|설문|참여한|참가한|선정된|\d+\s?(?:개|곳)\s?(?:구|동|지점|학교|단지|지역)", re.I)


def _same_value_spots(sents: list[str], value: dict) -> list[tuple[str, dict]]:
    return [(s, c) for s in sents for c in _quantity_values(s, _date_like_spans(s))
            if not c.get("unsupported_unit") and c["dimension"] == value["dimension"] and abs(c["value"]) == abs(value["value"])]


def _plan_overclaim(plain: str, sents: list[str]) -> bool:
    """주장 수치가 원문에서는 매번 계획·목표·전망을 말하는 절에만 나오는데, 주장은 그런 유보 없이 말하면 True."""
    if _PLAN_WORDS.search(plain):
        return False
    for value in _quantity_values(plain, _date_like_spans(plain)):
        if value.get("unsupported_unit"):
            continue
        spots = _same_value_spots(sents, value)
        if spots and all(_PLAN_WORDS.search(_clause_around(s, c)[1]) for s, c in spots):
            return True
    return False


def _scope_overclaim(plain: str, sents: list[str]) -> bool:
    """주장이 전역·전체 범위를 말하는데, 주장 수치가 든 원문 문장이 모두 시범·표본 범위만 말하고 전역 낱말은 없으면 True."""
    if not _WIDE_SCOPE.search(plain):
        return False
    held = list(dict.fromkeys(s for value in _quantity_values(plain, _date_like_spans(plain))
                              if not value.get("unsupported_unit") for s, _ in _same_value_spots(sents, value)))
    return bool(held) and all(_NARROW_SCOPE.search(s) and not _WIDE_SCOPE.search(s) for s in held)


# 본문 유사 묶음 경고(gates._SIMILAR_NOTE)가 붙은 겹침 인용에서 '독립 출처'라고 단정하는 표현.
_SIMILAR_WARNED = re.compile(r"\(S\d+(?:·S\d+)+: [^)]*(?:독립 출처가 아닐 수 있음|may not be independent)[^)]*\)")
_INDEPENDENCE_CLAIM = re.compile(
    r"독립(?:적인|된|적으로)?\s*(?:출처|자료|근거|조사|보도|확인)|서로 다른 (?:두|세|여러) (?:출처|자료)|(?:두|세|여러) 출처(?:가|가 모두|모두)\b|"
    r"\bindependent(?:ly)?\b|\b(?:two|three|both|multiple|several) (?:separate |different )?sources\b", re.IGNORECASE)


def _independence_overclaim(sentence: str) -> bool:
    """복제 후보 출처를 겹쳐 인용하면서 문장이 그 출처들을 독립 근거라고 말하면 True."""
    return bool(_SIMILAR_WARNED.search(sentence)) and bool(_INDEPENDENCE_CLAIM.search(_SIMILAR_WARNED.sub("", sentence)))


def _with_mark(sentence: str, mark: str) -> str:
    """문장 끝 구두점 앞에 표시를 넣는다. 구두점 뒤 인용이 있으면 맨 끝에 붙인다."""
    body = sentence.rstrip()
    trailing = sentence[len(body):]
    if body and body[-1] in ".!?。":
        return body[:-1].rstrip() + f" {mark}" + body[-1] + trailing
    return body + f" {mark}" + trailing


def _with_mismatch(sentence: str, mark: str) -> str:
    """끝 인용 묶음 앞에 표시를 넣는다. 인용 문장 분리기가 ']' 뒤에서 끊어도 표시가 같은 문장에 남는다."""
    tail = re.search(r"[ \t]*(?:\[S\d+\][ \t]*)+(?:\([^()]*\))?[ \t]*[.!?。]?\s*$", sentence)
    if not tail or not tail.group(0).strip().startswith("[S"):
        return _with_mark(sentence, mark)
    head = sentence[:tail.start()].rstrip()
    if head and head[-1] in ".!?。":        # "문장. [S1]" 꼴은 구두점 앞에 넣는다
        return head[:-1].rstrip() + f" {mark}" + head[-1] + " " + tail.group(0).lstrip()
    return head + f" {mark} " + tail.group(0).lstrip()


def _trusted_cited_claims(report: str, source_texts: dict[str, str], M: dict) -> list[tuple[str, set[str]]]:
    """답·근거·한계 절에서 인용이 있고 원문 대조에 걸리지 않은 문장의 (증감 방향, 문맥 낱말) 목록."""
    return [(direction, stems) for direction, stems, _ in _trusted_cited_rows(report, source_texts, M)]


def _trusted_cited_rows(report: str, source_texts: dict[str, str], M: dict) -> list[tuple[str, set[str], tuple[str, ...]]]:
    out, section, fenced = [], "", False
    for line in report.split("\n"):
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            fenced = not fenced
        if stripped.startswith("## "):
            section = stripped
        if fenced or section not in M["claims"] or stripped.startswith(("```", "~~~", "|", "#")) or not stripped:
            continue
        body = re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", line)
        for piece in _MARK_SPLIT.split(body)[::2]:
            cites = list(dict.fromkeys(_CITE_ID.findall(piece)))
            if not cites or M["mismatch"] in piece:
                continue
            cited_text = "\n".join(source_texts.get(c, "") for c in cites)
            plain = _plain_claim(piece)
            direction = _direction_of(plain)
            if (direction and cited_text.strip() and not _absent_values(piece, cited_text)
                    and not _value_conflicts(piece, cited_text)):
                out.append((direction, _content_stems(plain), tuple(cites)))
    return out


def _contradicts_cited(piece: str, trusted: list[tuple[str, set[str]]]) -> bool:
    """같은 대상(문맥 낱말 2개 이상 공유)을 말하는 믿을 만한 인용 문장과 증감 방향이 반대면 True."""
    plain = _plain_claim(piece)
    direction = _direction_of(plain)
    if not direction:
        return False
    stems = _content_stems(plain)
    return any(d != direction and len(stems & other) >= 2 for d, other in trusted)


def mark_report_claims(report: str, source_texts: dict[str, str], lang: str = "ko") -> tuple[str, dict]:
    """독자가 경고 없이 읽게 되는 근거 문제를 본문 문장에 직접 표시한다.

    - 인용 문장의 숫자·날짜가 인용 원문에 없으면 '(출처 불일치)'
    - 인용 문장이 원문 값과 반대 증감 방향을 말하거나, 수치가 원문의 전혀 다른 문맥에서 왔으면 '(출처 불일치)'
    - 답·근거·한계 절의 인용도 판단 표시도 없는 사실 문장에는 '(출처 없음)'
    - 본문 유사(복제 후보) 출처를 겹쳐 인용하며 '독립 출처'라고 말하면 '(출처 불일치)'
    - '(판단)'만 붙었지만 어떤 출처에도 없는 수치·날짜를 단정하는 문장에도 '(출처 없음)'
    - 인용이 원문이 유보한 인과를 단정하거나 수치를 원문과 다른 기간 단위로 말하면 '(출처 불일치)'
    - 인용 없는 문장(판단 포함)이 같은 대상의 인용 문장과 반대 방향이거나 출처 수치를 다른 기간으로 말하면 '(출처 불일치)'
    - 인용 문장이 원문의 계획·목표 수치를 이룬 것처럼, 시범·표본 범위 수치를 전역 결과처럼 말하면 '(출처 불일치)'
    표, 코드, 출처 절은 건드리지 않는다. 다시 돌려도 결과가 같다.
    반환: (표시한 본문, {"mismatch", "no_source", "direction_conflict", "context_conflict", "independence_conflict",
    "causal_conflict", "period_conflict", "internal_conflict", "plan_conflict", "scope_conflict": 문장 목록})."""
    M = _MARKS.get(lang, _MARKS["ko"])
    marks = (M["judgment"], M["no_source"], M["mismatch"])
    changes: dict[str, list[str]] = {"mismatch": [], "no_source": [], "direction_conflict": [], "context_conflict": [],
                                     "independence_conflict": [], "causal_conflict": [], "period_conflict": [],
                                     "internal_conflict": [], "plan_conflict": [], "scope_conflict": []}
    all_text = "\n".join(source_texts.values())
    all_values = [v for v in _quantity_values(all_text, _date_like_spans(all_text)) if not v.get("unsupported_unit")]
    all_dates = {d["value"] for d in _date_values(all_text)}
    all_sents = [x.strip() for x in _SOURCE_SPLIT.split(all_text) if x.strip()]
    trusted = _trusted_cited_claims(report, source_texts, M)
    out, section, fenced = [], "", False
    for line in report.split("\n"):
        stripped = line.strip()
        if stripped.startswith(("```", "~~~")):
            fenced = not fenced
        if fenced or stripped.startswith(("```", "~~~", "|", "#")) or not stripped:
            if stripped.startswith("## "):
                section = stripped
            out.append(line)
            continue
        if section == M["sources"]:
            out.append(line)
            continue
        claim_section = section in M["claims"]
        lead = re.match(r"^\s*(?:[-*]|\d+\.)\s+|^\s*", line).group(0)
        pieces = _MARK_SPLIT.split(line[len(lead):])
        fixed = []
        for index, piece in enumerate(pieces):
            if (not index % 2 and claim_section and M["judgment"] in piece
                    and not any(m in piece for m in marks[1:]) and not _CITE_ID.search(piece)
                    and not _UNVERIFIED_SCOPE.search(piece)
                    and (any(not any(c["dimension"] == v["dimension"] and abs(c["value"]) == abs(v["value"]) for c in all_values)
                             for v in _quantity_values(piece, _date_like_spans(piece)) if not v.get("unsupported_unit"))
                         or any(d["value"] not in all_dates for d in _date_values(piece)))):
                # 판단 표시는 해석에 쓰는 것이다. 어떤 출처에도 없는 수치·날짜를 단정하면 출처 없는 사실로 본다.
                changes["no_source"].append(piece.strip())
                fixed.append(_with_mark(piece, M["no_source"]))
                continue
            if (not index % 2 and claim_section and piece.strip() and not _CITE_ID.search(piece)
                    and not any(m in piece for m in marks[1:]) and not _UNVERIFIED_SCOPE.search(piece)):
                # 인용 없는 문장(판단 포함)이 같은 대상을 말하는 인용 문장과 반대 방향이거나, 출처 수치를 다른 기간으로 말하면
                # 출처와 어긋난 문장이다. '(출처 없음)'보다 강한 '(출처 불일치)'를 붙인다.
                kinds = (["internal"] if _contradicts_cited(piece, trusted) else []) + \
                        (["period"] if _period_conflict(_plain_claim(piece), all_sents) else [])
                if kinds:
                    changes["mismatch"].append(piece.strip())
                    for kind in kinds:
                        changes[f"{kind}_conflict"].append(piece.strip())
                    fixed.append(_with_mark(piece, M["mismatch"]))
                    continue
            if index % 2 or not piece.strip() or any(m in piece for m in marks):
                fixed.append(piece)
                continue
            cites = list(dict.fromkeys(_CITE_ID.findall(piece)))
            if cites:
                cited_text = "\n".join(source_texts.get(c, "") for c in cites)
                conflicts = _value_conflicts(piece, cited_text) if cited_text.strip() else []
                if _independence_overclaim(piece):
                    conflicts.append("independence")
                if cited_text.strip() and (_absent_values(piece, cited_text) or conflicts):
                    changes["mismatch"].append(piece.strip())
                    for kind in conflicts:
                        changes[f"{kind}_conflict"].append(piece.strip())
                    piece = _with_mismatch(piece, M["mismatch"])
            elif (claim_section and not piece.rstrip().endswith(":")
                  and len(re.sub(r"\W", "", piece)) >= 8):
                changes["no_source"].append(piece.strip())
                piece = _with_mark(piece, M["no_source"])
            fixed.append(piece)
        out.append(lead + "".join(fixed))
    return "\n".join(out), changes


_CONFLICT_ROW = {"ko": "- 출처끼리 상충: {a}·{b}를 인용한 문장이 같은 대상의 증감을 서로 반대로 말하므로 두 원문의 범위·기간·측정 방식을 확인해야 한다 {j}.",
                 "en": "- Sources disagree: sentences citing {a} and {b} give opposite directions for the same subject, so check each source's scope, period and method {j}."}


def note_source_conflicts(report: str, source_texts: dict[str, str], lang: str = "ko", limit: int = 3) -> tuple[str, list[list[str]]]:
    """서로 다른 출처를 인용한 두 문장이 같은 대상(문맥 낱말 2개 이상 공유)을 반대 증감 방향으로 말하는데
    한계 절이 두 출처를 함께 언급하지 않으면, 한계 절 끝에 상충 안내 한 줄을 '(판단)'으로 덧붙인다.

    출처끼리 다른 결과는 정당한 서술이라 본문에 불일치 표시를 하지 않고 독자에게 상충을 알리기만 한다.
    한계 절이 없으면 아무것도 하지 않는다. 다시 돌려도 같다. 반환: (본문, 덧붙인 출처 쌍 목록)."""
    M = _MARKS.get(lang, _MARKS["ko"])
    lines = report.split("\n")
    limits = M["claims"][2:]
    index = next((i for i, line in enumerate(lines) if line.strip() in limits), None)
    if index is None:
        return report, []
    end = next((j for j in range(index + 1, len(lines)) if lines[j].startswith("#")), len(lines))
    section = "\n".join(lines[index + 1:end])
    rows = _trusted_cited_rows(report, source_texts, M)
    pairs: list[list[str]] = []
    for i, (d1, stems1, cites1) in enumerate(rows):
        for d2, stems2, cites2 in rows[i + 1:]:
            if d1 == d2 or set(cites1) & set(cites2) or len(stems1 & stems2) < 2:
                continue
            pair = sorted({cites1[0], cites2[0]}, key=lambda c: int(c[1:]))
            mentioned = all(re.search(rf"(?<![A-Za-z0-9]){c}(?!\d)", section) for c in pair)
            if pair not in pairs and not mentioned:
                pairs.append(pair)
    pairs = pairs[:limit]
    if not pairs:
        return report, []
    added = [_CONFLICT_ROW.get(lang, _CONFLICT_ROW["ko"]).format(a=a, b=b, j=M["judgment"]) for a, b in pairs]
    last = end
    while last > index + 1 and not lines[last - 1].strip():
        last -= 1
    lines[last:last] = added
    return "\n".join(lines), pairs
