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
_UNITS = ("percentage points", "percentage point", "percent", "milliseconds", "millisecond", "seconds", "second", "minutes", "minute", "hours", "hour",
          "mWh", "mW", "kWh", "Wh", "kW", "W", "GB", "MB", "TB", "KRW", "USD", "km", "kg", "ms", "%p", "%", "개소", "년", "월", "일", "명", "건", "곳", "대", "회", "종", "개", "배",
          "원", "달러", "초", "분", "시간", "m", "g", "s")
# "%p"·"%포인트"·"percentage points"도 퍼센트 차원의 값으로 읽는다. 퍼센트와 퍼센트포인트의 구분은 _percent_point_conflict가 따로 본다.
# 자릿수 낱말: "420억 원"과 "420만 원", "4.2 million"과 "4.2 billion"은 숫자 글자가 같아도 다른 값이다. 값에 곱해 비교하므로
# "1.6 million"과 "1,600,000"은 같은 값으로 본다. "만큼"·"만에"의 '만'은 자릿수가 아니다.
_MAGNITUDES = {"천": 10**3, "만": 10**4, "십만": 10**5, "백만": 10**6, "천만": 10**7, "억": 10**8, "십억": 10**9, "백억": 10**10,
               "천억": 10**11, "조": 10**12, "thousand": 10**3, "million": 10**6, "billion": 10**9, "trillion": 10**12}
# 수치 하나를 읽는 순서(2026-10-07 2회차): 숫자 → 한국어 복합 자릿수("1억 2천만", "4천5백만", "3만 5천", "1조 5,000억") 또는
# 영어 자릿수 낱말·약어("3.8 million", "$3.8M", "2.5bn", "12k") → 단위. 같은 값의 다른 표기를 같은 값으로 읽어 맞는 환산에
# '(출처 불일치)'가 붙지 않게 하고, 약어로 바꾼 자릿수("4.6 million"→"$4.6bn")도 값으로 비교한다. 소문자 m·b는 통화 기호
# 바로 뒤 숫자에만 자릿수로 본다(그 밖의 "3.8 m"은 미터). 대문자 M·B·K와 k는 숫자에 붙어 있고 뒤에 영문자가 없을 때만
# 자릿수다("5MB"는 단위 MB).
_NUMBER_START = re.compile(r"(?<![A-Za-z0-9])[-+]?\d+(?:,\d{3})*(?:\.\d+)?")
_NUMBER_PART = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
_KO_BIG = {"만": 10**4, "억": 10**8, "조": 10**12}
_KO_SMALL = {"천": 1000, "백": 100, "십": 10}
_KO_TOKEN = re.compile(r"(\s?\d+(?:,\d{3})*(?:\.\d+)?)?(\s?)([천백십만억조])")
_EN_MAGNITUDE = re.compile(r"\s+(thousand|million|billion|trillion)(?![A-Za-z])|(\s?(?:bn|mn|mln|tn)|[KMBk])(?![A-Za-z])", re.I)
_EN_ABBREVIATIONS = {"k": 10**3, "m": 10**6, "mn": 10**6, "mln": 10**6, "b": 10**9, "bn": 10**9, "tn": 10**12}
_CURRENCY_LEAD = re.compile(r"[$€£₩]\s?$")
_UNIT_TAIL = re.compile(r"\s*(?:" + "|".join(re.escape(unit) for unit in _UNITS) + r")(?![A-Za-z0-9])", re.IGNORECASE)


def _korean_compound(text: str, pos: int, first: Decimal) -> tuple[Decimal, int] | None:
    """숫자 바로 뒤의 한국어 자릿수 묶음을 읽어 (값, 끝 위치)를 돌려준다. 자릿수가 없으면 None.

    큰 자릿수(조·억·만)는 내림차순, 묶음 안의 작은 자릿수(천·백·십)도 내림차순이어야 이어 읽는다. "만큼"·"만에"의 '만',
    낱말 첫 글자인 '십'·'백'(예: "10 백신")은 자릿수가 아니다."""
    total, group, pending, end = Decimal(0), Decimal(0), first, pos
    last_big, last_small, used = 10**13, 10**4, False
    while True:
        m = _KO_TOKEN.match(text, end)
        if not m:
            break
        number, space, unit = m.group(1), m.group(2), m.group(3)
        after = text[m.end():m.end() + 1]
        if number is not None:
            if pending is not None:
                break   # 숫자 두 개가 자릿수 없이 이어짐
            pending = Decimal(number.strip().replace(",", ""))
            if number[0].isspace() and not used:
                break
        if unit == "만" and re.match(r"큼|에(?![가-힣])", text[m.end():]):
            break
        if unit in _KO_SMALL:
            # 작은 자릿수는 숫자에 붙어 있어야 하고, 뒤가 다른 낱말이면 자릿수가 아니다("10 백신", "5천안").
            if space or (re.match(r"[가-힣]", after) and after not in "천백십만억조명원곳개건대회종배가"):
                break
            if _KO_SMALL[unit] >= last_small or pending is None:
                break
            group += pending * _KO_SMALL[unit]
            last_small, pending = _KO_SMALL[unit], None
        else:
            value = _KO_BIG[unit]
            if value >= last_big:
                break
            group += pending or 0
            if group == 0:
                break
            total += group * value
            group, pending, last_big, last_small = Decimal(0), None, value, 10**4
        used, end = True, m.end()
    if not used:
        return None
    return total + group + (pending or 0), end


