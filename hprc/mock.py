"""테스트용 가짜 모델: Codex 를 부르지 않고 스키마에 맞는 답을 입력에서 기계적으로 만든다."""
import html
import json
import re


def _first_sentence(text: str) -> str:
    match = re.search(r"<data_only>\n(.*?)\n</data_only>", text, re.S)
    body = html.unescape(match.group(1)) if match else text
    body = body.split("\n---\n", 1)[-1]
    body = re.sub(r"^#.*$", "", body, flags=re.M).strip()
    match = re.search(r"[^.\n!?]{20,200}[.!?]", body)
    return (match.group(0) if match else body[:120]).strip()


def _report(question: str, claims: list[dict], notes: dict, tag: str = "", en: bool = False) -> str:
    if en:
        body = [f"# Question: {question}", "", "## Answer", f"Mock conclusion{tag}. " + " ".join(f"{c['text']} [{c['sources'][0]}]" for c in claims[:2]),
                "This is the best order. (judgment) [S1]", "", "## Evidence"] + [f"{c['text']} [{c['sources'][0]}]" for c in claims] + \
               ["", "## Counter-evidence and limits", "Mock limit: few sources. (no source)", "", "## Next actions", "- collect more sources", "",
                "## Sources"] + [f"- [{k}] note {k}" for k in sorted(notes)]
        return "\n".join(body) + "\n"
    body = [f"# 질문: {question}", "", "## 답", f"모의 결론{tag}입니다. " + " ".join(f"{c['text']} [{c['sources'][0]}]" for c in claims[:2]), "",
            "## 근거"] + [f"{c['text']} [{c['sources'][0]}]" for c in claims] + \
           ["", "## 반대 근거와 한계", "모의 한계: 출처 수가 적습니다. (출처 없음)", "", "## 다음 행동", "- 출처를 더 모은다", "",
            "## 출처"] + [f"- [{k}] {k} 노트" for k in sorted(notes)]
    return "\n".join(body) + "\n"


def mock_backend(step: str, prompt: str, inputs: dict) -> dict:
    notes = {re.match(r"S[0-9]+", k).group(0): v for k, v in inputs.items() if k.startswith("S") and k.endswith(".md")}
    question = inputs.get("question.txt", "").strip()
    if step == "scout":
        return {"results": []}   # 테스트에서는 URL 목록을 쓴다
    if step in ("analyst", "analyst_gap", "analyst_update"):
        claims = [{"id": f"C{i+1}", "text": _first_sentence(v), "sources": [k], "confidence": "high"}
                  for i, (k, v) in enumerate(sorted(notes.items()))]
        if step == 'analyst_update':
            retained = json.loads(inputs.get('retained_claims.json', '[]'))
            for i, claim in enumerate(claims): claim['id'] = f'UPDATED{i+1}'
            claims = retained + claims
        return {"claims": claims, "contradictions": [], "gaps": ["모의 분석: 빈틈 예시"]}
    if step == "loci":
        first = sorted(notes)[:1]
        return {"loci": [{"id": "L1", "question": "모의 깊이 질문", "why": "노트가 얕음", "source_ids": first}]}
    if step.startswith("investigator"):
        first = sorted(notes)[:1]
        return {"position": "모의 입장: 확실하지 않다.", "evidence": [{"claim": "모의 근거 문장", "source_ids": first}], "open_questions": ["모의 열린 질문"]}
    if step == "writer" or step.startswith("draft") or step == "synth":
        en = "## Answer" in prompt
        claims = json.loads(inputs["claims.json"])["claims"] if "claims.json" in inputs else []
        if step == "synth":
            drafts = [v for k, v in inputs.items() if k.startswith("drafts/")]
            return {"markdown": drafts[0].replace("모의 결론", "종합 결론").replace("Mock conclusion", "Synthesized conclusion") if drafts else _report(question, claims, notes, " 종합", en)}
        tag = "" if step == "writer" else f" ({step})"
        return {"markdown": _report(question, claims, notes, tag, en)}
    if step.startswith("critic_"):
        draft = inputs["draft.md"]
        lines = draft.splitlines()
        if step == "critic_dialectic":
            idx = next((i for i, l in enumerate(lines) if l.startswith(("## 근거", "## Evidence"))), -1) + 1
            quote = lines[idx] if 0 < idx < len(lines) else ""
            return {"findings": [{"id": "F1", "quote": quote, "problem": "모의 지적: 반대 근거 없음", "suggested_fix": quote + " 다만 반대 사례도 있다.",
                                  "severity": "medium", "source_ids": [sorted(notes)[0]] if notes else []}]}
        if step == "critic_instruction":
            return {"findings": [{"id": "F9", "quote": "이 문장은 초안에 없습니다", "problem": "지어낸 비평(게이트가 버려야 함)",
                                  "suggested_fix": "", "severity": "low", "source_ids": []}]}
        return {"findings": []}
    if step == "patcher":
        findings = json.loads(inputs["findings.json"])["findings"]
        return {"hunks": [{"find": f["quote"], "replace": f["suggested_fix"], "finding_ids": [f["id"]]} for f in findings if f.get("suggested_fix")], "skipped": []}
    if step == "polish":
        report = inputs["report.md"]
        return {"hunks": [{"find": "모의 한계: ", "replace": "한계: ", "finding_ids": []}] if "모의 한계: " in report else [], "skipped": []}
    if step in ("citecheck", "citecheck_changed"):
        samples = json.loads(inputs["samples.json"])
        if "SEMANTIC_EVIDENCE_V1" in prompt:
            return {"checks": [{"sentence": s["sentence"], "cites": s["cites"], "supported": False,
                               "reason": "mock: no semantic judgment", "atoms": [{"quote": s["sentence"],
                               "verdict": "insufficient", "evidence": [], "conditions": "unknown", "limitations": "mock"}]} for s in samples]}
        return {"checks": [{"sentence": s["sentence"], "cites": s["cites"], "supported": True, "reason": "모의 검사"} for s in samples]}
    raise ValueError(f"mock: 모르는 단계 {step}")
