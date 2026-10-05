# 클라우드 회차 기록

최신 회차가 맨 위에 온다.

## 2026-10-05 (품질 회차 2)

- 점수 전후(`python -m evals.run`, 종합 평균, 12 case·강화 기준): **98.9 → 99.8**. 주장-출처 일치 93.4→99.0. (10 case 이전 끝 99.8, 새 case를 옛 기준으로 재면 99.8 — 맹점.) 상세는 `docs/QUALITY-LOG.md`.
- 한 일:
  - 평가 강화: 결함 case 2개(`ko-ev-charging`, `en-heat-pump`) — 원문의 계획·목표 수치를 실적처럼 씀, 시범·표본 결과를 전역 결과로 일반화. 점수기 주장-출처 일치에 두 검사 추가(기존 10 case 오탐 0). 추정치 유보 제거는 범위에서 빼고 이유 기록.
  - 개선: `verification`이 위 두 경우 인용 문장에 `(출처 불일치)` 표시(`plan_conflict`·`scope_conflict`). 기존 10 case 최종 보고서 변화 없음.
  - 백로그 1건: 출처끼리 반대 방향 결과를 한계 절이 다루지 않으면 상충 안내 `(판단)` 한 줄 추가(`note_source_conflicts`, `source_conflicts.json`). 점수기는 재지 않음. 새 백로그 3건(상충 case, 추정치 유보, 오표시율 실측). CHANGELOG `Unreleased` 한 줄.
- 돌린 시험: `HPR_BACKEND=mock python3 -m unittest discover -s tests -p 'test*.py'` → 529개 통과(Python 3.11, 새 시험 11개). `python -m evals.run --min-total 97` 통과. `compileall` 통과. `python -m evals.walkthrough examples/pipeline-walkthrough` 재생성 결과 변화 없음. 상충 안내는 임시 case로 실제 파이프라인을 돌려 한계 절 추가·`source_conflicts.json`·점수 무변화를 확인. 휠 빌드·3.12/3.13·Windows는 클라우드에서 돌리지 않음(CI는 푸시 후 확인 필요). 실제 `codex exec`는 로그인이 없어 돌리지 않음.
- PR #15(claude/cloud-work → main)를 열었다. CI 결과는 아직 확인하지 못했다. AGENTS.md의 커밋 댓글 규칙은 이 세션의 GitHub 도구에 커밋 댓글 기능이 없어 따르지 못했다. 대신 PR 본문과 이 기록에 남긴다.
- 남은 한계: 계획·범위 판정은 낱말 목록 근사(`will`·`expected`·`statewide` 등)라 실제 보고서에서 오표시·누락이 생길 수 있다. 수치 없는 일반화는 잡지 못한다.
- Mac에서 확인할 것:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && HPR_BACKEND=mock python -m evals.run --verbose
  hpr run "전기차 충전 인프라 확충 계획은 어디까지 왔나?"   # report_marks.json의 plan_conflict·scope_conflict 문장과 source_conflicts.json을 눈으로 판정
  ```

## 2026-10-05 (품질 회차)

- 점수 전후(`python -m evals.run`, 종합 평균, 10 case·강화 기준): **98.3 → 99.8**. 주장-출처 일치 95.1→98.8, 표시 없는 미검증 주장 97.3→100, 새 항목 본문 내부 일관성 97.3→100. (8 case 이전 끝 99.7은 새 기준에서도 99.7 — 오탐 0.) 상세는 `docs/QUALITY-LOG.md`.
- 한 일:
  - 평가 강화: 결함 case 2개(`ko-transit-pass`, `en-tree-canopy`) — 원문이 유보한 인과 단정, 판단 문장과 인용 문장의 반대 방향, 기간 단위 바꿔치기. 점수기에 인과·기간 검사와 "본문 내부 일관성" 항목 추가.
  - 개선: `verification.mark_report_claims`가 위 세 경우에 `(출처 불일치)`를 본문에 표시하고 `report_marks.json`에 `causal_conflict`·`period_conflict`·`internal_conflict`로 기록.
  - 백로그: 보고서 내부 모순 항목 완료 표시(인용 문장끼리 상충은 새 항목으로 분리), 인과 표시 범위 실측 항목 추가. CHANGELOG `Unreleased`에 한 줄 추가(백로그 'CHANGELOG와 다음 버전 준비'는 계속 진행 중).
- 돌린 시험: `HPR_BACKEND=mock python3 -m unittest discover -s tests -p 'test*.py'` → 514개 통과(Python 3.11, 새 시험 9개). `python -m evals.run --min-total 97` 통과. `compileall` 통과. `python -m evals.walkthrough examples/pipeline-walkthrough` 재생성 결과 변화 없음. 휠 빌드·3.12/3.13·Windows는 클라우드에서 돌리지 않음(CI는 푸시 후 확인 필요). 실제 `codex exec`는 로그인이 없어 돌리지 않음.
- PR #14(claude/cloud-work → main)를 열었다. CI 결과는 아직 확인하지 못했다. AGENTS.md의 커밋 댓글 규칙은 이 세션의 GitHub 도구에 커밋 댓글 기능이 없어 따르지 못했다. 대신 PR 본문과 이 기록에 남긴다.
- 남은 한계: 인과 표시는 원문이 명시적으로 유보할 때만 붙는다. 기간 낱말(`total`, `a day`, `하루`)과 반대 방향 판정은 낱말 근사라 실제 보고서에서 오표시가 생길 수 있다.
- Mac에서 확인할 것:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && HPR_BACKEND=mock python -m evals.run --verbose
  hpr run "청년 교통패스의 효과는?"   # 결과 폴더 report_marks.json의 causal_conflict·period_conflict·internal_conflict 문장이 실제로 틀린지 눈으로 판정
  ```

