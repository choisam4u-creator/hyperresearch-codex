"""모델 없이 긴 노트의 근거 후보를 제한된 문자 수 안에서 고른다.

단어 겹침은 위치 후보를 고르는 보조값일 뿐 의미적 지지 판정이 아니다. 긴
마크다운 표는 관련 행을 나눌 때 머리글/단위를 보존하고, 조건·예외 문단은
가능하면 인접 근거와 함께 넣는다.
"""
import re


_WORD = re.compile(r"[A-Za-z0-9]{2,}|[가-힣]{2,}")
_STOP = {"그리고", "그러나", "하지만", "있다", "없다", "한다", "된다", "이다",
         "the", "and", "for", "with", "that", "this", "from", "are", "is", "to", "of", "in", "on"}
_TABLE_SEPARATOR = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*$")
_CONTEXT_CUE = re.compile(
    r"(?:예외|제외|조건|단위|한정|경우에만|일\s*때만|않(?:는|다)|없(?:는|다)|"
    r"exception|except|unless|only\s+(?:when|if|for)|condition|unit|not\s+applicable)", re.IGNORECASE)
_SEPARATOR = "\n\n[…]\n\n"
_SUPPLEMENT_CONTEXT = re.compile(
    _CONTEXT_CUE.pattern + r"|\b(?:not|only|cannot|without|limited|unaudited)\b|미검증|검증되지|한계",
    re.IGNORECASE)


def terms(text: str) -> set[str]:
    return {word.lower() for word in _WORD.findall(text) if word.lower() not in _STOP}


