"""실제 적용한 수정에서 사라진 숫자를 무호출 검토 신호로 남긴다."""
from collections import Counter
import re

from .gates import CITE

_NUMBER = re.compile(r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:%|‰)?")


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