## 2026-10-04 (품질 회차 2)

- 점수 전후(`python -m evals.run`, 종합 평균, 8 case·강화 기준): **97.3 → 99.7**. 주장-출처 일치 87.9→98.4, 표시 없는 미검증 주장 없음 98.6→100. (이전 6 case·옛 기준 끝 점수는 99.2. 새 결함 case는 옛 점수기로 100점이라 기준을 강화했고 기존 case 점수는 변하지 않음.) 상세는 `docs/QUALITY-LOG.md`.
- 한 일:
  - 평가 강화: 결함 case 2개(`en-fare-free-bus`, `ko-heat-shelter`)와 점수기 방향·문맥·판단 남용 검사.
  - 개선 1: 원문과 반대 증감 방향, 다른 문맥에서 가져온 수치를 `(출처 불일치)`로, 출처에 없는 수치를 단정한 `(판단)` 문장을 `(출처 없음)`으로 본문 표시. `percent`↔`%` 정규화.
  - 개선 2: 복제 후보 출처를 겹쳐 인용하며 '독립 출처'라고 단정한 문장에 `(출처 불일치)`.
  - 백로그: 본문 표시 수를 `quality.json`의 `marks`, 머리 주석, `hpr status`에 노출. walkthrough 예시 재생성.
  - CI evals 하한 95→97. 시험 11개 추가.
- 돌린 시험: `HPR_BACKEND=mock python3 -m unittest discover -s tests -p 'test*.py'` → 503개 통과(Python 3.11). `python -m evals.run --min-total 97` 통과. `compileall` 통과. 휠 빌드·3.12/3.13·Windows는 클라우드에서 돌리지 않음(CI는 푸시 후 확인 필요). 실제 `codex exec`는 로그인이 없어 돌리지 않음.
- 남은 한계: 새 표시는 낱말 목록 근사라 실제 보고서에서 오표시가 생길 수 있다(특히 'lower'·'낮아' 같은 형용사 용법, 긴 문장의 여러 수치). 실측 전에는 표시 수를 품질 지표로 쓰지 말 것.
- Mac에서 확인할 것:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && HPR_BACKEND=mock python -m evals.run --verbose
  hpr run "무더위 쉼터 운영의 효과는?" && hpr status   # quality 옆 (출처 없음 N·출처 불일치 M) 확인
  # 결과 폴더 report_marks.json의 direction_conflict·context_conflict·independence_conflict 문장이 실제로 틀린 문장인지 눈으로 확인
  ```

## 2026-10-04 (품질 회차)

- 점수 전후(`python -m evals.run`, 종합 평균): **95.6 → 99.2**. 주장-출처 일치 90.4→95.8, 표시 없는 미검증 주장 없음 90.6→100, 보고서 구조 97.2→100. 상세는 `docs/QUALITY-LOG.md`.
- 한 일:
  - 개선 1 `verification.mark_report_claims`: 인용 원문에 없는 수치·날짜를 문장에 `(출처 불일치)`로, 답·근거·한계 절의 인용 없는 사실 문장을 `(출처 없음)`으로 직접 표시(수정·다듬기 직후, 인용 검사 전). 인용 없는 문장 표시가 있으면 review_required.
  - 개선 2 `gates.fill_empty_limits`: 빈 한계 절을 분석 단계의 상충·빈틈으로 `(판단)` 표시해 채우고, 없으면 검토 필요를 명시.
  - CI evals 하한 90→95. 시험 12개 추가(`tests/test_report_marks.py`, `tests/test_fill_limits.py`). CHANGELOG `Unreleased` 정리.
  - 백로그: 공개 전 점검 보고(`docs/PUBLIC-CHECK-20261004.md`, 지운 것 없음). 품질 3건 완료 표시, 새 항목 3건 근거와 함께 추가.
- 돌린 시험: `HPR_BACKEND=mock python3 -m unittest discover -s tests -p 'test*.py'` → 492개 통과(Python 3.11). `python -m evals.run --min-total 95` 통과. `compileall` 통과. `python -m evals.walkthrough examples/pipeline-walkthrough` 재생성 결과 변화 없음. 휠 빌드·3.12/3.13·Windows는 클라우드에서 돌리지 않음(CI 결과는 푸시 후 확인 필요). 실제 `codex exec`는 로그인이 없어 돌리지 않음.
- 남은 한계: 고정 6개 case가 99.2로 포화돼 다음 개선을 구분하지 못한다(결함 case 추가가 백로그 맨 위 후보). `(출처 없음)` 자동 표시는 실제 codex 보고서에서 너무 많이 붙을 수 있다 — 문장 수와 review_required 비율을 실측해야 한다.
- Mac에서 확인할 것:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && HPR_BACKEND=mock python -m evals.run --verbose
  hpr run "보호 자전거 차로의 효과는?"   # 결과 폴더의 report_marks.json·limits_filled.json과 final_report.md의 (출처 없음)·(출처 불일치) 개수 확인
  ```

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
