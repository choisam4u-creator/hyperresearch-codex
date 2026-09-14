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
_UNITS = ("milliseconds", "millisecond", "seconds", "second", "minutes", "minute", "hours", "hour",
          "GB", "MB", "TB", "KRW", "USD", "km", "kg", "ms", "%", "년", "월", "일", "명", "건", "개", "배",
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
_UNIT_SCALE = {
    "ms": ("time", Decimal("0.001")), "millisecond": ("time", Decimal("0.001")), "milliseconds": ("time", Decimal("0.001")),
    "s": ("time", Decimal("1")), "second": ("time", Decimal("1")), "seconds": ("time", Decimal("1")), "초": ("time", Decimal("1")),
    "minute": ("time", Decimal("60")), "minutes": ("time", Decimal("60")), "분": ("time", Decimal("60")),
    "hour": ("time", Decimal("3600")), "hours": ("time", Decimal("3600")), "시간": ("time", Decimal("3600")),
    "m": ("length", Decimal("1")), "km": ("length", Decimal("1000")),
    "g": ("mass", Decimal("1")), "kg": ("mass", Decimal("1000")),
    "%": ("percent", Decimal("1")), "gb": ("data_decimal", Decimal("1000")), "mb": ("data_decimal", Decimal("1")),
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
    for pattern_index, pattern in enumerate(_DATE_PATTERNS):
        for match in pattern.finditer(text):
            try:
                if pattern_index == 2:
                    year, month, day = int(match.group(3)), _MONTHS[match.group(1).lower()], int(match.group(2))
                else:
                    year, month, day = map(int, match.groups())
                value = dt.date(year, month, day).isoformat()
            except (ValueError, KeyError):
                continue
            values.append({"raw": match.group(0), "value": value, "start": match.start(), "end": match.end()})
    return sorted(values, key=lambda item: item["start"])


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
        values.append({"raw": raw, "value": number * scale, "dimension": dimension,
                       "start": match.start(), "end": match.end()})
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
    for value in claim_dates:
        matches = [candidate for candidate in source_dates if candidate["value"] == value["value"]]
        if not matches:
            issues.append(_issue("date_evidence_unclear", "medium", claim["line"],
                                 f"날짜 {value['raw']}의 원문 근거가 명확하지 않아 검토가 필요합니다."))
        elif not any(_context_compatible(claim["sentence"], value, cited_text, candidate) for candidate in matches):
            issues.append(_issue("date_context_unclear", "medium", claim["line"],
                                 f"날짜 {value['raw']}가 원문과 다른 문맥일 수 있어 검토가 필요합니다."))

    claim_quantities = _quantity_values(claim["sentence"], claim_dates)
    source_quantities = _quantity_values(cited_text, source_dates)
    for value in claim_quantities:
        matches = [candidate for candidate in source_quantities
                   if candidate["dimension"] == value["dimension"] and candidate["value"] == value["value"]]
        if not matches:
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