def _read_number(text: str, match: re.Match) -> tuple[Decimal, int] | None:
    """숫자 하나와 뒤따르는 자릿수를 읽어 (값, 끝 위치)를 돌려준다."""
    try:
        number = Decimal(match.group(0).replace(",", ""))
    except InvalidOperation:
        return None
    end = match.end()
    compound = _korean_compound(text, end, number)
    if compound:
        return compound
    en = _EN_MAGNITUDE.match(text, end)
    if en:
        if en.group(1):
            return number * _MAGNITUDES[en.group(1).lower()], en.end()
        abbr = en.group(2).strip()
        if abbr in ("K", "k", "M", "B") or abbr.lower() in ("bn", "mn", "mln", "tn"):
            return number * _EN_ABBREVIATIONS[abbr.lower()], en.end()
    lead = _CURRENCY_LEAD.search(text, 0, match.start())
    if lead:
        cur = re.match(r"([mb])(?![A-Za-z])", text[end:])
        if cur:
            return number * _EN_ABBREVIATIONS[cur.group(1)], end + 1
    return number, end


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
    "%": ("percent", Decimal("1")), "percent": ("percent", Decimal("1")), "%p": ("percent", Decimal("1")),
    "percentage point": ("percent", Decimal("1")), "percentage points": ("percent", Decimal("1")), "gb": ("data_decimal", Decimal("1000")), "mb": ("data_decimal", Decimal("1")),
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


_YEAR_RANGE_HEAD = re.compile(r"\s*[~–—-]\s*(?:19|20)\d\d\s*년")
_PER_UNIT_TAIL = re.compile(r"\s?(?:인|명|가구|세대|곳|개소)당")


def _quantity_values(text: str, excluded: list[dict]) -> list[dict]:
    values = []
    excluded_spans = [(item["start"], item["end"]) for item in excluded]
    pos = 0
    while True:
        match = _NUMBER_START.search(text, pos)
        if not match:
            break
        pos = match.end()
        if any(start <= match.start() < end for start, end in excluded_spans):
            continue
        read = _read_number(text, match)
        if not read:
            continue
        number, end = read
        unit_match = _UNIT_TAIL.match(text, end)
        unit = unit_match.group(0).strip().lower() if unit_match else ""
        stop = unit_match.end() if unit_match else end
        if re.match(r"[A-Za-z0-9]", text[stop:stop + 1]):
            continue   # "4.2xyz"처럼 영문·숫자가 바로 붙은 수는 수량으로 읽지 않는다
        pos = stop
        raw = text[match.start():stop]
        if raw == "1" and _PER_UNIT_TAIL.match(text, stop):
            continue   # "1인당"·"1가구당"의 1은 기준을 말하는 낱말이지 수량이 아니다
        if number == 1 and text.startswith("당", stop) and _UNIT_SCALE.get(unit, ("",))[0].startswith("count_"):
            continue   # "1곳당"·"1대당"·"1명당"도 같다(세는 말이 단위로 먼저 읽힌다)
        if not unit and _YEAR_RANGE_HEAD.match(text, stop) and re.fullmatch(r"(?:19|20)\d\d", raw):
            unit = "년"   # "2023~2025년"의 앞 연도도 연도다(단위 없는 수량 2023으로 읽으면 원문에 없는 값이 된다)
        dimension, scale = _UNIT_SCALE.get(unit, (unit or "unitless", Decimal("1")))
        item = {"raw": raw, "value": number * scale, "dimension": dimension, "start": match.start(), "end": stop}
        # mW/MW는 대소문자에 따라 배율이 달라 지원하지 않는다.
        # 공백 유무와 관계없이 추출하되 근거 일치에는 사용하지 않는다.
        if unit in {"mw", "mwh"}:
            item["unsupported_unit"] = unit_match.group(0).strip()
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


_MARKS = {"ko": {"judgment": "(판단)", "no_source": "(출처 없음)", "mismatch": "(출처 불일치)", "estimate": "(원문 추정치)",
                 "sources": "## 출처",
                 "claims": ("## 답", "## 근거", "## 반대 근거와 한계", "## 한계")},
          "en": {"judgment": "(judgment)", "no_source": "(no source)", "mismatch": "(source mismatch)",
                 "estimate": "(source estimate)", "sources": "## Sources",
                 "claims": ("## Answer", "## Evidence", "## Counter-evidence and limits", "## Limits")}}
