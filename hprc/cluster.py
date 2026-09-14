"""출처 관계 휴리스틱: 같은 정본 URL 또는 본문 유사도(8단어 조각 Jaccard)로 중복 후보를 묶어 근거 수를 보수적으로 센다. 발행자·원문 계보·독립성은 확정하지 않는다."""
import re


def shingles(text: str, k: int = 8) -> set[str]:
    words = re.findall(r"\w+", text.lower())
    return {" ".join(words[i:i + k]) for i in range(max(0, len(words) - k + 1))}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cluster(sources: list[dict], texts: dict[str, str], threshold: float = 0.6) -> dict[str, str]:
    """반환: {source_id: cluster_id}. cluster_id 는 묶음 첫 출처의 id."""
    ids = [s["id"] for s in sources]
    sh = {i: shingles(texts.get(i, "")) for i in ids}
    canon = {s["id"]: (s.get("canonical") or "").lower().rstrip("/") for s in sources}
    assign = {}
    for i in ids:
        if i in assign:
            continue
        assign[i] = i
        for j in ids:
            if j in assign:
                continue
            same_canon = canon[i] and canon[i] == canon[j]
            if same_canon or jaccard(sh[i], sh[j]) >= threshold:
                assign[j] = i
    return assign
