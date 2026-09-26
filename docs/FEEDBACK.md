# 피드백 보내기

`hpr feedback RUN_ID`는 이미 존재하는 실행의 비식별 진단 JSON을 화면에 출력합니다. 이 명령은 네트워크로 전송하지 않으며 모델이나 조사 파이프라인을 호출하지 않습니다. 출력에는 고정된 상태 열거형과 호출·토큰·시간·단계 수치만 들어갑니다. 프롬프트, 출처 본문·URL, 원시 로그, 로컬 경로, 오류 문자열, 계정 정보는 포함하지 않습니다. 알 수 없거나 허용 목록 밖인 값은 `null`입니다. `backend: "mock"`과 `token_measurement: "estimated"`는 mock 계산값입니다. 실제 Codex 기록은 `recorded`, 누락되거나 섞인 기록은 `unknown`입니다.

```console
hpr feedback my-run
```

`model_calls`는 저장된 전체 호출 행 수이고 `known_usage_calls`와 `unknown_usage_calls`가 측정 여부를 나눕니다. 토큰 합계는 `known_usage_calls`에 속한 행만 더하므로 미측정 호출까지 포함한 전체 토큰으로 해석하면 안 됩니다.
`run_status: "warn"`은 실행이 최종 단계까지 끝났지만 `quality_status: "review_required"`처럼 사람의 검토가 필요한 결과일 수 있음을 뜻합니다.

<a id="review-required-result"></a>
## `review_required` 결과 확인 순서

`review_required`는 보고서 파일이 없다는 뜻이 아니라, 자동 검사 범위에서 사람이 확인할 항목이 남았다는 뜻입니다. 해당 실행 폴더의 `quality.json`에서 `issues`를 확인하고 `final_report.md`의 **검증 상태**와 비교하세요.
경고가 가리킨 주장과 출처를 직접 대조해 해결하기 전까지는 해당 결론을 **HOLD(사용 보류)**로 취급하세요. 확인된 문제 문장을 제거하거나 고친 뒤 다시 검사하고, 단순히 종료 코드만 0으로 바꾸지 마세요.

- `citation_unsupported`: 검사한 인용 표본 중 원문이 해당 문장을 충분히 뒷받침하지 못했습니다. 그 문장을 결론으로 채택하지 말고 출처 원문을 직접 확인하세요.
- `numeric_evidence_unclear` 또는 `numeric_context_unclear`: 수치가 없거나 같은 수치가 다른 문맥에 있을 수 있다는 보수적 경고입니다. 모든 경고가 오류라는 뜻은 아니며, 단위·조건·기간을 원문과 대조해야 합니다.
- `review_required`인데 위 항목이 없다면 `quality.json`의 다른 issue와 `remaining_gaps`를 확인하세요. 인용 검사는 표본 검사이므로 `0/N unsupported`도 보고서 전체 검증을 뜻하지 않습니다.

재현 가능한 문제를 보고할 때는 `hpr feedback RUN_ID`의 허용 목록 JSON, OS·Python·hpr 버전과 합성 또는 mock 최소 재현만 사용하세요. 질문, 가져온 본문, 원시 로그, 사용자 경로와 계정 정보는 공개 이슈에 넣지 마세요. 전용 [review-required 이슈 양식](../.github/ISSUE_TEMPLATE/review-required.yml)을 사용할 수 있습니다.

내용을 직접 검토한 뒤 GitHub 이슈 양식에 붙여 넣으세요. 설치 실패나 합성 데모처럼 기존 실행이 없으면 JSON 칸은 비워 둘 수 있습니다. 이슈는 공개되며 제출은 수동입니다. 성공 사례와 실패 사례를 모두 환영합니다. 원한다면 공개 가능한 한 문장 설명과 공개 출처 URL을 별도 필드에 적을 수 있지만, 비공개 질문·본문·로그·경로·자격 증명은 올리지 마세요.

설치 후 실행 흐름만 보고 싶다면 `hpr demo`를 실행할 수 있습니다. 이것은 네트워크와 모델 호출이 0회인 합성 미리보기이며 실제 연구, 실제 사용 사례, 보고서 품질의 증거가 아닙니다.