_MARK_SPLIT = re.compile(r"(?<=[.!?。])(?<![Aa]pprox\.)(\s+)(?!\[S\d+\]|\((?:판단|출처 없음|출처 불일치|원문 추정치|judgment|no source|source mismatch|"
                         r"source estimate)\))")
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
# "approx. 3.8"처럼 약어 마침표 뒤에서는 끊지 않는다(추정 낱말이 수치와 한 문장에 남게, PR #16 리뷰 반영).
_SOURCE_SPLIT = re.compile(r"(?<=[.!?。])(?<![Aa]pprox\.)\s+|\n+")
_EN_CONTEXT_STOP = {"that", "with", "from", "this", "were", "have", "been", "than", "which", "about", "over", "after", "into",
                    "their", "percent", "compared", "they", "said", "also", "only", "during", "under", "same", "year",
                    "years", "median", "average", "report", "reports", "notes", "source"}


def _plain_claim(sentence: str) -> str:
    text = _CITE_ID.sub("", sentence)
    text = re.sub(r"\((?:S\d+[:·][^)]*|판단|출처 없음|출처 불일치|원문 추정치|judgment|no source|source mismatch|source estimate)\)",
                  "", text)
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
    - scope: 원문의 시범·표본 범위 수치를 전역·전체 결과로 말한다.
    - year: 원문이 한 해의 값으로 말한 수치를 다른 해의 값으로 말한다(원문 자리마다 연도가 분명할 때만).
    - unit: 원문이 퍼센트포인트로만 말한 수치를 퍼센트로(또는 반대로) 말한다.
    - bound: 원문이 상한(최대·up to)이나 범위 끝값(10~20%)으로만 말한 수치를 상한·범위 표시 없이 말한다.
    - subject: 원문이 한 대상의 값으로 말한 수치를 같은 종류 수치가 나란히 나오는 다른 대상의 값으로 말한다.
    - basis: 원문이 1인당·가구당·곳당·대당·학교당·평균 값으로 말한 수치를 총계로(또는 반대로, 단위당 기준끼리 바꿔) 말한다."""
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
    if _year_conflict(plain, sents):
        found.append("year")
    if _percent_point_conflict(plain, sents):
        found.append("unit")
    if _bound_overclaim(plain, sents):
        found.append("bound")
    if _subject_swap(plain, sents):
        found.append("subject")
    if _basis_conflict(plain, sents):
        found.append("basis")
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


_CLAUSE_BREAK = re.compile(r"[,;:()]|(?<=[.!?。])(?<![Aa]pprox\.)\s")


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


# 값의 기준: 같은 수치를 원문과 다른 기준(1인당·가구당·곳당·대당·학교당·평균·총계)으로 말하는지 본다. 기간 단위와 같은 방식(절 안 가장 가까운 것).
_BASIS_WORDS = {"person": r"1인당|인당|1명당|명당|\bper (?:person|capita|head|resident|participant|student|worker|employee|recipient|user)\b|"
                          r"\beach (?:person|resident|participant|student|recipient)\b",
                "household": r"가구당|세대당|\bper (?:household|home|family|dwelling)\b|\beach household\b",
                "site": r"곳당|개소당|시설당|지점당|\bper (?:site|facility|center|centre|branch|location|store|clinic)\b|"
                        r"\beach (?:site|facility|center|centre|branch|location|store|clinic)\b",
                "vehicle": r"(?<!세)대당|차량당|\bper (?:vehicle|bus|car|truck)\b|\beach (?:vehicle|bus|car|truck)\b",
                "school": r"학교당|개교당|\bper (?:school|campus)\b|\beach (?:school|campus)\b",
                "average": r"평균|\b(?:on )?average\b",
                "total": r"(?:^|(?<=\s))총(?=\s?\d)|총액|총계|합계|누적|통틀어|\bin total\b|\btotal(?:ing|ed|s)?\b|\bcumulative\b|"
                         r"\baltogether\b|\bcombined\b"}


def _bases_agree(a: set[str], b: set[str]) -> bool:
    """평균은 단위당 값과 어긋나지 않지만(가구 평균 = 가구당) 총계와는 다르다."""
    if a & b:
        return True
    return (a == {"average"} and "total" not in b) or (b == {"average"} and "total" not in a)


def _value_basis(text: str, value: dict) -> set[str]:
    start, clause = _clause_around(text, value)
    found = [(min(abs(m.start() + start - value["start"]), abs(m.end() + start - value["end"])), name)
             for name, pattern in _BASIS_WORDS.items() for m in re.finditer(pattern, clause, re.I)]
    return {min(found)[1]} if found else set()


def _basis_conflict(plain: str, sents: list[str]) -> bool:
    """주장 수치의 기준(1인당·가구당·곳당·대당·학교당·평균·총계)이 같은 값이 나오는 원문 자리마다의 기준과 하나도 겹치지 않으면 True.

    원문 자리 중 기준을 말하지 않는 곳이 하나라도 있으면 표시하지 않는다(값의 기준을 단정할 수 없음)."""
    for value in _quantity_values(plain, _date_like_spans(plain)):
        claim_basis = _value_basis(plain, value)
        if value.get("unsupported_unit") or not claim_basis:
            continue
        held = [_value_basis(s, c) for s, c in _same_value_spots(sents, value)]
        if held and all(b and not _bases_agree(b, claim_basis) for b in held):
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


# 한 절 안에서 실적과 계획이 이어질 때("500기를 설치했고 500기를 더 늘릴 계획") 계획 낱말을 제 명제에만 붙이려고
# 접속어에서도 끊는다(PR #15 Codex 리뷰 반영).
_PROPOSITION_BREAK = re.compile(r"\b(?:and|but|while|whereas)\b|그리고|했고|하고|됐고|되었고|였고|이었고|으며|이며|지만", re.I)


def _proposition_around(text: str, value: dict) -> str:
    start, clause = _clause_around(text, value)
    left, right = value["start"] - start, value["end"] - start
    a = max((m.end() for m in _PROPOSITION_BREAK.finditer(clause, 0, left)), default=0)
    b = next((m.start() for m in _PROPOSITION_BREAK.finditer(clause, right)), len(clause))
    return clause[a:b]


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
        if spots and all(_PLAN_WORDS.search(_proposition_around(s, c)) for s, c in spots):
            return True
    return False


# 추정·잠정치의 확정화: 원문이 추정·추산·잠정치로만 말한 수치를 유보 없이 확정 사실처럼 쓰는지 본다.
# 틀린 값은 아니므로 '(출처 불일치)'보다 약한 '(원문 추정치)'를 붙인다(2026-10-06 품질 회차).
_ESTIMATE_WORDS = re.compile(r"\b(?:estimat\w*|preliminary|provisional|unaudited|approximately|approx\.|roughly|nearly|almost|"
                             r"(?:about|around|some) (?=\d))|추정|추산|잠정|어림|대략|가량|안팎|내외|약\s?(?=\d)", re.I)


# 네 자리 수가 연도로 쓰이는 자리: 달 이름이나 연도 전치사 바로 뒤(PR #16 리뷰 반영 — 수량 2000명은 연도가 아님).
_YEAR_LEAD = re.compile(rf"(?:\b(?:{_MONTH_PATTERN}|in|by|since|until|till|from|through|to|during|before|after|of|year|"
                        r"fiscal|FY)|[-–—~])\s*$", re.I)


def _is_date_number(value: dict, text: str) -> bool:
    """연·월·일 수치와, 연도 자리에 쓰인 단위 없는 네 자리 수(1900~2099)는 날짜라 추정치 판정에서 뺀다."""
    if value["dimension"] in ("년", "월", "일"):
        return True
    return (value["dimension"] == "unitless" and "," not in value["raw"] and value["value"] == int(value["value"])
            and 1900 <= value["value"] <= 2099 and bool(_YEAR_LEAD.search(text[:value["start"]])))


def _estimate_overclaim(plain: str, sents: list[str]) -> bool:
    """주장 수치가 원문에서는 매번 추정·잠정치를 말하는 명제에만 나오는데, 주장은 그런 유보 없이 말하면 True.

    유보 낱말은 주장 문장 전체가 아니라 그 수치가 든 명제에서만 본다(PR #16 리뷰 반영)."""
    for value in _quantity_values(plain, _date_like_spans(plain)):
        if value.get("unsupported_unit") or _is_date_number(value, plain):
            continue
        own = _proposition_around(plain, value)
        if _ESTIMATE_WORDS.search(own) or _PLAN_WORDS.search(own):
            continue
        spots = _same_value_spots(sents, value)
        if spots and all(_ESTIMATE_WORDS.search(_proposition_around(s, c)) for s, c in spots):
            return True
    return False


# 기준 연도 옮김: 원문이 한 해의 값으로 말한 수치를 다른 해의 값으로 쓰는지 본다(2026-10-06 2회차 품질 회차).
# 수치의 연도는 그 수치가 든 명제에 연도가 하나뿐이면 그것, 명제에 없으면 문장 전체에 연도가 하나뿐일 때 그것이다.
# 범위("2022~2025년")나 연도가 둘 이상이면 모른다고 보고 표시하지 않는다.
_YEAR_TOKEN = re.compile(r"(?<![\d,.])((?:19|20)\d\d)(?!\d|,\d|\.\d)")


_SENTENCE_HEAD = re.compile(r"(?:^|[.!?]\s+)\s*$")


def _year_spans(text: str) -> list[tuple[int, int, int]]:
    out: list[tuple[int, int, int]] = []
    for m in _YEAR_TOKEN.finditer(text):
        before = text[:m.start()]
        # 'between'은 늘 연도 자리, 'and'는 앞에 연도가 이미 있을 때만("between 2022 and 2025")
        # 문장 첫머리의 네 자리 수("2023 enrollment reached …")도 연도로 본다(PR #17 리뷰 반영).
        if (re.match(r"\s?년", text[m.end():]) or _YEAR_RANGE_HEAD.match(text, m.end()) or _YEAR_LEAD.search(before)
                or re.search(r"\bbetween\s*$", before, re.I) or (_SENTENCE_HEAD.search(before) and re.match(r"\s+[A-Za-z]", text[m.end():]))
                or (out and re.search(r"\band\s*$", before, re.I))):
            out.append((int(m.group(1)), m.start(), m.end()))
    return out


def _value_year(text: str, value: dict, years: list[tuple[int, int, int]]) -> int | None:
    start, clause = _clause_around(text, value)
    own = _proposition_around(text, value)
    lo = start + clause.find(own)
    mine = {y for y, a, _ in years if lo <= a < lo + len(own)} or {y for y, _, _ in years}
    return next(iter(mine)) if len(mine) == 1 else None


def _year_values(text: str) -> list[tuple[dict, int | None]]:
    years = _year_spans(text)
    return [(v, _value_year(text, v, years)) for v in _quantity_values(text, _date_like_spans(text))
            if not v.get("unsupported_unit") and v["dimension"] not in ("년", "월", "일")
            and not any(a <= v["start"] < b for _, a, b in years)]


def _year_conflict(plain: str, sents: list[str]) -> bool:
    """주장 수치의 기준 연도가 같은 값이 나오는 원문 자리마다의 기준 연도(모두 알려짐)와 하나도 같지 않으면 True."""
    held_all = [x for s in sents for x in _year_values(s)]
    for value, year in _year_values(plain):
        if year is None:
            continue
        held = [y for c, y in held_all if c["dimension"] == value["dimension"] and abs(c["value"]) == abs(value["value"])]
        if held and all(y is not None and y != year for y in held):
            return True
    return False


# 퍼센트와 퍼센트포인트: 41%→47%는 6%포인트 오른 것이지 6% 오른 것이 아니다. 원문이 한쪽으로만 말한 수치를
# 다른 쪽으로 쓰면 다른 값이다. "6%포인트"는 수치 추출에서 6%와 같은 값으로 잡혀 위 대조를 통과하므로 따로 본다.
_PERCENT_POINT = re.compile(r"\s*(?:%\s?p\b|%\s?포인트|퍼센트\s?포인트|%\s?points?\b|percentage[- ]points?\b|pp\b)", re.I)
_PERCENT = re.compile(r"\s*(?:%|퍼센트|percent\b|per cent\b)", re.I)
_PLAIN_NUMBER = re.compile(r"(?<![A-Za-z0-9.,])\d+(?:,\d{3})*(?:\.\d+)?")


def _percent_kinds(text: str) -> list[tuple[Decimal, str]]:
    out = []
    for m in _PLAIN_NUMBER.finditer(text):
        rest = text[m.end():]
        kind = "pp" if _PERCENT_POINT.match(rest) else "pct" if _PERCENT.match(rest) else ""
        out.append((Decimal(m.group(0).replace(",", "")), kind))
    return out


def _percent_point_conflict(plain: str, sents: list[str]) -> bool:
    """주장이 퍼센트로 말한 수치를 원문은 매번 퍼센트포인트로만 말하거나, 그 반대면 True."""
    held_all = [x for s in sents for x in _percent_kinds(s)]
    for number, kind in _percent_kinds(plain):
        if not kind:
            continue
        held = [k for n, k in held_all if n == number]
        if held and all(k and k != kind for k in held):
            return True
    return False


# 상한·범위 끝값의 대표값화: 원문이 "최대 30%"·"up to 25 percent"처럼 상한으로만, "10~20%"·"between 8 and 12 percent"처럼
# 범위의 끝값으로만 말한 수치를 주장이 상한·범위 표시 없이 쓰는지 본다(2026-10-08 품질 회차). "from 9,000 to 14,000"·
# "10%에서 18%로"는 변화 전후 값이라 범위로 보지 않는다.
_BOUND_LEAD = re.compile(r"\b(?:up to|as (?:much|many|high|low|few|little) as|at (?:most|least)|a (?:maximum|minimum) of|"
                         r"no (?:more|less|fewer) than|more than|less than|fewer than|over|under|peak(?:ed|ing)? (?:at|of)|"
                         r"between|range[sd]? from|ranging from)\s*$|(?:최대|최고|최소|많게는|적게는|최저)\s*$", re.I)
# 단위로 읽지 않는 세는 말("300가구 이상")을 건너 하한·상한 낱말을 본다(2026-10-08 2회차 — 점수기는 이미 보던 자리).
_BOUND_TAIL = re.compile(r"\s*(?:가구|곳|명|원|개|건|대|회)?\s*(?:이상|이하|미만|초과|까지|이내|안쪽)")
_RANGE_BEFORE = re.compile(r"\d[\d,.]*\s*(?:%|percent|퍼센트|명|원|가구|곳)?\s*(?:~|–|—|-|\bto\b|\band\b)\s*$", re.I)
_RANGE_AFTER = re.compile(r"\s*(?:~|–|—|-|\bto\b)\s*\d", re.I)
_CHANGE_FROM = re.compile(r"\bfrom\s*$", re.I)


def _bounded_value(text: str, value: dict) -> bool:
    """수치가 상한·하한 낱말 뒤에 있거나 범위의 끝값이면 True("from X to Y"의 변화 전후 값은 뺀다)."""
    before = text[max(0, value["start"] - 40):value["start"]]
    if _BOUND_LEAD.search(before) or _BOUND_TAIL.match(text, value["end"]):
        return True
    prev = _RANGE_BEFORE.search(before)
    if prev and not _CHANGE_FROM.search(before[:prev.start()]):
        return True
    return bool(_RANGE_AFTER.match(text, value["end"])) and not _CHANGE_FROM.search(before)


def _bound_overclaim(plain: str, sents: list[str]) -> bool:
    """주장 수치가 원문에서는 매번 상한·범위 끝값으로만 나오는데, 주장은 상한·범위 표시 없이 말하면 True."""
    for value in _quantity_values(plain, _date_like_spans(plain)):
        if value.get("unsupported_unit") or _is_date_number(value, plain) or _bounded_value(plain, value):
            continue
        spots = _same_value_spots(sents, value)
        if spots and all(_bounded_value(s, c) for s, c in spots):
            return True
    return False


# 대상 바꿈: 원문이 "심야버스 이용객 18%, 지하철 막차 이용객 4%"처럼 같은 종류 수치를 여러 대상에 나란히 말할 때, 주장이 한
# 대상의 수치를 다른 대상의 값으로 옮겨 쓰는지 본다(2026-10-08 2회차 품질 회차). 값은 원문에 있으므로 수치 대조를 통과하고, 문맥 낱말도
# 같은 문장 안에서 겹쳐 지금까지는 표시되지 않았다. 수치의 대상 낱말은 그 수치가 든 명제에서 앞 수치 뒤부터 그 수치까지로 근사한다
# (한국어·영어 모두 대상이 수치 앞에 온다). 앞 수치와 변화·범위로 이어진 수치("10%에서 18%로", "지난해 18분에서 올해 11분으로")는
# 그 앞까지 거슬러 올라간다.
_LABEL_STOP = {"the", "and", "for", "was", "are", "its", "has", "had", "not", "but", "all", "per", "new", "one", "two", "who",
               "percent", "에서", "에는", "에도", "으로", "부터", "까지", "에게"}
_LINKED_VALUE = re.compile(r"^\s*(?:%|퍼센트|percent|[가-힣]{1,2})?(?:\s*[가-힣A-Za-z]{1,4}){0,2}\s*(?:에서|부터|~|–|-|\bto\b|\band\b)"
                           r"(?:\s+[가-힣A-Za-z]{1,4}){0,2}\s*$", re.I)


def _subject_terms(text: str, value: dict, values: list[dict]) -> set[str]:
    """수치 앞, 같은 명제 안에서 앞 수치(와 거기 붙은 단위·조사) 뒤부터 수치까지의 낱말."""
    start, clause = _clause_around(text, value)
    left = value["start"] - start
    a = max((m.end() for m in _PROPOSITION_BREAK.finditer(clause, 0, left)), default=0) + start
    cut = value["start"]
    for prev in sorted((v for v in values if a <= v["start"] and v["end"] <= cut), key=lambda v: v["start"], reverse=True):
        if prev["end"] > cut:
            continue
        if not _LINKED_VALUE.match(text[prev["end"]:cut]):
            a = prev["end"] + len(re.match(r"\S*", text[prev["end"]:cut]).group(0))
            break
        cut = prev["start"]
    head = _UP_MARK.sub(" ", _DOWN_MARK.sub(" ", text[a:cut]))
    english = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", head)} - _EN_CONTEXT_STOP - _CONTEXT_STOP - _LABEL_STOP
    return english | ({w[:2] for w in re.findall(r"[가-힣]{2,}", head)} - _LABEL_STOP)


def _value_kind(value: dict, text: str) -> tuple[str, bool]:
    """같은 종류 수치: 차원이 같고 퍼센트포인트 여부도 같다."""
    return value["dimension"], bool(_PERCENT_POINT.search(value["raw"]) or _PERCENT_POINT.match(text, value["end"]))


def _subject_swap(plain: str, sents: list[str]) -> bool:
    """주장 수치가 원문에서 나오는 자리마다, 그 자리의 대상 낱말은 주장에 없고 같은 종류 다른 수치 자리의 대상 낱말이 주장에 더
    많이 있으면 True(주장이 수치를 원문의 다른 대상으로 옮겨 붙임)."""
    claim_values = [v for v in _quantity_values(plain, _date_like_spans(plain)) if not v.get("unsupported_unit")]
    spots = [(s, v, vals) for s in sents
             for vals in [[v for v in _quantity_values(s, _date_like_spans(s)) if not v.get("unsupported_unit")]] for v in vals]
    for value in claim_values:
        if _is_date_number(value, plain):
            continue
        mine = _subject_terms(plain, value, claim_values)
        kind = _value_kind(value, plain)
        held = [(s, v, vals) for s, v, vals in spots if v["dimension"] == value["dimension"] and abs(v["value"]) == abs(value["value"])]
        if not mine or not held or any(_scripts(s) != _scripts(plain) for s, _, _ in held):
            continue

        def moved(s: str, v: dict, vals: list[dict]) -> bool:
            own = _subject_terms(s, v, vals)
            for s2, w, vals2 in spots:
                if abs(w["value"]) == abs(value["value"]) or _value_kind(w, s2) != kind or _is_date_number(w, s2):
                    continue
                other = _subject_terms(s2, w, vals2)
                toward, away = mine & (other - own), mine & (own - other)
                # 주장이 원래 자리의 고유 대상 낱말을 모두 담으면 옮긴 것이 아니다. "에너지 바우처는 가구당 15만 원이었고, 사업비는
                # 총 36억 원"처럼 앞 절의 주제어가 뒤 절에서 생략되면 주제어가 앞 수치의 대상으로만 잡히기 때문이다(2026-10-09).
                if own - other and toward and len(toward) > len(away) and not (own - other) <= mine:
                    return True
            return False
        if all(moved(s, v, vals) for s, v, vals in held):
            return True
    return False


def _scope_overclaim(plain: str, sents: list[str]) -> bool:
    """주장이 전역·전체 범위를 말하는데, 주장 수치가 든 원문 문장이 모두 시범·표본 범위만 말하고 전역 낱말은 없으면 True.

    수치 없는 주장은 같은 대상(문맥 낱말 2개 이상 공유)을 말하는 원문 문장으로 본다(PR #15 Codex 리뷰 반영)."""
    if not _WIDE_SCOPE.search(plain):
        return False
    values = [v for v in _quantity_values(plain, _date_like_spans(plain)) if not v.get("unsupported_unit")]
    if values:
        held = list(dict.fromkeys(s for value in values for s, _ in _same_value_spots(sents, value)))
    else:
        stems = _scope_stems(plain)
        held = [s for s in sents if len(stems & _scope_stems(s)) >= 2]
    return bool(held) and all(_NARROW_SCOPE.search(s) and not _WIDE_SCOPE.search(s) for s in held)


def _scope_stems(text: str) -> set[str]:
    return _content_stems(_NARROW_SCOPE.sub(" ", _WIDE_SCOPE.sub(" ", text)))


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
    return [(direction, stems) for direction, stems, _, _ in _trusted_cited_rows(report, source_texts, M)]


def _trusted_cited_rows(report: str, source_texts: dict[str, str], M: dict) -> list[tuple[str, set[str], tuple[str, ...], str]]:
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
                out.append((direction, _content_stems(plain), tuple(cites), plain))
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
    - 인용 문장이 원문 수치를 다른 기준 연도의 값으로 옮기거나 퍼센트포인트를 퍼센트로(또는 반대로) 말하면 '(출처 불일치)'
    - 인용 문장이 원문의 상한(최대·up to)·범위 끝값을 대표값처럼 말하면 '(출처 불일치)'
    - 인용 문장이 원문의 한 대상 수치를 나란히 나오는 다른 대상의 값으로 옮겨 말하면 '(출처 불일치)'
    - 인용 문장이 원문의 1인당·가구당·곳당·대당·학교당·평균 값을 총계로(또는 반대로, 단위당 기준끼리 바꿔) 말하면 '(출처 불일치)'
    표, 코드, 출처 절은 건드리지 않는다. 다시 돌려도 결과가 같다.
    반환: (표시한 본문, {"mismatch", "no_source", "direction_conflict", "context_conflict", "independence_conflict",
    "causal_conflict", "period_conflict", "internal_conflict", "plan_conflict", "scope_conflict", "year_conflict", "unit_conflict", "bound_conflict", "subject_conflict", "basis_conflict", "estimate_dropped": 문장 목록})."""
    M = _MARKS.get(lang, _MARKS["ko"])
    marks = (M["judgment"], M["no_source"], M["mismatch"])
    estimate_mark = M["estimate"]
    changes: dict[str, list[str]] = {"mismatch": [], "no_source": [], "direction_conflict": [], "context_conflict": [],
                                     "independence_conflict": [], "causal_conflict": [], "period_conflict": [],
                                     "internal_conflict": [], "plan_conflict": [], "scope_conflict": [], "year_conflict": [],
                                     "unit_conflict": [], "bound_conflict": [], "subject_conflict": [], "basis_conflict": [],
                                     "estimate_dropped": []}
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
            if index % 2 or not piece.strip() or any(m in piece for m in marks + (estimate_mark,)):
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
                elif cited_text.strip() and _estimate_overclaim(
                        _plain_claim(piece), [x.strip() for x in _SOURCE_SPLIT.split(cited_text) if x.strip()]):
                    changes["estimate_dropped"].append(piece.strip())
                    piece = _with_mismatch(piece, estimate_mark)
            elif (claim_section and not piece.rstrip().endswith(":")
                  and len(re.sub(r"\W", "", piece)) >= 8):
                changes["no_source"].append(piece.strip())
                piece = _with_mark(piece, M["no_source"])
            fixed.append(piece)
        out.append(lead + "".join(fixed))
    return "\n".join(out), changes


_CONFLICT_ROW = {"ko": "- 출처끼리 상충: {a}·{b}를 인용한 문장이 같은 대상의 증감을 서로 반대로 말하므로 두 원문의 범위·기간·측정 방식을 확인해야 한다 {j}.",
                 "en": "- Sources disagree: sentences citing {a} and {b} give opposite directions for the same subject, so check each source's scope, period and method {j}."}
_MAGNITUDE_ROW = {"ko": "- 출처끼리 증감 폭이 크게 다름: {a}·{b}를 인용한 문장이 같은 대상의 증감 폭을 {x}·{y}로 말하므로 두 원문의 범위·기간·측정 방식을 확인해야 한다 {j}.",
                  "en": "- Sources differ in size: sentences citing {a} and {b} give {x} and {y} for the same subject's change, so check each source's scope, period and method {j}."}


def _magnitude_gap(a: str, b: str) -> tuple[str, str] | None:
    """같은 방향 두 문장이 퍼센트(또는 퍼센트포인트) 수치를 하나씩만 말하고, 같은 종류인데 큰 값이 작은 값의 2배 이상이면
    두 수치 표기를 돌려준다. 2배는 집계 범위·방법이 다를 때 생기는 차이로 보고 반올림 정도의 차이는 세지 않으려는 문턱이다."""
    pa = [(n, k) for n, k in _percent_kinds(a) if k]
    pb = [(n, k) for n, k in _percent_kinds(b) if k]
    if len(pa) != 1 or len(pb) != 1 or pa[0][1] != pb[0][1]:
        return None
    lo, hi = sorted((pa[0][0], pb[0][0]))
    if lo <= 0 or hi < 2 * lo:
        return None
    unit = "%p" if pa[0][1] == "pp" else "%"
    return f"{pa[0][0].normalize():f}{unit}", f"{pb[0][0].normalize():f}{unit}"


def note_source_conflicts(report: str, source_texts: dict[str, str], lang: str = "ko", limit: int = 3) -> tuple[str, list[list[str]]]:
    """서로 다른 출처를 인용한 두 문장이 같은 대상(문맥 낱말 2개 이상 공유)을 반대 증감 방향으로 말하거나, 같은 방향이라도
    증감 폭(퍼센트 하나씩)을 2배 이상 다르게 말하는데 한계 절이 두 출처를 함께 언급하지 않으면, 한계 절 끝에 안내 한 줄을
    '(판단)'으로 덧붙인다.

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
    rows_by_pair: dict[tuple[str, ...], str] = {}
    for i, (d1, stems1, cites1, plain1) in enumerate(rows):
        for d2, stems2, cites2, plain2 in rows[i + 1:]:
            gap = _magnitude_gap(plain1, plain2) if d1 == d2 else None
            years1, years2 = {y for y, _, _ in _year_spans(plain1)}, {y for y, _, _ in _year_spans(plain2)}
            if gap and years1 and years2 and not years1 & years2:
                gap = None   # 서로 다른 해의 증감 폭은 상충이 아니다(PR #17 리뷰 반영)
            if (d1 == d2 and not gap) or set(cites1) & set(cites2) or len(stems1 & stems2) < 2:
                continue
            pair = sorted({cites1[0], cites2[0]}, key=lambda c: int(c[1:]))
            # 두 출처를 한 줄에서 함께 다뤄야 상충을 다룬 것으로 본다(따로 떨어진 언급은 치지 않음, PR #15 Codex 리뷰 반영).
            mentioned = any(all(re.search(rf"(?<![A-Za-z0-9]){c}(?!\d)", row) for c in pair) for row in section.split("\n"))
            if pair not in pairs and not mentioned:
                pairs.append(pair)
                if gap:
                    x, y = gap if int(cites1[0][1:]) <= int(cites2[0][1:]) else gap[::-1]
                    rows_by_pair[tuple(pair)] = _MAGNITUDE_ROW.get(lang, _MAGNITUDE_ROW["ko"]).format(
                        a=pair[0], b=pair[1], x=x, y=y, j=M["judgment"])
    pairs = pairs[:limit]
    if not pairs:
        return report, []
    added = [rows_by_pair.get(tuple(p)) or _CONFLICT_ROW.get(lang, _CONFLICT_ROW["ko"]).format(a=p[0], b=p[1], j=M["judgment"])
             for p in pairs]
    last = end
    while last > index + 1 and not lines[last - 1].strip():
        last -= 1
    lines[last:last] = added
    return "\n".join(lines), pairs
