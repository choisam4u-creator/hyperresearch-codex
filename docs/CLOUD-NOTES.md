# 클라우드 회차 기록

최신 회차가 맨 위에 온다.

## 2026-10-10 (품질 회차 6)

- 점수 전후: 코드 수정 전에 만든 새 holdout2 라벨 평가(`python -m evals.labeled --set holdout2`, 12 case·136문장) **F1 59.5 → 80.9**(recall 50.0→80.3, precision 73.3→81.5, 맞는 문장 오표시율 17.1 그대로, 못 찾은 문장 2→0). 설계 때 보지 않은 묶음: dev 82.9→88.4, 5회차 holdout 73.4→80.0(둘 다 오표시율 그대로). 고정 32 case(`evals.run`) 100.0 그대로. 상세는 `docs/QUALITY-LOG.md`.
- 한 일(항목마다 커밋·푸시):
  - 코드 수정 전 먼저: 기존과 겹치지 않는 holdout2 case 12개(범위 과장 11·부정·유보 뒤집기 15·인과 역전 5·방향 9·단위 9, 동의어 맞는 문장 33·반올림·계산 값 26·단위 환산 3)와 `--set holdout2`(`4f263eb`).
  - 개선 1 전체 범위 단정 `_universal_overclaim`(범위 과장 0/11→11/11). 개선 2 효과 동사 인과 단정·유보 표현 확장과 무변화·비유의 뒤집기 `_null_result_flip`(부정 5/15→13/15). 개선 3 'a.m.' 등 약어 마침표에서 문장을 끊어 본문이 깨지던 결함. 시험 3개(모두 옛 코드에서 실패 확인).
  - 백로그: holdout 새로 만들기 항목 완료, 부정 항목 진행 기록, 새 항목 4건(사람 검토·오표시 17.1·단위 차원·시간 순서 역전). CI에 holdout2 `--min-f1 75`. CHANGELOG·evals README.
