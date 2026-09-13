"""관련 문단 고르기(모델 없이): 긴 노트를 앞에서 자르는 대신, 질문·초안과 겹치는 단어가 많은 문단을 골라 상한 안에 넣는다.
같은 토큰으로 더 쓸모 있는 근거를 넣기 위한 장치. 첫 문단(도입)은 항상 포함한다."""
import re

_WORD = re.compile(r"[A-Za-z0-9]{2,}|[가-힣]{2,}")  # "Google은" → google (조사가 붙은 영문 낱말도 겹치게)
_STOP = {"그리고", "그러나", "하지만", "있다", "없다", "한다", "된다", "이다", "the", "and", "for", "with", "that", "this", "from", "are", "is", "to", "of", "in", "on"}


def terms(text: str) -> set[str]:
    return {w.lower() for w in _WORD.findall(text) if w.lower() not in _STOP}


def paragraphs(body: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    out = []
    for p in parts:  # 너무 긴 문단은 1,200자 단위로 나눠 고를 수 있게
        while len(p) > 1200:
            cut = p.rfind(". ", 0, 1200)
            cut = cut + 1 if cut > 300 else 1200
            out.append(p[:cut].strip()); p = p[cut:].strip()
        if p:
            out.append(p)
    return out


def select(body: str, query: str, cap: int, intro_chars: int = 800) -> tuple[str, bool]:
    """반환: (선택된 본문, 잘렸는지). cap 이하면 원문 그대로."""
    if len(body) <= cap:
        return body, False
    paras = paragraphs(body)
    q = terms(query)
    scored = []
    for i, p in enumerate(paras):
        t = terms(p)
        score = len(t & q) / (len(t) ** 0.5 + 1) if t else 0
        scored.append((score, i, p))
    chosen, used = [], 0
    intro = paras[0][:intro_chars] if paras else ""
    if intro:
        chosen.append((0, intro)); used += len(intro)
    for score, i, p in sorted(scored, key=lambda x: -x[0]):
        if i == 0 or score <= 0:
            continue
        if used + len(p) > cap:
            continue
        chosen.append((i, p)); used += len(p)
        if used >= cap * 0.95:
            break
    if len(chosen) <= 1:
        # 질의와 겹치는 문단이 하나도 없으면(다른 언어 노트 등) 제목만 주지 말고 본문 순서대로 채운다.
        # (tp-light-ko-1b: 한국어 문장으로 영어 노트를 고르니 제목 93자만 남아 인용 검사가 '본문 생략'으로 오탐)
        have = {i for i, _ in chosen}
        for i, p in enumerate(paras):
            if i in have or len(p) < 60:
                continue
            if used + len(p) > cap:
                continue
            chosen.append((i, p)); used += len(p)
            if used >= cap * 0.95:
                break
    chosen.sort()
    text = "\n\n[…]\n\n".join(p for _, p in chosen)
    omitted = len(body) - used
    return text + f"\n\n[… 관련도 낮은 {omitted:,}자 생략: 이 노트는 잘렸다 …]\n", True
