# 파이프라인 단계별 산출물 예시 (가짜 응답)

`evals/cases/ko-bike-lanes.json`의 고정 질문 하나를 light tier로 돌린 결과다. 모델 단계는 기록된 가짜 응답(작성자)과 `hprc.mock`의 기계적 응답으로 대신했고, 외부 검색·다운로드는 하지 않았다. 내용의 사실성을 보여 주는 예시가 아니라 **각 단계가 어떤 파일을 남기고 게이트가 무엇을 고치는지** 보여 주는 예시다.

| 순서 | 파일 | 단계 | 볼 점 |
|---|---|---|---|
| 1 | `frozen_input.json` | 고정 입력 | 질문·언어·합성 출처 원문 S1~S3 |
| 2 | `sources.json` | 수집 | 출처별 노트 경로·관계 묶음(cluster) |
| 3 | `claims.json` | 분석(analyst) | 출처에서 뽑은 주장과 인용 별칭 |
| 4 | `draft.md` | 작성(writer) + 초안 게이트 | 작성자가 쓴 없는 출처 `[S4]`가 `(출처 없음)`으로 바뀜 |
| 5 | `draft_gate.json` | 초안 게이트 기록 | 지운 별칭 `S4`, 복제 출처 정리 내역 |
| 6 | `findings.json` | 비평(critics) | 통과한 비평 지적 |
| 7 | `citecheck.json` | 인용 표본 검사 | 표본 문장별 지지 판정 |
| 8 | `report.md` | 수정·다듬기 후 보고서 | |
| 9 | `quality.json` | 자동 검증 | `unknown_cites_removed`로 `review_required` |
| 10 | `final_report.md` | 최종 | 검증 상태·인용 표본·출처 상세가 붙은 결과 |

다시 만들기:

```bash
HPR_BACKEND=mock python -m evals.walkthrough examples/pipeline-walkthrough
```