- 돌린 시험: `HPR_BACKEND=mock python3 -m unittest discover -s tests -p 'test*.py'` → 590개 통과(Python 3.11; `httpx`·`pypdf`·`cffi`를 따로 설치). `evals.run`(100.0)·`evals.labeled`(dev 88.4, holdout 80.0, holdout2 80.9)·`compileall` 통과, walkthrough 재생성 변화 없음. 3.12/3.13·Windows·휠 빌드와 실제 `codex exec`는 돌리지 않았다.
- 한계: holdout2도 이 세션이 쓰고 라벨을 달았고, 개선 1·2는 holdout2 기준선 오판을 본 뒤 만들었다(효과 동사 낱말 공유 문턱은 holdout2 두 문장을 보고 2→1로 낮춤) — holdout2 끝 점수는 과대평가이고 dev·holdout 상승이 덜 편향된 근거다. 맞는 문장 오표시율 17.1(단위 환산·곱·배수)은 이번에 손대지 않았다. 커밋 댓글 규칙은 이 세션 GitHub 도구에 커밋 댓글 기능이 없어 PR 본문·이 기록으로 대신한다. CI 결과는 푸시 직후라 확인하지 못했다.
- Mac에서 실제 codex로 확인할 명령 3줄:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && python3 hpr.py doctor
  python3 hpr.py run "LED 가로등 교체는 전력 사용과 야간 범죄를 줄였나? 근거와 한계를 밝혀라"
  grep -h '"scope_conflict"\|"causal_conflict"\|"negation_conflict"' -A6 research/runs/*/report_marks.json   # 표시 문장을 원문과 대조해 오표시를 센다
  ```

## 2026-10-10 (품질 회차 5)

- 점수 전후: 코드 수정 전에 만든 새 holdout 라벨 평가(`python -m evals.labeled --set holdout`, 12 case·127문장) **F1 60.9 → 73.4**(recall 56.5→64.5, precision 66.0→85.1, 맞는 문장 오표시율 27.7→10.8). dev 108문장 81.0→82.9(오표시율 6.5→3.2). 고정 32 case(`evals.run`) 100.0 그대로. 상세는 `docs/QUALITY-LOG.md`.
- 한 일(항목마다 커밋·푸시):
  - 코드 수정 전 먼저: 기존과 겹치지 않는 holdout case 12개(부정 13·인과 역전 5·방향 5·범위 9·단위 7, 동의어 맞는 문장 25·반올림·계산 값 26)와 `--set dev|holdout|all`(`406d0f3`). 기준선이 4회차 끝 점수(81.0)의 과적합을 드러냄(60.9).
  - 개선 1 계산 값 인정(나눗셈·%p 차·하한·몫 반올림·연간 환산·낱말 몫, "1만 2,400"·Mbps 읽기). 개선 2 반대말 뒤집기 `antonym_conflict`·인과 역전 `causal_reversal_conflict`(dev로 설계 뒤 holdout 한 번 측정). 시험 각 1개(옛 코드에서 실패 확인).
  - 백로그: 맞는 문장 오표시 2건(“9~10월”, 천 단위 쉼표에서 절을 끊던 결함) 수정, 인과 역전 항목 완료, 새 항목 4건. CI에 holdout 라벨 평가(`--min-f1 70`). CHANGELOG·evals README.
- 돌린 시험: `HPR_BACKEND=mock python3 -m unittest discover -s tests -p 'test*.py'` → 587개 통과(Python 3.11; `httpx`·`pypdf`·`cffi`를 따로 설치). `evals.run`(100.0)·`evals.labeled`(dev `--min-f1 75`, holdout `--min-f1 70`)·`compileall` 통과, walkthrough 재생성 변화 없음. 3.12/3.13·Windows·휠 빌드와 실제 `codex exec`는 돌리지 않았다.
- 한계: 개선 1은 holdout 오표시 문장을 보며 만들어 holdout 오표시율 개선은 독립 측정이 아니다(개선 2만 설계 뒤 한 번 잼). holdout도 이 세션이 쓰고 라벨을 달았다(사람 검토 전). 다음 회차는 이번 코드를 보지 않은 새 holdout이나 실제 codex 보고서 라벨로 다시 재야 한다. 커밋 댓글 규칙은 이 세션 GitHub 도구에 커밋 댓글 기능이 없어 PR 본문·이 기록으로 대신한다. CI 결과는 푸시 직후라 확인하지 못했다.
- Mac에서 실제 codex로 확인할 명령 3줄:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && python3 hpr.py doctor
  python3 hpr.py run "주 4일 수업제는 교사 채용과 학생 성적에 어떤 변화를 냈나? 근거와 한계를 밝혀라"
  grep -h '"antonym_conflict"\|"causal_reversal_conflict"' -A6 research/runs/*/report_marks.json   # 표시 문장을 원문과 대조해 오표시를 센다
  ```

## 2026-10-10 (품질 회차 4)

- 점수 전후: 새 사람 라벨 대조 평가(`python -m evals.labeled`, 12 case·108문장) **F1 44.7 → 81.0**(recall 41.3→73.9, precision 48.7→89.5, 맞는 문장 오표시율 32.3→6.5). 고정 32 case(`evals.run`)는 전후 100.0 그대로. 상세는 `docs/QUALITY-LOG.md`.
- 한 일(항목마다 커밋·푸시):
  - 코드 수정 전 먼저: 기존과 겹치지 않는 라벨 case 12개(부정 뒤집기·인과 역전·범위 과장·동의어 바꿔 말하기·반올림·단위 환산)와 라벨 대조 점수기 `evals/labeled.py`(`cae7ad1`).
  - 개선 1 단위 환산(톤·킬로그램·마일·킬로미터, 하이픈 단위), 개선 2 어림·계산 값 인정(오표시 대폭 감소), 개선 3 부정 뒤집기 `negation_conflict`, 개선 4 몫 과장 `share_conflict`. 시험 4개(모두 옛 코드에서 실패 확인).
  - 백로그: 라벨 평가 항목 완료로 추가, CI에 `evals.labeled --min-f1 75`. CHANGELOG·evals README.
- 돌린 시험: `HPR_BACKEND=mock python3 -m unittest discover -s tests -p 'test*.py'` → 584개 통과(Python 3.11; `pip install -e .`이 이 컨테이너에서 의존성을 깔지 못해 `httpx`·`pypdf`·`cffi`를 따로 설치). `evals.run`(100.0)·`evals.labeled --min-f1 75`·`compileall` 통과, walkthrough 재생성 변화 없음. 3.12/3.13·Windows·휠 빌드와 실제 `codex exec`는 돌리지 않았다.
- 한계: 라벨은 이 클라우드 세션이 달았고 사람 검토 전이다. 부정·몫 문턱은 이 108문장을 본 뒤 정해 끝 점수에 과적합 몫이 있다 — 다음 회차는 새 라벨 case로 다시 잰다. 인과 역전은 0/4 그대로. AGENTS.md의 커밋 댓글 규칙은 이 세션 GitHub 도구에 커밋 댓글 기능이 없어 따르지 못했고 PR 본문·이 기록에 남긴다. CI 결과는 푸시 직후라 확인하지 못했다.
- Mac에서 실제 codex로 확인할 명령 3줄:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && python3 hpr.py doctor
  python3 hpr.py run "방과후 수학교실은 참여 학생의 수학 점수를 올렸나? 근거와 한계를 밝혀라"
  grep -h '"negation_conflict"\|"share_conflict"' -A6 research/runs/*/report_marks.json   # 표시 문장을 원문과 눈으로 대조해 오표시를 센다
  ```

## 2026-10-09 (품질 회차 3)

