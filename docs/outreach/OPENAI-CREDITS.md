# OpenAI 오픈소스 지원 신청 준비 (2026-09-26 확인)

## 현재 공식 조건

- [Codex for Open Source](https://developers.openai.com/community/codex-for-oss)는 공개 오픈소스의 주 유지관리자 또는 핵심 유지관리자에게 열려 있다. 채택되면 ChatGPT Pro 6개월, 별도 심사 대상인 Codex Security, 핵심 OSS 유지보수 작업에 쓰는 API 크레딧을 받을 수 있다. 혜택은 신청자별로 달라질 수 있으며 선정은 보장되지 않는다.
- [신청 양식](https://openai.com/form/codex-for-oss/)은 공개 GitHub 프로필·저장소, 유지관리자 역할, 저장소의 사용·생태계 중요성, OpenAI 조직 ID, API 크레딧 사용 계획을 묻는다. 사용·중요성 설명과 크레딧 계획은 각각 500자 이하다. 신청은 수시 심사이며 공식 페이지에 고정 마감일은 표시되지 않았다.
- [프로그램 약관](https://learn.chatgpt.com/docs/codex-for-oss-terms)은 유효한 ChatGPT 계정, 정확한 본인·저장소·역할 정보, 유지관리 활동과 사용 증거 등을 명시한다. 필요하면 관리 권한 검증을 요청할 수 있다. 신청 자료에 비밀 정보를 넣지 않는다.
- [기존 Codex Open Source Fund 양식](https://openai.com/form/codex-open-source-fund/)도 수시 심사와 최대 25,000달러 API 크레딧을 표시하지만, 현재 안내의 주 신청 경로는 위 Codex for Open Source 양식이다. 크레딧 액수를 이 저장소에 보장된 혜택으로 쓰지 않는다.

## 이 저장소의 증거 격차

2026-09-26 읽기 조회: 공개 `main` = `ba850468`, v0.4.0, 별 1, 포크 0. 이번 실사용에서 [출처 후보 편중](https://github.com/choisam4u-creator/hyperresearch-codex/issues/5), [수치 문맥 경고](https://github.com/choisam4u-creator/hyperresearch-codex/issues/6), [출처 목록 불일치](https://github.com/choisam4u-creator/hyperresearch-codex/issues/9) 이슈를 기록했고, 기여자가 맡을 수 있는 문서·상태 표시 이슈 2건을 열었다. 이 숫자는 신청 자격의 공식 하한이 아니다.

| 검토 신호 | 현재 확인 | 다음 증거 |
|---|---|---|
| 실제 사용 | 예시 보고서와 과거 실측은 있으나 외부 사용자 수는 미확인 | 개인 정보를 뺀 실사용 사례, 시간·토큰·인용 검사 결과 |
| 유지관리 | v0.4.0 릴리스와 회귀·CI 기록이 있음 | 실제 사용에서 나온 재현 가능한 이슈와 수정·검증 이력 |
| 채택 | 별 1, 포크 0; 다운로드 수는 미확인 | 측정 가능한 설치·사용 피드백과 문서 개선 |
| 크레딧 계획 | 초안 미완성 | PR 검토·이슈 분류·릴리스 검증 등 OSS 작업의 구체적 예산과 목적 |

우선순위: (1) 도구로 실제 조사하고 민감 정보를 제외한 측정 기록 작성, (2) 관찰된 오류를 재현 가능한 이슈로 기록, (3) 결과와 검증 한계가 담긴 사례 문서·README 연결, (4) 유지관리 용도의 크레딧 계획 작성. 신청 제출과 계정 정보 입력은 소유자가 한다.
