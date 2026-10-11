# PR #17 맥 실응답 시험 — 2026-10-10

상태: PARTIAL

승인된 실 Codex 호출 3회를 실행해 정찰 응답 3개를 받았다. 각 실행은 호출 상한 1회에 도달해 analyst 단계 전에 종료했다. 완성 보고서는 0개이고, tests/fixtures/real/에 넣을 보고서는 확보하지 못했다.

## 대상과 명령

- 원 task: ENTRY9-OSS3-REGISTRATION-PR-INTAKE-20261010-CANDIDATE1-hyperresearch-codex-MAC-TEST
- PR: https://github.com/choisam4u-creator/hyperresearch-codex/pull/17
- 시험 코드 HEAD: `517efba1c33551656bfd7e58fd9f19632c421c07`
- 이전 보고 커밋: `11fcbc274f59c5757b85ef127358be7428f9607a`
- Python 3.14.7, Codex CLI 0.162.0-alpha.2, macOS arm64.
- doctor exit0: 기존 ChatGPT 로그인 확인. 기준 CLI 버전 차이와 pypdf 없음 확인.
- 전체 mock576·eval32 평균100.0은 원 시험 기록이며 이번에 재실행하지 않았다.

각 질문은 `PYTHONDONTWRITEBYTECODE=1 HPR_BACKEND=codex python3 hpr.py run "질문" --run-id <아래 ID> --preset lean --max-calls 1 --budget 800000 --lang ko`로 시작했다. 모델 단계를 직접 호출하지 않았다. codex exec read-only와 output-schema 경로를 사용했다.

| run ID | 질문 | 호출/종료 | 입력/출력 토큰 | 관측 |
|---|---|---|---|---|
| pr17-real-20261010-resume1-camera | 어린이보호구역 과속 단속카메라는 사고를 줄였나? 근거와 한계를 밝혀라 | 1 / exit2 | 207461 / 1350 | scout 스키마 통과, analyst 예산 중단 |
| pr17-real-20261010-resume1-noise | 도로 방음벽은 주거지 소음을 얼마나 줄이는가? 효과의 범위와 한계를 밝혀라 | 1 / exit2 | 204752 / 1068 | scout 스키마 통과, analyst 예산 중단 |
| pr17-real-20261010-resume1-ebus | 전기버스 보조금과 충전소 설치비는 얼마였나? 대당·곳당·총계 기준을 구분하라 | 1 / exit2 | 261708 / 1420 | scout 스키마 통과, analyst 예산 중단 |

측정 입력 합계 673,921, 캐시 입력 493,184, 출력 3,838토큰이다. 캐시 입력은 입력에 포함되므로 더하지 않는다. 이전 누적 사용량과 구독 잔량은 UNKNOWN이다. 이번 승인분은 3/3회 사용했고 재시도는 0회다. CLI의 달러 환산은 구독 결제액을 뜻하지 않는다.

## 검증과 남은 조건

실 응답 3개를 원 events의 최종 agent_message와 결속하고 SCOUT 필수 키·추가 키·타입을 검사했다. 응답은 검색 결과 목록이며 writer 보고서가 아니다. analyst START 출력 뒤 실 자식 호출은 없고 manifest에는 각 scout 성공 1회만 있다. 운영 코드·기존 assert 변경은 없다.

CLI plan은 Light lean 예상 단계 호출 최대7과 실행 상한1을 별도 표시한다. 세 완성 보고서를 얻으려면 정찰 뒤 분석·작성·비평·인용검사를 이어갈 호출 승인이 필요하다. 호출 상한이나 운영 코드를 바꾸지 않았다.

wording_conflict 오표시율·실응답 품질·100점 천장 밖의 새 결함·CI·Windows·wheel·실PDF 검증은 결과 없음이다. 정찰응답 스키마 검사로 품질 평가를 대체하지 않았다. 독립 review1과 같은 PR SHA Claude 감사는 대기다.

## 자기 점검

| 필수 항목 | 자기 점검 |
|---|---|
| 실제 응답 기원·모델·사용량 | 통과: codex manifest/event SHA와 결속 |
| 실응답과 완성 보고서 구분 | 통과: 정찰3·완성0 명시 |
| 원 예산과 UNKNOWN 보존 | 통과: 이전UNKNOWN·이번3/3 별도 |
| 코드·기존 시험·다른 작업 보존 | 통과: 문서만 변경 |
| 공개 문서 경로·비밀 검사 | 통과: 개인 절대경로·비밀값 제외 |
| AI 티·상태·사실 근거 | 통과: 관측과 미측정 분리 |

읽은 교훈: [[코덱스 운영]]
적용: 실 영수증과 보고서 완성을 구분하고 원 코드 SHA·예산을 보존했다. 교훈 활용도·같은 원인 재발 수는 UNKNOWN이다.
