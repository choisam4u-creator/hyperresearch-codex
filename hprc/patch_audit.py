"""실제 적용한 수정에서 사라진 수치·한정어를 무호출 검토 신호로 남긴다."""
from collections import Counter
import re

from .gates import CITE

_NUMBER = re.compile(r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:%|‰)?")

# 의미 판정기가 아니다. 경계가 비교적 분명한 표지만 좁게 세어 검토 후보를 만든다.
_QUALIFIERS = {
    "ko": {
        "exclusion": re.compile(r"(?<![가-힣])(제외(?:하\w*|되\w*)?|예외|외에는)(?![가-힣])"),
        "condition": re.compile(r"(?<![가-힣])(단|다만|경우|한정(?:하\w*|되\w*)?|조건(?:부)?)(?![가-힣])"),
        "negation": re.compile(r"(?<![가-힣])(아니\w*|않\w*|없\w*|못\w*)(?![가-힣])"),
    },
    "en": {
        "exclusion": re.compile(r"\b(?:except(?:ing)?|exclud(?:e[ds]?|ing)|exception)\b", re.I),
        "condition": re.compile(r"\b(?:if|unless|when|only|provided|subject\s+to|limited\s+to)\b", re.I),
        "negation": re.compile(r"\b(?:not|no|never|without|cannot|can't|neither|nor)\b", re.I),
    },
}


def _numbers(text: str) -> Counter:
    result = Counter()
    for match in _NUMBER.finditer(CITE.sub("", text).replace("−", "-")):
        token = match.group()
        suffix = token[-1] if token[-1] in "%‰" else ""
        number = token[:-1] if suffix else token
        # Decimal.normalize의 기본 정밀도 반올림으로 서로 다른 큰 수가 합쳐지지 않게 한다.
        number = number.replace(",", "")
        negative = number.startswith("-")
        integer, _, fraction = number.lstrip("+-").partition(".")
        integer, fraction = integer.lstrip("0") or "0", fraction.rstrip("0")
        normalized = integer + ("." + fraction if fraction else "")
        result[("-" if negative and normalized != "0" else "") + normalized + suffix] += 1
    return result


def numeric_removals(applied_hunks: list[dict]) -> list[dict]:
    """정정도 신호에 포함한다. 사실 오류 판정이나 수정 거부 근거는 아니다."""
    changes = []
    for index, hunk in enumerate(applied_hunks):
        before, after = _numbers(hunk["find"]), _numbers(hunk["replace"])
        removed = before - after
        if removed:
            changes.append({"applied_hunk_index": index,
                            "finding_ids": hunk.get("finding_ids", []),
                            "removed_numbers": sorted(removed.elements()),
                            "added_numbers": sorted((after - before).elements())})
    return changes


def qualifier_removals(applied_hunks: list[dict], lang: str) -> list[dict]:
    """명시적 제외·조건·부정 표지의 감소를 경고한다. 올바른 정정도 포함될 수 있다."""
    patterns = _QUALIFIERS.get(lang, _QUALIFIERS["en"])
    changes = []
    for index, hunk in enumerate(applied_hunks):
        before_text, after_text = CITE.sub("", hunk["find"]), CITE.sub("", hunk["replace"])
        removed = {}
        for category, pattern in patterns.items():
            before = Counter(match.group(0).casefold() for match in pattern.finditer(before_text))
            after = Counter(match.group(0).casefold() for match in pattern.finditer(after_text))
            missing = sorted((before - after).elements())
            if missing:
                removed[category] = missing
        if removed:
            changes.append({
                "applied_hunk_index": index,
                "finding_ids": hunk.get("finding_ids", []),
                "removed_qualifiers": removed,
                "before": hunk["find"],
                "after": hunk["replace"],
            })
    return changes