- 점수 전후(`python -m evals.run`, 종합 평균, 32 case·강화 기준): **99.7 → 100.0**. 주장-출처 일치 98.1→100, 잘못 붙은 경고 없음 99.6→100. (30 case 이전 끝 99.9, 새 case를 옛 기준으로 재면 99.8 — 영어 쪽 맹점.) 상세는 `docs/QUALITY-LOG.md`.
- 한 일(항목마다 커밋·푸시):
  - 평가 강화: 결함 case 2개(`ko-school-zone-camera`, `en-noise-barrier`) — 수치 없이 원문에 없는 추론·사실을 인용만 달아 씀. 점수기 `wording_unsupported`(영어 내용 낱말 절반 이상이 원문에 있어야 함). 기존 30 case 오탐 0.
  - 개선 1: `verification._wording_unsupported` → 인용 문장에 `(출처 불일치)`(`wording_conflict`). 같은 문자 체계만, 출처 틀 낱말은 뺌, 다음 행동 절 제외. 남아 있던 ko-cooling-pilot 감점도 해소.
  - 개선 2: 새 case가 드러낸 `_subject_swap` 오표시 수정(영어 단수·복수, 세는 낱말이 다른 단위 없는 수치).
  - 백로그·CHANGELOG·`evals/README.md`(case 수 28→32로 바로잡음, 기준 설명).
