"""보고서 인용 표본을 고정 규칙으로 고른다. 표본은 사실성 전체를 보장하지 않는다."""
import re


_CITE = re.compile(r"\[S(\d+)\]")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+")
_SENTENCE_SPACE = re.compile(r"(?<=[.!?。\]])\s+")


def _is_source_heading(line: str) -> bool:
    heading = re.sub(r"^\s{0,3}#{1,6}\s+", "", line).strip().lower()
    return heading in {"출처", "출처 목록", "출처 상세(자동 생성)", "sources", "source details (auto-generated)"}


def _has_content(sentence: str) -> bool:
    """인용 표식만 있는 표·목록 항목은 검사할 주장으로 세지 않는다."""
    remainder = _CITE.sub("", sentence)
    return bool(re.sub(r"[\s|*`_~>\-–—]", "", remainder))


def _sentences(raw: str, judgment_marker: str) -> list[str]:
    # 먼저 공백 전체를 소비한 뒤 표식을 판정해 정규식 역추적으로 분리되지 않게 한다.
    spaces = {(m.start(), m.end()) for m in _SENTENCE_SPACE.finditer(raw)}
    if judgment_marker:
        spaces.update((m.start() + len(judgment_marker), m.end())
                      for m in re.finditer(re.escape(judgment_marker) + r"\s+", raw))
    parts, start = [], 0
    for left, right in sorted(spaces):
        if _CITE.match(raw, right) or (judgment_marker and raw.startswith(judgment_marker, right)):
            continue
        if left < start:
            continue
        parts.append(raw[start:left])
        start = right
    parts.append(raw[start:])
    return parts


def _candidates(report: str, judgment_marker: str) -> tuple[list[dict], int]:
    """코드·헤더·출처 목록 밖의 인용 문장을 원문 문자열 그대로 찾는다."""
    found, excluded = [], 0
    fenced = False
    in_sources = False
    for line_no, raw in enumerate(report.splitlines(), 1):
        stripped = raw.strip()
        if stripped.startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced:
            continue
        if _HEADING.match(raw):
            in_sources = _is_source_heading(raw)
            continue
        if in_sources:
            continue
        pieces = [raw] if stripped.startswith("|") else _sentences(raw, judgment_marker)
        for sentence in pieces:
            cites = _CITE.findall(sentence)
            if not cites:
                continue
            if not _has_content(sentence):
                continue
            if judgment_marker and judgment_marker in sentence:
                excluded += 1
                continue
            found.append({"sentence": sentence, "cites": [f"S{cite}" for cite in dict.fromkeys(cites)], "line": line_no})
    return found, excluded


