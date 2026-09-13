<!-- hyperresearch-codex light -->
<!-- run: demo-01 · 출처 8개 · 지적 4개 · 인용표본 6개 중 미지지 2개 · 린트 ['section_missing:## 한계'] -->
# 질문: OpenAI Codex CLI의 codex exec를 자동화 파이프라인에서 쓸 때 샌드박스 모드, JSON 출력 스키마, 비대화형 실행 옵션은 어떻게 동작하고 무엇을 주의해야 하나?

## 답

`codex exec`는 TUI 없이 스크립트와 CI에서 작업을 실행하며, 기본 출력에서 진행 정보는 stderr로, 최종 답변은 stdout으로 분리한다. [S4] 제공 자료를 기준으로 읽기·분석은 `read-only`에서 시작하고, 파일 수정이 필요한 작업에만 `--sandbox workspace-write`를 명시하는 것이 적절하다. [S4][S8] 실행 이벤트를 수집하려면 `--json`을, 정해진 JSON 필드로 최종 결과를 받으려면 `--output-schema`와 `-o`를 조합한다. [S4] 다만 `--full-auto`의 지원 상태와 비대화형 실행 중 승인 처리에 관한 설명이 서로 달라, 자료의 예시를 모든 버전에 적용할 수는 없다. [S1][S4][S6]

## 근거

**기본 실행과 출력 분리.** `codex exec`는 반복적인 저장소 요약, 검토, 문서화처럼 스크립트에서 호출할 작업에 적합한 비대화형 진입점이다. [S4] 기본 실행에서는 최종 agent 메시지를 stdout으로 받아 후속 명령에 전달하고, 진행 로그는 stderr에서 별도로 확인할 수 있다. [S4] 따라서 최종 요약만 필요한 작업은 기본 출력을 사용하고, 실행 과정까지 수집할 때 출력 방식을 바꾸는 구성이 자료의 권고에 부합한다. [S4]

**샌드박스의 파일 접근 범위.** S4·S7·S8은 CLI 기본 모드를 파일 수정이 불가능한 `read-only`로 설명한다. [S4][S7][S8] 반면 S6의 GitHub Action 입력 표는 `sandbox` 기본값을 `workspace-write`로 제시하므로, 읽기 전용 검토에는 S2 예시처럼 `sandbox: read-only`를 명시한다. [S2][S6] `workspace-write`는 워크스페이스 안의 쓰기를 허용하므로 코드 생성이나 수정 작업에 사용한다. [S6][S7] S6의 표는 네트워크를 `workspace-write`에서 `Restricted`, `read-only`에서 `None`으로 표시하지만, 이 표만으로 구체적인 예외 설정까지 설명하지는 않는다. [S6] `danger-full-access`는 파일 시스템과 네트워크 접근을 넓히므로 신뢰할 수 있는 격리 환경에 한정하며, S1이 설명하는 `--yolo`는 샌드박스와 승인을 우회하는 옵션이다. [S1][S4][S6]

**샌드박스와 승인 정책.** S1은 수정 권한을 `--sandbox workspace-write`로 명시하고 승인 정책은 config/requirements에서 별도로 관리하도록 안내한다. [S1] S6에는 프로젝트의 `.codex/config.toml` 안에 `[profiles.ci]`를 만들고 `sandbox_mode = "workspace-write"`, `approval_policy = "never"`를 설정한 뒤 `codex --profile ci exec`로 실행하는 예시가 있다. [S6] 그러나 S4는 자동화에서도 승인 prompt 때문에 멈출 수 있다고 경고하므로, 이 예시만으로 모든 환경의 무중단 실행이 보장된다고 해석해서는 안 된다. [S4][S6]

**JSONL 이벤트 출력.** `--json`은 stdout에 실행 이벤트를 JSON Lines 형식으로 내보내며, 최종 답변 하나만 JSON 객체로 반환하는 옵션과 구별된다. [S1][S4][S6] S6는 `thread.started`, `turn.started`, `turn.completed`, `item.started`, `item.completed`를 나열하고 `turn.completed`에 토큰 사용량이 포함된다고 설명한다. [S6] S1은 `0.125.0`부터 reasoning token usage도 포함된다고 기술한다. [S1] 이 방식은 진행 상태와 도구 실행을 수집하는 프로그램에 맞으며, 최종 답변만 필요한 경우에는 불필요한 이벤트 처리 부담이 생길 수 있다. [S4]

