"""출처 독립성: 같은 정본 URL 이거나 본문이 거의 같은(8단어 조각 Jaccard) 출처를 한 묶음으로 본다. 다섯 번 퍼 나른 보도자료는 하나로 센다."""
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
