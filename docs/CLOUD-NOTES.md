# 클라우드 회차 기록

최신 회차가 맨 위에 온다.

## 2026-10-03 (품질 회차)

- 점수 전후(`python -m evals.run`, 종합 평균): **76.0 → 95.6**. 인용 유효성 83.3→100, 주장-출처 일치 73.8→90.4, 중복 출처 없음 68.3→100, 표시 없는 미검증 주장 없음 73.9→90.6, 보고서 구조 80.5→97.2. 상세는 `docs/QUALITY-LOG.md`.
- 한 일:
  - `evals/` 신설: 고정 질문 6개(한 3·영 3)를 실제 파이프라인 고정 입력 재생 모드로 돌리고 기록된 가짜 작성자 응답으로 최종 보고서를 5개 항목 채점. CI(`tests.yml`)에 `python -m evals.run --min-total 90` 추가, `tests/test_evals.py` 15개.
  - 개선 1: 초안의 없는 출처 인용 하나로 실행 전체가 `초안 게이트 실패`로 멈추던 것을, 인용을 지우고 `(출처 없음)` 표시 후 계속 + 검증 상태 review_required로 바꿈(`gates.drop_unknown_cites`).
  - 개선 2: 중복 후보 출처의 겹침 인용 `[S1][S3]` 정리 — 정본 URL이 같으면 대표 출처로 줄이고, 본문 유사도로만 묶였으면 인용은 두고 '독립 출처가 아닐 수 있음' 표시. 출처 목록 중복 행 제거(`gates.collapse_duplicate_sources`, 인용 검사 전). PR #11 Codex 리뷰 지적 3건(유사도 묶음을 복제본으로 단정, 혼합 출처 행의 없는 별칭, 인용 검사 뒤 수정)을 반영.
  - 백로그: `examples/pipeline-walkthrough/` 단계별 산출물 예시와 `python -m evals.walkthrough`. 품질 백로그 4건 근거와 함께 추가.
  - 점수기 기준 변경 1건(출처 주석을 주장 내용에서 제외)과 그 영향 없음 확인을 QUALITY-LOG에 적음.
- 돌린 시험: `HPR_BACKEND=mock python3 -m unittest discover -s tests -p 'test*.py'` → 478개 통과(Python 3.11). `python -m evals.run --min-total 90` 통과. `compileall` 통과. 휠 빌드·Windows 작업은 클라우드에서 돌리지 않음(CI 결과 미확인). 실제 `codex exec`는 로그인이 없어 돌리지 않음.
- 남은 한계: 평가 응답 픽스처는 손으로 쓴 결함 사례라 실제 모델 출력 분포와 다르다. 개선 1은 hard 게이트를 완화한 것이라 실제 codex 초안에서 `(출처 없음)` 문장이 얼마나 생기는지 확인이 필요하다.
- Mac에서 확인할 것:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && HPR_BACKEND=mock python -m evals.run --verbose
  hpr run "보호 자전거 차로의 효과는?" --dry-run && hpr run "보호 자전거 차로의 효과는?"   # 결과의 draft_gate.json·검증 상태 확인
  ```

## 2026-10-03

- 한 일: 공개 저장소 기본 문서 점검. LICENSE(MIT)와 `pyproject.toml` 라이선스 표기는 일치. SECURITY.md의 지원 버전이 `0.4.x`로 남아 있어 현재 `0.5.x`로 고침. 이슈 생성 화면에서 보안 신고를 비공개 advisory로 안내하는 `.github/ISSUE_TEMPLATE/config.yml` 추가. PR 템플릿의 시험 항목을 CONTRIBUTING과 같은 전체 mock 묶음 명령으로 맞춤. tester-feedback 템플릿 버전 예시 0.3.1→0.5.0.
- 돌린 시험: `HPR_BACKEND=mock python3 -m unittest discover -s tests -p 'test*.py'` → 463개 통과(Python 3.11, 클라우드). `compileall` 통과, 이슈 템플릿 YAML 파싱 확인. 실제 `codex exec` 조사는 로그인이 없어 돌리지 않음.
- 남은 한계: 이슈 템플릿의 `feedback` 라벨이 저장소에 실제로 있는지는 확인하지 않음. CI 결과는 푸시 직후라 미확인.
- Mac에서 확인할 것:
  ```bash
  git fetch origin claude/cloud-work && git diff main...origin/claude/cloud-work -- SECURITY.md .github/
  # GitHub에서 New issue 화면에 "Security vulnerability" 링크가 보이는지 확인
  ```

## 2026-10-02

- 한 일: `docs/CLOUD-BACKLOG.md` 생성. README.md에 "At a glance", README.ko.md에 "한눈에 보기" 절 추가(한 줄 설명·설치 3줄·첫 실행·실측 예시 보고서 발췌). 시험·CI 항목은 기존 463개 mock 시험과 `tests.yml`로 이미 충족됨을 확인하고 표시만 바꿈.
- 돌린 시험: `python3 -m unittest discover -s tests` → 463개 통과(Python 3.11, 클라우드, 모델·네트워크 호출 없음). 실제 `codex exec` 조사는 로그인이 없어 돌리지 않음.
- 남은 한계: CI(tests run 46)는 푸시 시점에 대기 중이라 결과 미확인. AGENTS.md의 커밋 댓글 규칙은 이 클라우드 세션의 GitHub 도구에 커밋 댓글 기능이 없어 이행하지 못했다. 이 기록으로 대신한다.
- Mac에서 확인할 것:
  ```bash
  git fetch origin claude/cloud-work && git diff main...origin/claude/cloud-work -- README.md README.ko.md
  hpr doctor && hpr run "테스트 질문" --dry-run
  ```