def _split_prose(text: str, limit: int) -> list[str]:
    out = []
    remaining = text.strip()
    while len(remaining) > limit:
        cut = max(remaining.rfind(mark, 0, limit) for mark in (". ", "。", "\n"))
        cut = cut + 1 if cut >= max(80, limit // 4) else limit
        out.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        out.append(remaining)
    return out


def _table_chunks(part: str, limit: int) -> list[str] | None:
    lines = part.splitlines()
    table_indices = [index for index, line in enumerate(lines) if line.strip().startswith("|")]
    if not table_indices:
        return None
    first, last = min(table_indices), max(table_indices)
    if table_indices != list(range(first, last + 1)):
        return None
    table = lines[first:last + 1]
    if len(table) < 2 or not _TABLE_SEPARATOR.match(table[1]):
        return None
    before = [line for line in lines[:first] if line.strip()]
    after = [line for line in lines[last + 1:] if line.strip()]
    context = [line for line in before + after if _CONTEXT_CUE.search(line)]
    header = table[:2]
    rows = table[2:]
    prefix = before[-1:] + header if before else header
    suffix = context[-1:] if context and context[-1] not in prefix else []
    base = "\n".join(prefix + suffix)
    if not rows:
        header_only = "\n".join(header)
        return [base] if len(base) <= limit else [header_only] if len(header_only) <= limit else []
    chunks, current = [], list(prefix)
    for row in rows:
        candidate = "\n".join(current + [row] + suffix)
        if len(candidate) > limit and len(current) > len(prefix):
            chunks.append("\n".join(current + suffix))
            current = list(prefix)
            candidate = "\n".join(current + [row] + suffix)
        if len(candidate) > limit:
            # 일반 문단 분할은 표 머리글 없는 조각을 만들므로, 긴 행 조각마다
            # 머리글/조건을 다시 붙인다. 고정 문맥 자체가 상한을 채우면 행은 뺀다.
            fixed = "\n".join(prefix + suffix)
            room = limit - len(fixed) - 12
            if room >= 16:
                row_text = row.strip().strip("|").strip()
                for start in range(0, len(row_text), room):
                    fragment = row_text[start:start + room]
                    wrapped = f"| … {fragment} … |"
                    value = "\n".join(prefix + [wrapped] + suffix)
                    if len(value) <= limit:
                        chunks.append(value)
            current = list(prefix)
            continue
        current.append(row)
    if len(current) > len(prefix):
        chunks.append("\n".join(current + suffix))
    header_only = "\n".join(header)
    return chunks or ([header_only] if len(header_only) <= limit else [])


def paragraphs(body: str, chunk_limit: int = 1200) -> list[str]:
    """선택 가능한 구조 단위. 긴 표 조각에는 머리글을 반복해 문맥을 보존한다."""
    limit = max(80, chunk_limit)
    parts = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
    out = []
    for part in parts:
        if len(part) <= limit:
            out.append(part)
            continue
        table = _table_chunks(part, limit)
        out.extend(table if table is not None else _split_prose(part, limit))
    return out


def _score(paragraph: str, query_terms: set[str]) -> float:
    paragraph_terms = terms(paragraph)
    return len(paragraph_terms & query_terms) / (len(paragraph_terms) ** 0.5 + 1) if paragraph_terms else 0.0


def _render(chosen: list[tuple[tuple[int, int], str]], body_length: int, cap: int) -> str:
    content = _SEPARATOR.join(text for _, text in sorted(chosen))
    omitted = max(0, body_length - sum(len(text) for _, text in chosen))
    marker = f"\n\n[… 관련도 낮은 {omitted:,}자 생략: 이 노트는 잘렸다 …]\n"
    if cap <= len(marker):
        return marker[:cap]
    return content[:cap - len(marker)].rstrip() + marker


def select(body: str, query: str, cap: int, intro_chars: int = 800, evidence_queries: tuple[str, ...] = (),
           supplemental_cap: int | None = None) -> tuple[str, bool]:
    """(선택 본문, 잘림 여부). 기본 상한은 cap; 공유 예산은 기존 선택을 유지하며 보충에만 쓴다."""
    if cap <= 0:
        return "", bool(body)
    if len(body) <= cap:
        return body, False

    chunk_limit = max(120, min(1200, cap // 2))
    paras = paragraphs(body, chunk_limit)
    query_terms = terms(query)
    scores = [_score(paragraph, query_terms) for paragraph in paras]
    chosen: dict[int, str] = {}
    if paras:
        intro_limit = min(intro_chars, max(40, cap // 3))
        chosen[0] = paras[0][:intro_limit]

    def projected(extra: str) -> int:
        values = list(chosen.values()) + [extra]
        return sum(map(len, values)) + max(0, len(values) - 1) * len(_SEPARATOR)

    reserve = min(80, max(24, cap // 8))
    ranked = sorted(range(len(paras)), key=lambda index: (-scores[index], index))
    for index in ranked:
        if index == 0 or scores[index] <= 0:
            continue
        paragraph = paras[index]
        if projected(paragraph) + reserve <= cap:
            chosen[index] = paragraph
        for neighbor in (index - 1, index + 1):
            if neighbor < 0 or neighbor >= len(paras) or neighbor in chosen:
                continue
            if _CONTEXT_CUE.search(paras[neighbor]) and projected(paras[neighbor]) + reserve <= cap:
                chosen[neighbor] = paras[neighbor]

    if len(chosen) <= 1:
        # 언어가 달라 겹침이 없을 때는 의미 검색 성공을 가장하지 않고 본문 순서로 채운다.
        for index, paragraph in enumerate(paras):
            if index in chosen or len(paragraph) < 40:
                continue
            if projected(paragraph) + reserve <= cap:
                chosen[index] = paragraph
            if projected("") >= cap * 0.8:
                break

    # 이미 고른 문맥을 교체하지 않는다. 남은 상한 안에서 분석 주장의 원문
    # 후보 문장만 보충한다. 주장의 진실 여부를 단어 겹침으로 판정하지 않는다.
    pieces = [((index, 0), paragraph) for index, paragraph in chosen.items()]
    limit = max(len(_render(pieces, len(body), cap)), supplemental_cap) if evidence_queries and supplemental_cap is not None else cap
    reserve = max(reserve, len(f"\n\n[… 관련도 낮은 {len(body):,}자 생략: 이 노트는 잘렸다 …]\n"))
    claim_terms = [terms(value) for value in evidence_queries if isinstance(value, str)]
    if not claim_terms:
        return _render(pieces, len(body), cap), True

    # 보충 구간은 인위적인 chunk 경계가 아니라 원문 문단에서 찾는다.
    # 그래야 chunk 다음에 이어지는 조건 문장도 같은 원문 구간에 들어간다.
    offsets, cursor = [], 0
    for paragraph in paras:
        position = body.find(paragraph, cursor)
        offsets.append(position)
        if position >= 0:
            cursor = position + len(paragraph)
    occupied = [(offsets[index], offsets[index] + len(value))
                for index, value in chosen.items() if offsets[index] >= 0]
    candidates, cursor = [], 0
    for paragraph in re.split(r"\n\s*\n", body):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        position = body.find(paragraph, cursor)
        cursor = position + len(paragraph)
        if "|" in paragraph:
            continue
        boundaries = [0] + [match.end() for match in re.finditer(r"(?<=[.!?。])\s+", paragraph)]
        spans = [(start, end) for start, end in zip(boundaries, boundaries[1:] + [len(paragraph)]) if start < end]
        for offset, (start, end) in enumerate(spans):
            sentence = paragraph[start:end].rstrip()
            sentence_terms = terms(sentence)
            matching = [query for query in claim_terms if len(sentence_terms & query) >= 2]
            if not matching:
                continue
            left, right = offset, offset
            while left > 0 and _SUPPLEMENT_CONTEXT.search(paragraph[slice(*spans[left - 1])]):
                left -= 1
            while right + 1 < len(spans) and _SUPPLEMENT_CONTEXT.search(paragraph[slice(*spans[right + 1])]):
                right += 1
            value = paragraph[spans[left][0]:spans[right][1]].rstrip()
            first = position + spans[left][0]
            last = first + len(value)
            if any(first < old_end and last > old_start for old_start, old_end in occupied):
                continue
            score = max(_score(sentence, query) for query in matching)
            candidates.append((-score, first, last, value))
    for _, first, last, sentence in sorted(candidates):
        if any(first < old_end and last > old_start for old_start, old_end in occupied):
            continue
        needed = sum(len(value) for _, value in pieces) + len(pieces) * len(_SEPARATOR) + len(sentence) + reserve
        if needed <= limit:
            index = max((i for i, position in enumerate(offsets) if 0 <= position <= first), default=0)
            pieces.append(((index, first + 1), sentence))
            occupied.append((first, last))
    return _render(pieces, len(body), limit), True