**최종 응답의 JSON Schema.** `--output-schema`는 마지막 응답을 지정한 JSON Schema에 맞추는 옵션이며, `-o` 또는 `--output-last-message`는 마지막 메시지를 파일에 저장한다. [S1][S4][S6] S4에 따르면 파일에 저장해도 stdout 출력은 유지된다. [S4] 예컨대 `codex exec "Extract metadata" --output-schema ./schema.json -o ./result.json`은 스키마에 맞춘 최종 결과를 파일로 저장하는 방식이다. [S4] S6의 PR 검토 스키마 예시는 `severity`를 `low`, `medium`, `high`, `critical` 중 하나인 문자열로, `issues`를 `file`·`message` 문자열과 `line` 숫자 속성을 정의한 객체 배열로, `summary`를 문자열로 지정하지만, `required`는 지정하지 않는다. [S6] 다만 스키마는 사실관계를 보장하지 않으며, S1은 특히 이전 맥락을 이어받는 실행에서 별도 검증 단계를 두라고 안내한다. [S1]

**세션 저장과 재개.** `--ephemeral`은 session rollout 파일을 디스크에 남기지 않으므로, 이후 `codex exec resume --last`로 이어갈 실행에는 사용하지 않는다. [S4][S6] S6는 `codex exec resume --last`와 `codex exec resume <SESSION_ID>`를 이전 세션을 이어가는 방법으로 제시한다. [S6] S1은 `0.132.0`부터 resume에 `--output-schema`를 사용할 수 있고, `0.148.0`부터 `codex exec fork`로 기존 thread를 분기할 수 있다고 설명한다. [S1]

**입력 전달과 실행 환경.** S1은 `0.118.0`부터 stdin 입력과 별도 프롬프트 인자를 함께 전달하는 흐름을 지원한다고 설명한다. [S1] S2는 CLI의 `--prompt-file` 예시를 제공하지만, S6가 설명하는 GitHub Action의 `prompt-file`은 Action 입력 항목이다. [S2][S6] S1에 따르면 `--skip-git-repo-check`는 Git 저장소 요구사항을 우회하므로 격리된 안전 환경에서만 예외적으로 사용한다. [S1] 또한 S1은 `0.122.0`에 추가된 `--ignore-user-config`와 `--ignore-rules`를 개인 설정과 로컬 rules의 영향을 제외하는 실험·CI 옵션으로 소개한다. [S1]

**비밀값과 후속 작업.** S1과 S4는 API 키를 단일 `codex exec` 호출에 제한하고, 저장소 코드를 실행하는 job의 전역 환경에 `OPENAI_API_KEY`나 `CODEX_API_KEY`를 두지 말라고 권고한다. [S1][S4] 빌드 스크립트, 테스트, dependency hook, 손상된 Action이 해당 환경의 키를 읽을 수 있기 때문이다. [S1][S4] S2는 키를 GitHub secret으로 관리하고 `~/.codex/auth.json`을 커밋하지 않으며, 악의적 지시가 들어갈 수 있는 PR 본문이나 커밋 메시지를 프롬프트에 그대로 넣지 말라고 경고한다. [S2] S1과 S6는 `openai/codex-action@v1` 및 `safety-strategy: drop-sudo`를 안내하며, S6는 이를 표준 Linux/macOS GitHub runner용으로 설명하고 이후 같은 job의 단계에서도 sudo를 사용할 수 없다고 명시한다. [S1][S6] S6는 계정이 사전 설정된 self-hosted runner에는 비루트 사용자로 실행하는 `unprivileged-user`를 제시하고, 권한을 축소하지 않는 `unsafe`는 Windows 전용으로 설명한다. [S6]

## 반대 근거와 한계

`--full-auto`에 대해 S6는 확인 없는 편집에 사용하도록 권장하고, 마지막 수정일이 2026년 8월 10일인 S4는 경고가 표시되는 deprecated 호환 옵션이라고 설명하며, S1은 `0.147.0`에서 제거됐다고 말한다. [S1][S4][S6] 이는 동일한 CLI에 동시에 적용할 수 없는 설명이며, 사용할 버전과 해당 버전의 도움말 출력이 제공되지 않아 실제 지원 상태는 확정할 수 없다. (출처 없음)

S6의 사용자 질문 없는 자율 실행이라는 설명과 S4의 승인 prompt에 따른 정지 가능성도 어긋난다. [S4][S6] 승인 정책 기본값, 권한이 필요한 경우의 대기·거부·실패 구분, config/requirements 적용 우선순위, 운영체제와 runner별 차이는 제공 자료만으로 확정할 수 없다. (출처 없음)

S6의 “스크립트 파싱에 `--json`이 필요하다”는 표현은 S4가 구분한 이벤트 파싱과 최종 JSON 응답 파싱을 나눠 읽어야 한다. [S4][S6] JSON Schema 지원 범위, 잘못된 스키마나 응답 거부·중단 시 결과 파일 생성 여부, 종료 코드에 관한 구체적인 계약은 제공되지 않았다. (출처 없음) JSONL의 전체 필드 명세와 실제 로그도 없어 S6의 `thread.started`에서 `.id`를 추출하는 예시를 검증하지 못했으며, 타임아웃·재시도·부분 성공의 판정 방식도 미확인이다. (출처 없음)