- 돌린 시험: `HPR_BACKEND=mock python3 -m unittest discover -s tests -p 'test*.py'` → 576개 통과(Python 3.13, 새 시험 3개 — 코드 시험 2개는 옛 코드에서 실패 확인, `httpx` 등은 `pip install -e .`로 설치 필요했음). `python -m evals.run --min-total 97`·`compileall` 통과. walkthrough 재생성 결과 변화 없음. 3.11/3.12·Windows·휠 빌드는 클라우드에서 돌리지 않았다. 실제 `codex exec`는 로그인이 없어 돌리지 않았다.
- PR #17(claude/cloud-work → main)에 이어 푸시하고 PR 본문에 이번 회차 표를 더한다. CI 결과는 푸시 직후라 확인하지 못했다. AGENTS.md의 커밋 댓글 규칙은 이 세션의 GitHub 도구에 커밋 댓글 기능이 없어 따르지 못했고, 대신 PR 본문과 이 기록에 남긴다.
- 남은 한계: 문턱 0.4는 새 case를 본 뒤 정했다. 원문을 많이 바꿔 말한 맞는 문장에 오표시가 생길 수 있고, 원문 낱말을 그대로 쓰며 뜻만 뒤집은 추론은 잡지 못한다. 32 case 모두 100점이라 다음 회차는 실제 codex 픽스처나 새 결함 유형이 먼저다.
- Mac에서 실제 codex로 확인할 명령 3줄:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && python3 hpr.py doctor
  python3 hpr.py run "어린이보호구역 과속 단속카메라는 사고를 줄였나? 근거와 한계를 밝혀라"
  grep -h '"wording_conflict"' -A6 research/runs/*/report_marks.json   # 표시된 문장을 원문과 눈으로 대조해 오표시를 센다
  ```

## 2026-10-09 (품질 회차 2)

- 점수 전후(`python -m evals.run`, 종합 평균, 30 case·강화 기준): **99.7 → 99.9**. 주장-출처 일치 97.7→99.6. (28 case 이전 끝 99.9, 새 case를 옛 기준으로 재면 99.9 — 맹점.) 상세는 `docs/QUALITY-LOG.md`.
- 한 일:
  - 평가 강화: 결함 case 2개(`ko-ebus-subsidy`, `en-school-tech-grant`) — 원문의 대당·학교당·평균 값을 총계로, 또는 다른 단위당 기준으로 바꿔 씀. 점수기 `basis_mismatch`에 site·vehicle·school·average 기준 추가(평균은 단위당 값과 맞고 총계와만 어긋남). 노트 머리 "S2"의 2가 판정을 끄던 점수기 결함 수정. 기존 28 case 오탐 0.
  - 개선: `verification._BASIS_WORDS`·`_bases_agree` → 인용 문장에 `(출처 불일치)`(`basis_conflict`). 새 시험이 드러낸 오표시("충전소 1곳당"의 1을 수량으로 읽음) 수정. 기존 28 case 최종 보고서 diff 없음.
  - 백로그: 곳당·대당·평균 항목 완료, 새 항목 1건(평균 기준 오표시율·subject/basis 겹침 실측). CHANGELOG `Unreleased` 한 줄, `evals/README.md` 기준 설명.
- 돌린 시험: `HPR_BACKEND=mock python3 -m unittest discover -s tests -p 'test*.py'` → 573개 통과(시스템 Python 3.11, 새 시험 2개 — 둘 다 옛 코드·옛 점수기에서 실패 확인, `httpx`는 설치 필요했음). `python -m evals.run --min-total 97`·`compileall` 통과. walkthrough 재생성 결과 변화 없음. 3.12/3.13·Windows·휠 빌드는 클라우드에서 돌리지 않았다. 실제 `codex exec`는 로그인이 없어 돌리지 않았다.
- PR #17(claude/cloud-work → main)에 이어 푸시하고 PR 본문에 이번 회차 표를 더한다. CI 결과는 푸시 직후라 확인하지 못했다. AGENTS.md의 커밋 댓글 규칙은 이 세션의 GitHub 도구에 커밋 댓글 기능이 없어 따르지 못했고, 대신 PR 본문과 이 기록에 남긴다.
- 남은 한계: `평균`·`average`는 총계와 대비되지 않는 뜻으로도 쓰여 오표시 가능. 한 절에 기준 낱말이 둘이면 가장 가까운 것 하나로만 판정.
- Mac에서 확인할 것:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && HPR_BACKEND=mock python -m evals.run --verbose
  hpr run "전기버스 보조금과 충전소 설치비는 얼마였나?"   # report_marks.json의 basis_conflict 문장(특히 '평균')을 원문과 눈으로 대조
  ```

## 2026-10-09 (품질 회차)

- 점수 전후(`python -m evals.run`, 종합 평균, 28 case·강화 기준): **99.6 → 99.9**. 주장-출처 일치 97.9→99.6, 잘못 붙은 경고 없음 99.6→100. (26 case 이전 끝 99.9, 새 case를 옛 기준으로 재면 99.9 — 맹점.) 상세는 `docs/QUALITY-LOG.md`.
- 한 일:
  - 평가 강화: 결함 case 2개(`ko-youth-allowance`, `en-utility-rebate`) — 원문의 1인당·가구당 값을 총계로, 또는 1인당↔가구당으로 바꿔 씀. 점수기 `basis_mismatch` 추가(기존 26 case 오탐 0).
  - 개선: `verification._basis_conflict` → 인용 문장에 `(출처 불일치)`, `report_marks.json`의 `basis_conflict`. 새 case가 드러낸 옛 코드 오표시 1건(`_subject_swap`이 앞 절 주제어가 생략된 맞는 인용 "사업비는 총 36억 원"을 표시) 수정, "1인당"의 1을 수량으로 읽지 않게 함. 기존 26 case 최종 보고서 diff 없음.
  - 백로그: 1인당↔총계 항목 완료. 새 항목 2건(기준 판정 오표시율 실측, 곳당·대당·평균 확장). CHANGELOG `Unreleased` 한 줄.
- 돌린 시험: `HPR_BACKEND=mock python3 -m unittest discover -s tests -p 'test*.py'` → 571개 통과(시스템 Python 3.11, 새 시험 2개 — 둘 다 옛 코드·옛 점수기에서 실패 확인, `httpx`는 설치 필요했음). `python -m evals.run --min-total 97`·`compileall` 통과. walkthrough 재생성 결과 변화 없음. 3.12/3.13·Windows·휠 빌드는 클라우드에서 돌리지 않았다. 실제 `codex exec`는 로그인이 없어 돌리지 않았다.
- PR #17(claude/cloud-work → main)에 이어 푸시하고 PR 본문에 이번 회차 표를 더한다. CI 결과는 푸시 직후라 확인하지 못했다. AGENTS.md의 커밋 댓글 규칙은 이 세션의 GitHub 도구에 커밋 댓글 기능이 없어 따르지 못했고, 대신 PR 본문과 이 기록에 남긴다.
- 남은 한계: 기준 낱말은 절 안 가장 가까운 것 하나로 근사("1인당 20만 원씩 총 1,200명"처럼 한 절에 기준이 둘이면 오판 가능). 곳당·대당·평균은 아직 안 본다.
- Mac에서 확인할 것:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && HPR_BACKEND=mock python -m evals.run --verbose
  hpr run "청년 정착 지원금과 에너지 바우처는 누구에게 얼마씩 지급됐나?"   # report_marks.json의 basis_conflict·subject_conflict 문장을 원문과 눈으로 대조
  ```

## 2026-10-08 (품질 회차 2)

- 점수 전후(`python -m evals.run`, 종합 평균, 26 case·강화 기준): **99.6 → 99.9**. 주장-출처 일치 97.3→99.5. (24 case 이전 끝 99.9, 새 case를 옛 기준으로 재면 99.9 — 맹점.) 상세는 `docs/QUALITY-LOG.md`.
- 한 일:
  - 평가 강화: 결함 case 2개(`ko-night-bus`, `en-water-meters`) — 원문에 나란히 나오는 두 대상 중 한 대상의 수치를 다른 대상의 값으로 옮김(심야버스 18%→지하철 막차, household 9%→commercial). 점수기 `subject_swapped` 추가(기존 24 case 오탐 0, 처음 오탐 4건은 대상 낱말 근사를 고쳐 없앰).
  - 개선: `verification._subject_swap` → 인용 문장에 `(출처 불일치)`, `report_marks.json`의 `subject_conflict`. 첫 구현의 오표시 1건(ko-ev-charging "18분에서 11분으로")을 '잘못 붙은 경고 없음' 항목이 잡아 고침. 기존 24 case 최종 보고서 diff 없음.
  - 백로그 1건: 하한 표시 강도 검토 → 강한 표시 유지, 그 과정에서 세는 말 뒤 하한("300가구 이상")을 코드가 못 읽던 결함 수정. 새 백로그 2건(대상 바꿈 오표시율 실측, 1인당↔총계 바꿈 — 지금 점수기·코드 모두 통과시킴). CHANGELOG `Unreleased` 한 줄.
- 돌린 시험: `HPR_BACKEND=mock python3 -m unittest discover -s tests -p 'test*.py'` → 569개 통과(시스템 Python 3.11, 새 시험 3개 — 모두 옛 코드·옛 점수기에서 실패 확인, `httpx`는 설치 필요했음). `python -m evals.run --min-total 97`·`compileall` 통과. walkthrough 재생성 결과 변화 없음. 3.12/3.13·Windows·휠 빌드는 클라우드에서 돌리지 않았다. 실제 `codex exec`는 로그인이 없어 돌리지 않았다.
- PR #17(claude/cloud-work → main)에 이어 푸시하고 PR 본문에 이번 회차 표를 더한다. CI 결과는 푸시 직후라 확인하지 못했다. AGENTS.md의 커밋 댓글 규칙은 이 세션의 GitHub 도구에 커밋 댓글 기능이 없어 따르지 못했고, 대신 PR 본문과 이 기록에 남긴다.
- 남은 한계: 대상 낱말은 "앞 수치 뒤부터 그 수치까지" 위치 근사라 대상이 수치 뒤에 오거나 생략된 문장, 동의어로 바꾼 대상은 놓친다.
- Mac에서 확인할 것:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && HPR_BACKEND=mock python -m evals.run --verbose
  hpr run "심야버스 노선 확대 뒤 심야 교통 이용과 시민 만족도는 어떻게 바뀌었나?"   # report_marks.json의 subject_conflict 문장이 실제로 다른 대상의 수치인지 눈으로 판정
  ```

## 2026-10-08 (품질 회차)

- 점수 전후(`python -m evals.run`, 종합 평균, 24 case·강화 기준): **99.6 → 99.9**. 주장-출처 일치 97.2→99.5. (22 case 이전 끝 99.9, 새 case를 옛 기준으로 재면 99.9 — 맹점.) 상세는 `docs/QUALITY-LOG.md`.
- 한 일:
  - 평가 강화: 결함 case 2개(`ko-insulation-retrofit`, `en-congestion-charge`) — 원문의 상한("최대 30%"·"up to 25 percent")과 범위 끝값("10~20%"·"between 8 and 12 percent")을 대표값처럼 씀. 변화 전후 값("from 9,000 to 14,000")은 맞는 문장으로 넣어 오탐 확인. 점수기 `bound_dropped` 추가(기존 22 case 오탐 0).
  - 개선: `verification._bound_overclaim` → 인용 문장에 `(출처 불일치)`, `report_marks.json`의 `bound_conflict`. 기존 22 case 최종 보고서 diff 없음.
  - 백로그 1건: '잘못 붙은 경고 없음'을 인용 없는·판단 문장의 `(출처 불일치)`·`(출처 없음)`까지 확장(분모를 절 문장 전체로). 새 백로그 2건(상한 판정 오표시율 실측, 하한 표시 강도). CHANGELOG `Unreleased` 한 줄.
- 돌린 시험: `HPR_BACKEND=mock python3 -m unittest discover -s tests -p 'test*.py'` → 566개 통과(시스템 Python 3.11, 새 시험 2개 — 둘 다 옛 코드·옛 점수기에서 실패 확인, `httpx`는 설치 필요했음). `python -m evals.run --min-total 97`·`compileall` 통과. walkthrough 재생성 결과 변화 없음. 3.12/3.13·Windows·휠 빌드는 클라우드에서 돌리지 않았다. 실제 `codex exec`는 로그인이 없어 돌리지 않았다.
- PR #17(claude/cloud-work → main)이 아직 열려 있어 같은 브랜치에 이어 푸시하고 PR 본문에 이번 회차 표를 더했다. CI 결과는 푸시 직후라 확인하지 못했다. AGENTS.md의 커밋 댓글 규칙은 이 세션의 GitHub 도구에 커밋 댓글 기능이 없어 따르지 못했고, 대신 PR 본문과 이 기록에 남긴다.
- 남은 한계: 상한·범위 판정은 낱말·기호 근사(`over`·`under`·`-`)다. 하한을 뗀 과소 진술도 강한 표시를 받는다.
- Mac에서 확인할 것:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && HPR_BACKEND=mock python -m evals.run --verbose
  hpr run "혼잡통행료 도입 뒤 도심 교통량과 대기오염은 얼마나 줄었나?"   # report_marks.json의 bound_conflict 문장이 실제로 원문 상한·범위 끝값인지 눈으로 판정
  ```

## 2026-10-07 (품질 회차 2)

- 점수 전후(`python -m evals.run`, 종합 평균, 22 case·7항목 기준): **99.3 → 99.9**. 새 항목 잘못 붙은 경고 없음 95.5→100. (20 case·6항목 이전 끝 99.9, 새 항목만 더하면 99.9, 새 case를 옛 표기 점수기로 재면 99.8 — 맹점.) 상세는 `docs/QUALITY-LOG.md`.
- 한 일:
  - 평가 강화: 새 항목 **잘못 붙은 경고 없음** — 표시를 떼도 점수기 대조를 통과하는 인용 문장에 `(출처 불일치)`·`(원문 추정치)`가 붙으면 감점(경고를 남발해도 주장-출처 일치가 오르던 맹점). 지난 회차 개선 전 코드를 이 항목으로 재면 97.8.
  - 평가 강화: case 2개(`en-port-dredging`, `ko-library-budget`) — 자릿수 약어($3.8M·2.5bn·12k)와 한국어 복합 표기(1억 2천만·4천5백만·3만 5천). 점수기가 이 표기를 값으로 읽는다(같은 값은 일치 — 넓히는 쪽, 이유는 QUALITY-LOG).
  - 개선: `verification._quantity_values`가 약어·복합 표기를 한 값으로 읽는다. 옛 코드가 맞는 환산 4문장에 붙이던 `(출처 불일치)` 제거, 바꾼 2문장은 정확한 값으로 표시. 기존 20 case 최종 보고서 diff 없음.
  - 백로그 1건 완료(약어·복합 표기), 새 항목 2건(약어 오인 실측, 경고 정확도 범위를 판단·출처 없음 표시로 확장). CHANGELOG `Unreleased` 한 줄.
- 돌린 시험: `HPR_BACKEND=mock python3 -m unittest discover -s tests -p 'test*.py'` → 564개 통과(시스템 Python 3.11, 새 시험 4개 — 코드 시험 2개는 옛 코드에서 실패 확인, `httpx`는 설치 필요했음). `python -m evals.run --min-total 97`·`compileall` 통과. walkthrough 재생성 결과 변화 없음. 3.12/3.13·Windows·휠 빌드는 클라우드에서 돌리지 않았다. 실제 `codex exec`는 로그인이 없어 돌리지 않았다.
- PR #17(claude/cloud-work → main)이 아직 열려 있어 같은 브랜치에 이어 푸시하고 PR 본문에 이번 회차 표를 더했다. CI 결과는 푸시 직후라 확인하지 못했다. AGENTS.md의 커밋 댓글 규칙은 이 세션의 GitHub 도구에 커밋 댓글 기능이 없어 따르지 못했고, 대신 PR 본문과 이 기록에 남긴다.
- 남은 한계: 숫자에 붙은 대문자 M·B·K는 자릿수로 읽어 제품명 같은 드문 표기를 오인할 수 있다. 새 항목은 인용 문장의 경고만 본다.
- Mac에서 확인할 것:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && HPR_BACKEND=mock python -m evals.run --verbose
  hpr run "항만 준설 사업비와 연방 분담금은 얼마였나?"   # report_marks.json의 mismatch에 $3.8M·1억 2천만 같은 맞는 환산이 들어가지 않았는지 눈으로 판정
  ```

## 2026-10-07 (품질 회차)

- 점수 전후(`python -m evals.run`, 종합 평균, 20 case·강화 기준): **99.1 → 99.9**. 주장-출처 일치 94.9→99.4. (18 case 이전 끝 99.9, 새 case를 옛 기준으로 재면 99.9 — 맹점.) 상세는 `docs/QUALITY-LOG.md`.
- 한 일:
  - 평가 강화: 결함 case 2개(`ko-sewer-upgrade`, `en-bus-grant`) — 숫자는 같고 자릿수 낱말만 바꿈("420억 원"→"420만 원", "4.2 million"→"4.2 billion"). 점수기가 수치를 숫자×자릿수로 비교(같은 값의 다른 표기는 인정 — 넓히는 쪽이라 이유를 QUALITY-LOG에 적음, 기존 18 case 점수 변화 없음).
  - 개선: `verification._quantity_values`가 천·만·억·조·thousand·million·billion·trillion을 값에 곱한다. 바꿔치기 4문장에 `(출처 불일치)`, 옛 코드가 맞는 환산 2문장("120,000가구", "1,600,000 trips")에 붙이던 오표시 제거. 기존 18 case 최종 보고서 diff 없음.
  - 백로그 1건: ko-cooling-pilot 남은 감점 검토 → 원문에 없는 작성자 추론을 인용만 달아 쓴 것이라 감점이 맞음, 기준 유지. 새 백로그 1건(약어 M·bn·복합 표기·'만' 조사 오인 실측). CHANGELOG `Unreleased` 한 줄.
- 돌린 시험: `HPR_BACKEND=mock python3 -m unittest discover -s tests -p 'test*.py'` → 560개 통과(시스템 Python 3.11, 새 시험 3개, `httpx`는 설치 필요했음). `python -m evals.run --min-total 97`·`compileall` 통과. walkthrough 재생성 결과 변화 없음. 3.12/3.13·Windows·휠 빌드는 클라우드에서 돌리지 않았다. 실제 `codex exec`는 로그인이 없어 돌리지 않았다.
- PR #17(claude/cloud-work → main)이 아직 열려 있어 같은 브랜치에 이어 푸시하고 PR 본문에 이번 회차 표를 더했다. CI 결과는 푸시 직후라 확인하지 못했다. AGENTS.md의 커밋 댓글 규칙은 이 세션의 GitHub 도구에 커밋 댓글 기능이 없어 따르지 못했고, 대신 PR 본문과 이 기록에 남긴다.
- 남은 한계: 약어(M·bn·k)와 "1억 2천만"↔"1.2억" 같은 복합 표기 환산은 보지 않는다. '만'이 조사로 쓰인 드문 경우를 자릿수로 읽을 수 있다.
- Mac에서 확인할 것:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && HPR_BACKEND=mock python -m evals.run --verbose
  hpr run "노후 하수관 정비 사업비는 얼마였나?"   # report_marks.json의 mismatch 중 금액 문장이 자릿수(억·만)를 원문대로 썼는지 눈으로 판정
  ```

## 2026-10-06 (품질 회차 2)

- 점수 전후(`python -m evals.run`, 종합 평균, 18 case·강화 기준): **99.3 → 99.9**. 주장-출처 일치 97.0→99.3, 본문 내부 일관성 98.6→100. (15 case 이전 끝 99.9, 새 case를 옛 기준으로 재면 99.9 — 맹점.) 상세는 `docs/QUALITY-LOG.md`.
- 한 일:
  - 평가 강화: 결함 case 2개(`ko-recycling-rate`, `en-broadband-access`) — 수치를 다른 기준 연도로 옮김, 퍼센트포인트를 퍼센트로 씀. 점수기 주장-출처 일치에 두 검사 추가(기존 15 case 오탐 0).
  - 개선: `verification._year_conflict`·`_percent_point_conflict` → `(출처 불일치)`(`year_conflict`·`unit_conflict`). 옛 코드 오표시 2건 수정("6%p"를 단위 없는 6으로 읽음, "2023~2025년"의 2023을 수량으로 읽음).
  - 백로그 1건: 같은 방향·2배 이상 다른 증감 폭 출처 상충(`ko-bike-share` case, 점수기, `note_source_conflicts` 안내 줄). 새 백로그 2건(연도 판정 오표시율, 2배 문턱 적정성). CHANGELOG `Unreleased` 한 줄.
- 돌린 시험: `HPR_BACKEND=mock python -m unittest discover -s tests -p 'test*.py'` → 554개 통과(시스템 Python 3.11, 새 시험 15개 — 이번에는 `cryptography` 오류 없음, `httpx`는 설치 필요했음). `python -m evals.run --min-total 97`·`compileall` 통과. walkthrough 재생성 결과 변화 없음. 기존 15 case 최종 보고서 전후 diff 없음. 3.12/3.13·Windows·휠 빌드는 클라우드에서 돌리지 않았다. 실제 `codex exec`는 로그인이 없어 돌리지 않았다.
- PR #17(claude/cloud-work → main)을 열었다. 이전 PR #16은 병합돼 있어 main을 fast-forward한 뒤 시작했다. CI 결과는 아직 확인하지 못했다. AGENTS.md의 커밋 댓글 규칙은 이 세션의 GitHub 도구에 커밋 댓글 기능이 없어 따르지 못했다. 대신 PR 본문과 이 기록에 남긴다.
- PR #17 Codex 리뷰 2건(P2)을 54354d4에서 반영했다. 서로 다른 해의 증감 폭은 상충으로 보지 않고, 문장 첫머리의 영어 연도도 연도로 인식한다(코드·점수기, 시험 3개 추가, 557개 통과, 18 case 점수·보고서 변화 없음).
- 남은 한계: 연도 판정은 명제·문장 단위 근사(비교 연도가 섞인 문장은 모르면 표시 안 함)이고, 퍼센트포인트는 표기만 본다. 증감 폭 상충은 퍼센트 수치·2배 문턱만 본다.
- Mac에서 확인할 것:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && HPR_BACKEND=mock python -m evals.run --verbose
  hpr run "최근 3년 재활용률은 몇 %포인트 올랐나?"   # report_marks.json의 year_conflict·unit_conflict 문장과 한계 절 '증감 폭' 안내를 눈으로 판정
  ```

## 2026-10-06 (품질 회차)

- 점수 전후(`python -m evals.run`, 종합 평균, 14 case·강화 기준): **98.9 → 99.9**. 주장-출처 일치 93.3→99.1. (12 case 이전 끝 99.8, 새 case를 옛 기준으로 재면 99.9 — 맹점.) 상충 case를 더한 15 case 최종 99.9(상충 안내를 끈 코드는 99.6). 상세는 `docs/QUALITY-LOG.md`.
- 한 일:
  - 평가 강화: 결함 case 2개(`ko-flood-damage`, `en-homeless-count`) — 원문의 추정·잠정치를 확정 사실처럼 씀. 점수기 주장-출처 일치에 추정치 검사 추가(연·월·일 제외). 기존 en-fare-free-bus 1문장이 새로 감점(의도).
  - 개선: `verification._estimate_overclaim` → 인용 문장에 약한 표시 `(원문 추정치)`·`(source estimate)`, `report_marks.json`의 `estimate_dropped`, `quality.json`의 `marks.estimate`·머리 주석·`hpr status`(0이면 생략), low 안내(검토 요구 아님).
  - 백로그 1건: 출처끼리 상충 case(`en-school-meals`)와 본문 내부 일관성 기준 → `note_source_conflicts`를 evals가 처음 잰다. 백로그 2건 완료, 새 항목 2건(추정치 오표시율 실측, 같은 방향·다른 값 상충). CHANGELOG `Unreleased` 한 줄.
- 돌린 시험: `HPR_BACKEND=mock python -m unittest discover -s tests -p 'test*.py'` → 539개 통과(Python 3.11 venv, 새 시험 7개). 시스템 python에서는 `cryptography` 패닉(pyo3)으로 doctor 시험 10개가 오류. 변경 전 코드에서도 같아 환경 문제로 보고 venv로 돌렸다. `python -m evals.run --min-total 97`·`compileall` 통과. walkthrough 재생성(`marks.estimate: 0`만 바뀜). 3.12/3.13·Windows·휠 빌드는 클라우드에서 돌리지 않았다. 실제 `codex exec`도 로그인이 없어 돌리지 않았다.
- PR #16(claude/cloud-work → main)을 열었다. CI 결과는 아직 확인하지 못했다. AGENTS.md의 커밋 댓글 규칙은 이 세션의 GitHub 도구에 커밋 댓글 기능이 없어 따르지 못했고, 대신 PR 본문과 이 기록에 남긴다.
- 남은 한계: 추정 낱말(`about`·`nearly`·`약`·`내외`)은 실적 어림수에도 쓰여, 실제 보고서에서 오표시가 생길 수 있다. 상충 기준은 반대 방향만 본다.
- Mac에서 확인할 것:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && HPR_BACKEND=mock python -m evals.run --verbose
  hpr run "지난여름 집중호우 피해 규모는?"   # report_marks.json의 estimate_dropped 문장이 실제로 원문 추정치인지 눈으로 판정
  ```

## 2026-10-05 (품질 회차 2)

- 점수 전후(`python -m evals.run`, 종합 평균, 12 case·강화 기준): **98.9 → 99.8**. 주장-출처 일치 93.4→99.0. (10 case 이전 끝 99.8, 새 case를 옛 기준으로 재면 99.8 — 맹점.) 상세는 `docs/QUALITY-LOG.md`.
- 한 일:
  - 평가 강화: 결함 case 2개(`ko-ev-charging`, `en-heat-pump`) — 원문의 계획·목표 수치를 실적처럼 씀, 시범·표본 결과를 전역 결과로 일반화. 점수기 주장-출처 일치에 두 검사 추가(기존 10 case 오탐 0). 추정치 유보 제거는 범위에서 빼고 이유 기록.
  - 개선: `verification`이 위 두 경우 인용 문장에 `(출처 불일치)` 표시(`plan_conflict`·`scope_conflict`). 기존 10 case 최종 보고서 변화 없음.
  - 백로그 1건: 출처끼리 반대 방향 결과를 한계 절이 다루지 않으면 상충 안내 `(판단)` 한 줄 추가(`note_source_conflicts`, `source_conflicts.json`). 점수기는 재지 않음. 새 백로그 3건(상충 case, 추정치 유보, 오표시율 실측). CHANGELOG `Unreleased` 한 줄.
- 돌린 시험: `HPR_BACKEND=mock python3 -m unittest discover -s tests -p 'test*.py'` → 529개 통과(Python 3.11, 새 시험 11개). `python -m evals.run --min-total 97` 통과. `compileall` 통과. `python -m evals.walkthrough examples/pipeline-walkthrough` 재생성 결과 변화 없음. 상충 안내는 임시 case로 실제 파이프라인을 돌려 한계 절 추가·`source_conflicts.json`·점수 무변화를 확인. 휠 빌드·3.12/3.13·Windows는 클라우드에서 돌리지 않음(CI는 푸시 후 확인 필요). 실제 `codex exec`는 로그인이 없어 돌리지 않음.
- PR #15(claude/cloud-work → main)를 열었다. CI 결과는 아직 확인하지 못했다. AGENTS.md의 커밋 댓글 규칙은 이 세션의 GitHub 도구에 커밋 댓글 기능이 없어 따르지 못했다. 대신 PR 본문과 이 기록에 남긴다.
- 남은 한계: 계획·범위 판정은 낱말 목록 근사(`will`·`expected`·`statewide` 등)라 실제 보고서에서 오표시·누락이 생길 수 있다. 수치 없는 일반화는 문맥 낱말 근사로만 잡는다. PR #15 Codex 리뷰 3건(한 절 안 실적·계획 구분, 수치 없는 일반화, 한계 절 상충 언급 판정)을 반영했다.
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
