---
name: hyperresearch-codex
description: 질문 하나로 출처 기반 리서치 보고서를 만든다. "리서치해줘", "출처 붙여서 정리", "조사 보고서", "깊게 조사" 요청 때. 단계는 파이썬 드라이버가 돌리고 Codex 는 단계별 판단만 한다. / One prompt → sourced research report; Python drives the steps, Codex only judges.
---

# hyperresearch-codex

설치 위치는 `HPR_HOME` 환경변수 또는 `~/hyperresearch-codex` 로 본다. (Set `HPR_HOME` to the cloned repo.)

1. 사용자의 질문을 **한 글자도 바꾸지 않고** 확정한다. 모호하면 한 번만 되묻는다.
2. 가벼운 질문은 Light, "깊게·전체적으로·보고서급"이면 Full:
   `python3 "${HPR_HOME:-$HOME/hyperresearch-codex}/hpr.py" run "<질문 원문>" [--tier full] [--urls 파일 --no-search] [--scholar]`
   Full 은 모델 호출 약 15회라 사용자에게 먼저 알린다.
3. `BLOCKED:` 가 나오면 이유를 그대로 보고하고 멈춘다. 단계를 직접 대신 수행하지 않는다.
4. 끝나면 `research/runs/<id>/final_report.md` 첫 주석 줄(출처·지적·인용 미지지·린트·토큰)을 요약하고 경로를 알린다.
5. 이전 조사 재사용: `hpr.py search "키워드"` 또는 MCP 도구 `search_notes`.

금지: 보고서 게시·전송, 노트 삭제, 다른 프로젝트 파일 수정, 사용량 한도 우회.