S6는 키를 `export`하는 예시와 단일 호출에 제한하는 예시를 모두 제공하지만, `CODEX_API_KEY`가 표준 변수라는 주장에는 `[unverified]`를 붙인다. [S6] 따라서 키의 노출 범위를 좁히라는 운영 권고와 인증 변수의 지원·우선순위가 검증됐다는 판단은 구분해야 한다. [S1][S4][S6]

S3와 S5는 같은 저장소의 동일한 README이므로 독립적인 교차 검증 자료로 셀 수 없으며, 스스로 비공식 가이드라고 밝히고 세부 동작은 `codex --help`로 확인하도록 안내한다. [S3][S5] S1에는 말미 생략 표시도 있어 전체 원문을 확보한 자료가 아니다. [S1] 이번 보고서는 제공 노트를 종합한 것으로, 공식 원문 재검증이나 실제 CLI 실행 시험을 수행한 결과는 아니다. (출처 없음)

## 다음 행동

1. 사용할 CLI 버전과 도움말을 기록하고, 특히 `--full-auto`, `--prompt-file`, 설정 제외 옵션, resume/fork의 지원 여부를 대조한다. [S1][S2][S3][S5]
2. 작업별 입력·쓰기 경로·네트워크·비밀값 필요성을 정하고, CI 실패 자동 수정 제안은 S8처럼 읽기 권한 job에서 패치 artifact만 만들고 PR 생성은 별도 job으로 분리한다. [S8] 문서 초안을 파일로 저장하는 작업에는 `--sandbox workspace-write`와 출력 경로 제한을 함께 적용한다. [S8]
3. 이벤트 수집에는 `--json`, 최종 구조화 결과에는 `--output-schema`와 `-o`를 선택하고, 수정 결과의 diff와 검증 명령을 남긴다. [S4][S8] 실패·중단 시험으로 종료 코드와 산출물 검사 기준을 정하는 것은 이 보고서의 추가 제안이다. (출처 없음)
4. 키를 단일 실행에 제한하고 가져온 훅의 내용을 확인하며, 외부 API 호출·공개 발행·계정 작업에는 사람 승인 또는 별도 게이트를 둔다. [S1][S3][S5][S8]

## 출처

- [S1] [Ch7. exec/자동화 | Codex 고급 활용 — 리옵트 핸드북](https://handbook.reopt.ai/ko/books/codex-advanced/exec)
- [S2] [Codex CLI 입문 (6) : Codex 자동화 파이프라인 구축 - 사람 없이 돌아가는 Codex](https://goddaehee.tistory.com/601)
- [S3] [GitHub - Ihan0316/codex-code-toolkit: 실무에서 다듬은 OpenAI Codex CLI 실전 셋업 ...](https://github.com/Ihan0316/codex-code-toolkit/tree/main)
- [S4] [codex exec 기본 | RefDock](https://refdock.kr/gpt/codex-exec-basics)
- [S5] [GitHub - Ihan0316/codex-code-toolkit: 실무에서 다듬은 OpenAI Codex CLI 실전 셋업 ...](https://github.com/Ihan0316/codex-code-toolkit)
- [S6] [Codex CLI for CI/CD: codex exec, Non-Interactive Mode and Pipeline ...](https://codex.danielvaughan.com/2026/03/26/codex-cli-cicd-non-interactive/)
- [S7] [GPT-5 Codex CLI 사용법 7단계 — Rust 설치·config.toml·모델 - cadenhub](https://www.cadenhub.com/gpt-5-codex-cli-%EC%82%AC%EC%9A%A9%EB%B2%95-2/)
- [S8] [Codex exec 자동화 사용법: CI·예약 작업 전에 권한부터 정하기](https://eroke-note.tistory.com/32)

## 인용 검사에서 걸린 문장
- [S4] 다만 `--full-auto`의 지원 상태와 비대화형 실행 중 승인 처리에 관한 설명이 서로 달라, 자료의 예시를 모든 버전에 적용할 수는 없다. → 부분 지지: S4는 --full-auto가 deprecated 상태로 남아 있고 승인 prompt에서 실행이 멈출 수 있다고 설명하지만, 설명 간 차이나 버전별 적용 범위는 제시하지 않는다. 인용된 S4만으로 자료 간 불일치를 입증할 수 없다.
- [S1][S4][S6] → 인용 표시만 있고 검증할 문장이나 주장이 없어 지지 여부를 판단할 수 없다.