def select_samples(report: str, limit: int, judgment_marker: str) -> dict:
    """앞·중간·끝과 출처 다양성을 우선한 결정적 표본을 반환한다.

    eligible_count는 인용 문장 수이고, 이 표본 비율은 문장 기준 범위일 뿐
    보고서 전체의 사실성이나 인용 정확성을 보장하지 않는다.
    """
    candidates, excluded = _candidates(report, judgment_marker)
    if limit <= 0 or not candidates:
        return {"samples": [], "eligible_count": len(candidates), "excluded_judgment_count": excluded,
                "selected_count": 0, "scope": "sample_only"}
    # 같은 원문·인용 조합은 한 번만 검사한다. 그렇지 않으면 모델의 동일 결과를
    # 어느 행에 붙일지 알 수 없어 실제 판정 수가 인위적으로 줄어든다.
    unique, seen = [], set()
    for candidate in candidates:
        key = (candidate["sentence"], tuple(candidate["cites"]))
        if key not in seen:
            unique.append(candidate)
            seen.add(key)
    count = min(limit, len(unique))
    chosen: list[int] = []
    # 최소 세 표본이면 앞·중간·끝을 먼저 놓는다. 가까운 문장을 고르되 같은
    # 출처 반복은 다음 후보로 밀어 출처 다양성을 잃지 않는다.
    if count == 1:
        targets = [(len(unique) - 1) // 2]
    elif count == 2:
        targets = [0, len(unique) - 1]
    else:
        targets = [0, (len(unique) - 1) // 2, len(unique) - 1]
    for target in targets:
        used = {cite for index in chosen for cite in unique[index]["cites"]}
        available = [index for index in range(len(unique)) if index not in chosen]
        if not available:
            break
        chosen.append(min(available, key=lambda index: (abs(index - target), bool(set(unique[index]["cites"]) & used), index)))
    while len(chosen) < count:
        used = {cite for index in chosen for cite in unique[index]["cites"]}
        target = round((len(chosen) + 1) * (len(unique) - 1) / (count + 1))
        available = [index for index in range(len(unique)) if index not in chosen]
        chosen.append(min(available, key=lambda index: (bool(set(unique[index]["cites"]) & used), abs(index - target), index)))
    samples = [{key: unique[index][key] for key in ("sentence", "cites", "line")} for index in sorted(chosen)]
    return {"samples": samples, "eligible_count": len(candidates), "excluded_judgment_count": excluded,
            "selected_count": len(samples), "scope": "sample_only"}


def enrich_checks(checks: list[dict], metadata: dict) -> list[dict]:
    """표본과 정확히 한 번 일치한 CITECHECK 결과만 반환하고 행 번호를 붙인다.

    문장 원문과 인용 ID 집합이 모두 같은 결과만 채택한다. 표본 밖 결과나
    같은 표본의 중복 결과는 반환하지 않고 metadata의 unmatched_count에 남긴다.
    """
    by_key = {(sample["sentence"], frozenset(sample["cites"])): sample for sample in metadata.get("samples", [])}
    enriched = []
    used = set()
    unmatched = 0
    for check in checks:
        cites = check.get("cites", [])
        key = (check.get("sentence", ""), frozenset(cites))
        sample = by_key.get(key)
        if not sample or key in used:
            unmatched += 1
            continue
        used.add(key)
        item = dict(check)
        item["line"] = sample["line"]
        enriched.append(item)
    metadata["checked_count"] = len(enriched)
    metadata["unmatched_count"] = unmatched
    return enriched


def render_summary(checks: list[dict], metadata: dict | None, lang: str) -> str:
    """표본 검사 결과를 표시한다. 표본 밖 문장은 검사하지 않았음을 항상 밝힌다."""
    ko = lang == "ko"
    legacy = metadata is None
    metadata = metadata or {"checked_count": len(checks), "scope": "legacy_metadata_missing", "line_reference": "report.md"}
    heading = "## 인용 표본 검사" if ko else "## Citation sample check"
    scope = "표본 밖 문장은 검증하지 않았습니다." if ko else "Sentences outside this sample were not checked."
    sampled = metadata.get("selected_count", len(checks))
    eligible = metadata.get("eligible_count", 0)
    checked = metadata.get("checked_count", len(checks))
    missing = max(sampled - checked, 0)
    reference = metadata.get("line_reference", "report.md")
    if legacy:
        lines = [heading, "", f"- {'반환된 판정' if ko else 'Returned judgments'}: {checked}.",
                 f"- {'이전 실행이라 전체 인용 문장 수와 표본 범위가 기록되지 않았습니다.' if ko else 'This legacy run did not record the total cited-sentence count or sampling scope.'}",
                 f"- {scope}"]
    else:
        lines = [heading, "", f"- {'표본' if ko else 'Sample'}: {sampled}/{eligible} {'인용 문장' if ko else 'cited sentences'} ({metadata.get('scope', 'sample_only')}).",
                 f"- {'실제 판정 결과' if ko else 'Returned judgments'}: {checked}/{sampled}.",
                 f"- {scope}", f"- {'행 번호는 ' + reference + ' 기준입니다.' if ko else 'Line numbers refer to ' + reference + '.'}"]
    if missing:
        lines.append(f"- {'미반환 표본' if ko else 'Unreturned samples'} {missing}{'개는 미검증입니다.' if ko else ' were not checked.'}")
    unmatched = metadata.get("unmatched_count", 0)
    if unmatched:
        lines.append(f"- {'표본과 일치하지 않거나 중복된 반환 결과' if ko else 'Unmatched or duplicate returned results'} {unmatched}{'개는 판정 수에서 제외했습니다.' if ko else ' were excluded from the judgment count.'}")
    if legacy:
        lines.append(f"- {'이전 실행이라 표본 메타데이터가 없어 반환된 판정만 표시합니다.' if ko else 'This legacy run has no sampling metadata; only returned judgments are shown.'}")
    elif reference != "report.md":
        lines.append(f"- {'검사 표본은 ' + reference + ' 기준이며, 현재 report.md는 이후 다듬기 결과일 수 있습니다.' if ko else 'Samples use ' + reference + '; current report.md may include later polishing.'}")
    unsupported = [check for check in checks if check.get("supported") is False or check.get("verdict") == "unsupported"]
    if not checks:
        lines.append(f"- {'반환된 판정 결과가 없습니다.' if ko else 'No judgment result was returned.'}")
        return "\n".join(lines) + "\n"
    if not unsupported:
        lines.append(f"- {'반환된 판정에서 미지지 표본 없음' if ko else 'No unsupported sentence among returned judgments'}.")
        return "\n".join(lines) + "\n"
    lines += ["", f"### {'미지지 표본' if ko else 'Unsupported samples'}"]
    for check in unsupported:
        cites = " ".join(f"[{cite}]" for cite in check.get("cites", []))
        position = f"L{check.get('line', '?')}"
        reason = check.get("reason", "")
        lines.append(f"- {position} {cites} — {check.get('sentence', '')}" + (f" ({reason})" if reason else ""))
    return "\n".join(lines) + "\n"
