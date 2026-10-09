# PR #17 맥 시험 — 2026-10-10

상태: PARTIAL

맥 mock 시험 576개와 오프라인 평가 32개가 통과했다. 실 Codex 호출 기존 사용량은 UNKNOWN이어서 이번 호출을 시작하지 않았다. 실제 응답 픽스처와 wording_conflict 실응답 오표시율은 결과 없음이다.

## 대상과 환경

- task: ENTRY9-OSS3-REGISTRATION-PR-INTAKE-20261010-CANDIDATE1-hyperresearch-codex-MAC-TEST
- PR: https://github.com/choisam4u-creator/hyperresearch-codex/pull/17, 조회 시 OPEN.
- tested code HEAD: `517efba1c33551656bfd7e58fd9f19632c421c07`
- base HEAD: `800c0abace2e5d205a577d97f9721615e7953625`
- gitTree: `826c93a1b1bccfd416d8e2127c6491ef95c1f158`
- codeTreeHash: `55c8166b8f8423eb7b04993aa5c49d39b62f328b60d43759428e77e9f6b79e8a`
- 해시 방식: tracked hprc/evals/tests/prompts/hpr.py/pyproject.toml의 path:sha256 정렬 compact JSON을 SHA256으로 계산했다. 전체 manifest는 원 task evidence/provenance.json에 있다.
- 환경: macOS-26.6.2-arm64-arm-64bit-Mach-O, Python 3.14.7, httpx0.28.1, SQLite FTS5.
- Codex CLI0.162.0-alpha.2, 프로젝트 기준0.153.4와 다르다. doctor는 기존 ChatGPT 로그인 상태만 확인했다.
- pypdf 없음: PDF 읽기는 결과 없음이다. Blender는 HPR 범위에 해당 없음.
- source: /Users/sam/Documents/ChatGPT/오픈소스/hyperresearch-codex, main, HEAD70edc68c451bd46506883502d850e95a4e7ab44d, dirty0/index0.
- 원 source의 다른 CWD 프로세스를 보존하고 동일origin 독립 checkout을 사용했다. fetch는 origin/main ref만 base까지 갱신했다.
- origin: https://github.com/choisam4u-creator/hyperresearch-codex.git
- 독립 checkout: `/Users/sam/Desktop/클로드/Hermes-Project-Ops/state/worklog/outputs/ENTRY9-OSS3-REGISTRATION-PR-INTAKE-20261010-CANDIDATE1-hyperresearch-codex-MAC-TEST-EVIDENCE/checkout`
- 보고 branch: mac-test/pr17-20261010-13ff98c7. 보고 커밋 parent는 tested code HEAD다. 보고 SHA는 원 task의 commit-readback.json에 기록한다.

## 실제 명령

| 명령 | exit | 관측 |
|---|---:|---|
| `git fetch origin refs/pull/17/head refs/heads/main` | 0 | ref 조회·갱신 |
| 독립 checkout `git checkout --detach 517efba1c33551656bfd7e58fd9f19632c421c07` | 0 | exact PR HEAD |
| `HPR_BACKEND=mock python3 hpr.py doctor` | 0 | CLI 버전 차이·PDF 모듈 없음 |
| `HPR_BACKEND=mock python3 -m unittest discover -s tests -p 'test*.py'` | 0 | 576개, 23.125초, failures0/errors0/skips0 |
| `HPR_BACKEND=mock python3 -m evals.run --min-total 97` | 0 | 32 case, 종합 평균100.0 |

PYTHONDONTWRITEBYTECODE=1도 적용했다. unittest의 BLOCKED·usage 오류·START real 문구는 모의 실패 경로 시험 출력이다. 실 Codex 영수증이 아니다. mock 토큰·가격도 모의값이다.

## CLOUD-NOTES 최신 명령 3줄 대조

1. fetch/checkout/doctor는 원 source 대신 같은origin 독립 PR HEAD에서 실행했다.
2. hpr.py run 실조사는 멈춤이다. original_test_budget.used=null/remaining=null/UNKNOWN과 실상한1을 보존했다. 공동 장부·dispatch·원 research manifest 메타에서 해당 호출 사용량을 증명할 영수증을 확보하지 못했다. 이번 일꾼의 호출 시작은 없음이며 누적 사용·잔여는 UNKNOWN이다.
3. 새 실제 report_marks가 없어 wording_conflict 실응답 오표시율도 UNKNOWN이다. 합성32 case 점수와 구분한다.

현재 CLI는 --max-calls1을 지원한다(cli.py238, pipeline.py178~189). _reserve_call은 lock 안에서 완료 사용량과 진행 예약을 합해 실패·재시도·병렬의 상한을 제한한다(pipeline.py246~257). codex_runner.py115~120은 codex exec -s read-only --output-schema를 구성한다. 이 경로의 기존 시험은 576개에 포함된다. doctor/mock은 실제 CLI 옵션 호환성·모델 응답·전체 다단계 E2E의 증거가 아니다.

## 인계와 한계

- 원 실호출 영수증을 먼저 확정해 상한1의 잔여를 확인한다. 결과 불명 재호출을 피한다.
- 실제 응답 fixture는 결과 없음이다. 기존 eval 사례 schema는 id/lang/baseline_time/prompt/flaws/sources/responses이고, 현재 사례는 합성 자료다. 실응답은 provenance·출처 링크·확인일·정답 검증 불확실성을 결속해야 한다.
- CI, Windows, Python3.11/3.12/3.13, wheel, 실PDF, 실응답 품질은 이번 결과 없음이다.
- same-PR-SHA Claude 감사는 결과 없음이다. 병합은 그 실제 PASS를 확인하는 별도 단계다.

## 자기 점검

| review1 필수 항목 | 자기 확인 |
|---|---|
| 명령·exit·시험 수 | 통과: raw log 대조 |
| exact tested SHA·보고 SHA 분리 | 통과: parent 및 commit readback |
| 코드·원 index 보존 | 통과: 문서 path-only 커밋·코드 SHA 재검산 |
| 원 실예산·UNKNOWN 보존 | 통과: 사용0으로 치환하지 않음 |
| mock·실품질·CI 구분 | 통과: 실제 명령 및 한계 문단 |
| 말투·AI 티 대조 | 통과: 과장·반복·방어용 면책 꼬리표 제외 |

이 자기 점검은 독립 review1 판정과 구분한다. 프로젝트 전용 STYLE-GUIDE는 찾지 못해 원 카드 필수 항목과 TEST-PLAN·VERIFICATION-BOUNDARIES를 적용했다.

읽은 교훈: [[코덱스 운영]]
적용: 모의 START와 실호출 영수증을 분리하고 원 source 파일 소유를 보존했다. 교훈 활용도·같은 원인 재발 수는 UNKNOWN이다.
