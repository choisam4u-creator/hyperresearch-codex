# 클라우드 회차 기록

최신 회차가 맨 위에 온다.

## 2026-10-16 (품질 회차 21)

- 최우선 B1~B4(베타 0.5.0b1): 9회차에 끝나 PR #17로 main에 병합됐고 태그 `v0.5.0b1`도 있다(B1 `ce60e80`·B2 `5fdbbab`·B3 `7c42fee`). 다시 고치지 않고 확인만 했다. PR #17은 병합돼 본문을 고칠 수 없어 열린 PR 본문에 적는다.
- 점수 전후: 별도 에이전트가 쓴 holdout17(12 case·229문장) 기준선 **F1 58.5 → 59.5**, 오표시율 22.2 → 21.3 — **두 개선 모두 holdout17을 보지 않고 설계해 잰 값**. holdout16 62.7 → 64.7(오표시 17.3 → 15.4), holdout15 65.2 → 66.7, holdout12 67.6 → 68.0, holdout5 74.6 → 75.6, holdout9 81.5 → 82.4. 눈가림 holdout8b 66.7 그대로. 전체 73.6 → 74.0(오표시 12.1 → 11.9). 새로 틀린 문장 없음, 고정 32 case 99.9. 상세는 `docs/QUALITY-LOG.md`.
- 한 일: holdout17 먼저(`d93a946`) → 시각 범위 끝 시각·시간당 값×시간·낱말 개수 평균(`4f4b68d`) → 나열 값-이름 맞바꿈(`4295e12`) → 기록, CI holdout17 `--min-f1 55`. 백로그 새 항목 2건.
- 돌린 시험: `HPR_BACKEND=mock python -m unittest discover -s tests -p 'test*.py'` → 648개 통과(Python 3.11 venv, httpx·pypdf 설치). 새 시험 2개는 옛 코드에서 실패를 확인했다. `evals.run` 99.9, 라벨 평가 열여덟 묶음(holdout17 `--min-f1 55` 통과). 실제 `codex exec`는 로그인이 없어 돌리지 않았다. 병합·태그·릴리스·PyPI 게시는 하지 않았다. 이번 푸시들의 GitHub CI 결과는 이 기록 시점에 확인하지 못했다.
- 남은 한계: 보지 않은 묶음 효과는 +1.0으로 작다. 출처 없는 단정·인과 단정·순위 바꿈·부정 뒤집기·표본 일반화가 여전히 큰 약점이고, 맞는 계산 문장(곱·차·퍼센트) 오표시가 holdout17 오표시의 절반이다. 사람 라벨 검토는 아직 없다.
- Mac에서 실제 codex로 확인할 명령 3줄:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && python3 hpr.py doctor
  python3 hpr.py run "야간 연장 돌봄센터는 몇 시간 운영되고, 운영비는 국비·시비·구비가 각각 얼마씩 냈나? 근거와 한계를 밝혀라"
  grep -h -B2 -A8 '"subject_conflict"\|"mismatch"' research/runs/*/report_marks.json | head -60   # 재원 몫·시간 계산 문장 표시를 원문과 대조
  ```

## 2026-10-15 (품질 회차 20)

- 최우선 B1~B4(베타 0.5.0b1): 9회차에 끝나 PR #17로 main에 병합됐고 태그 `v0.5.0b1`도 있다(B1 `ce60e80`·B2 `5fdbbab`·B3 `7c42fee`). 다시 고치지 않고 확인만 했다. PR #17은 병합돼 본문을 고칠 수 없어 열린 PR 본문에 적는다.
- 점수 전후: 별도 에이전트가 쓴 holdout16(12 case·226문장) 기준선 **F1 59.3 → 62.7**, 오표시율 17.3 → 17.3. **보지 않고 잰 holdout16은 개선 1 뒤 59.3 그대로**(개선 1은 이미 본 묶음의 오표시만 줄임). holdout15 64.6 → 65.2(오표시 16.8 → 14.7), holdout12 66.7 → 67.6, holdout2 88.9 → 89.6, 보지 않은 holdout7 78.7 → 79.7. 눈가림 holdout8b 66.7 그대로. 전체 74.4 → 74.9(오표시 11.8 → 11.3). 새로 틀린 문장 없음, 고정 32 case 99.9. 상세는 `docs/QUALITY-LOG.md`.
- 한 일: holdout16 먼저(`02b1df1`) → 원문 값×개수·기간 곱 인정(`442b617`, 백로그 holdout2 '곱으로 낸 값' 진행) → 수치로 순위 바꿈 판정(`e3256d9`) → 기록, CI holdout16 `--min-f1 60`. 백로그 새 항목 2건.
- 돌린 시험: `HPR_BACKEND=mock python -m unittest discover -s tests -p 'test*.py'` → 646개 통과(Python 3.11 venv, httpx·pypdf 설치). 새 시험 2개는 옛 코드에서 실패를 확인했다. `evals.run` 99.9, 라벨 평가 열일곱 묶음(holdout16 `--min-f1 60` 통과). 실제 `codex exec`는 로그인이 없어 돌리지 않았다. 병합·태그·릴리스·PyPI 게시는 하지 않았다. 이번 푸시들의 GitHub CI 결과는 이 기록 시점에 확인하지 못했다.
- 남은 한계: 보지 않은 묶음에서의 효과는 holdout7 1건뿐이다. 조건·범위 바꿈, 몫 맞바꿈, 계획을 완료로, 유보 인과·표본 일반화가 여전히 큰 약점이다. 사람 라벨 검토는 아직 없다.
- Mac에서 실제 codex로 확인할 명령 3줄:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && python3 hpr.py doctor
  python3 hpr.py run "공공 공구 대여소는 어떤 품목이 가장 많이 빌려졌고, 시작 비용은 모두 얼마였나? 근거와 한계를 밝혀라"
  grep -h -B2 -A8 '"subject_conflict"\|"mismatch"' research/runs/*/report_marks.json | head -60   # 순위·합계 문장 표시를 원문과 대조
  ```

## 2026-10-15 (품질 회차 19)

- 최우선 B1~B4(베타 0.5.0b1): 9회차에 끝나 PR #17로 main에 병합됐고 태그 `v0.5.0b1`도 있다(B1 `ce60e80`·B2 `5fdbbab`·B3 `7c42fee`). 다시 고치지 않고 확인만 했다: pyproject·`__version__` `0.5.0b1`, classifier Beta, README 첫 줄 베타 안내, CHANGELOG 머리. PR #17은 병합돼 본문을 고칠 수 없어 열린 PR #18 본문에 적는다.
- 점수 전후: 별도 에이전트가 쓴 holdout15(12 case·207문장) 기준선 **F1 60.1 → 64.6**, 오표시율 16.8 → 16.8. **보지 않고 잰 holdout15 60.1 → 61.3**(개선 1, 결함 +2·오표시 +1). holdout13 72.4 → 73.2, holdout14 66.7 → 68.9(개선 4는 보지 않은 1건). 눈가림 holdout8b 66.7 그대로. 전체 75.2 → 75.7. 새로 틀린 문장 없음, 고정 32 case 99.9. 상세는 `docs/QUALITY-LOG.md`.
- 한 일: holdout15 먼저(`46a02e2`) → 빈도 바꿈(`b1623d3`, 백로그 '빈도·시간대·기간 바꿈' 진행) → 'p.m. 요일' 문장 끊김(`76e811c`) → N 기간마다 빈도(`b5a756b`) → 한국어 수행 주체(`926c30a`) → 기록, CI holdout15 `--min-f1 60`. 백로그 새 항목 2건.
- 돌린 시험: `HPR_BACKEND=mock python -m unittest discover -s tests -p 'test*.py'` → 644개 통과(Python 3.11 venv, httpx·pypdf 설치). 새 시험 4개는 옛 코드에서 실패를 확인했다. `evals.run` 99.9, 라벨 평가 열여섯 묶음(holdout15 `--min-f1 60` 통과). 실제 `codex exec`는 로그인이 없어 돌리지 않았다. 병합·태그·릴리스·PyPI 게시는 하지 않았다. 이번 푸시들의 GitHub CI 결과는 이 기록 시점에 확인하지 못했다.
- 남은 한계: 보지 않은 묶음 효과는 작다(holdout15 +1.2, holdout14 1건). 순위 바꿈·유보 인과 단정·표본 일반화(holdout15 각 4, 0건 잡음)가 가장 큰 약점이다. 사람 라벨 검토는 아직 없다.
- Mac에서 실제 codex로 확인할 명령 3줄:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && python3 hpr.py doctor
  python3 hpr.py run "농촌 순회 진료 버스는 면마다 얼마나 자주 오고, 운영은 누가 맡나? 근거와 한계를 밝혀라"
  grep -h -A8 '"period_conflict"\|"subject_conflict"' research/runs/*/report_marks.json   # 빈도·수행 주체 표시를 원문과 대조
  ```

## 2026-10-14 (품질 회차 18)

- 최우선 B1~B4(베타 0.5.0b1): 9회차에 끝나 PR #17로 main에 병합됐고 태그 `v0.5.0b1`도 있다(B1 `ce60e80`·B2 `5fdbbab`·B3 `7c42fee`). 다시 고치지 않고 확인만 했다: pyproject·`__version__` `0.5.0b1`, classifier Beta, README 첫 줄 베타 안내, CHANGELOG 머리. PR #17은 병합돼 본문을 고칠 수 없어 열린 PR #18 본문에 적는다.
- 점수 전후: 별도 에이전트가 쓴 holdout14(12 case·192문장) 기준선 **F1 61.0 → 66.7**, 오표시율 19.8 → 16.3. **보지 않고 잰 holdout14 61.0 → 61.8**(개선 1, +1문장). 눈가림 holdout8b 64.5 → 66.7, holdout13 67.1 → 72.4(개선 1 설계용), holdout3 84.6 → 88.1(개선 4 설계용), holdout7 77.8 → 78.7. 전체 75.3 → 76.5. 새로 틀린 문장 없음, 고정 32 case 99.9. 상세는 `docs/QUALITY-LOG.md`.
- 한 일: holdout14 먼저(`56de0e2`) → 부담·납부 주체 바꿈(`59169f3`) → 인과 단정 credit·효과로 확인(`e4108d6`) → 상한 어림·기간당 값×기간(`747f9dd`) → 백로그 인과 역전(`963e296`, 백로그 2건 완료) → 기록, CI holdout14 `--min-f1 60`. 개선 4 커밋 메시지의 'holdout3 보지 않음'은 잘못이다(QUALITY-LOG에 바로잡음).
- 돌린 시험: `HPR_BACKEND=mock python -m unittest discover -s tests -p 'test*.py'` → 640개 통과(Python 3.11 venv, httpx·pypdf 설치). 새 시험 4개는 옛 코드(verification.py만 되돌림)에서 실패를 확인했다. `evals.run` 99.9, 라벨 평가 열다섯 묶음(holdout13·14 `--min-f1 60` 통과). 실제 `codex exec`는 로그인이 없어 돌리지 않았다. 병합·태그·릴리스·PyPI 게시는 하지 않았다. 17회차 끝 PR #18 CI(mock 3.11~3.13·windows·CodeQL)는 성공을 확인했고, 이번 푸시들의 CI 결과는 이 기록 시점에 확인하지 못했다.
- 남은 한계: 보지 않은 묶음에 대한 효과는 작다(holdout14 +1, 다른 묶음 결함 3건). 수행 주체·빈도·시간대·방법·조건 바꿈과 '최대' 누락이 가장 큰 약점이다. 사람 라벨 검토는 아직 없다.
- Mac에서 실제 codex로 확인할 명령 3줄:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && python3 hpr.py doctor
  python3 hpr.py run "무더위 쉼터 운영 비용은 누가 냈고, 응급실 온열질환 감소는 쉼터 덕분인가? 근거와 한계를 밝혀라"
  grep -h -A8 '"subject_conflict"\|"causal_conflict"\|"causal_reversal_conflict"' research/runs/*/report_marks.json   # 부담 주체·인과 표시를 원문과 대조
  ```

## 2026-10-14 (품질 회차 17)

- 최우선 B1~B4(베타 0.5.0b1): 9회차에 끝나 PR #17로 main에 병합됐고 태그 `v0.5.0b1`도 있다(B1 `ce60e80`·B2 `5fdbbab`·B3 `7c42fee`). 다시 고치지 않고 확인만 했다: pyproject·`__version__` `0.5.0b1`, classifier Beta, README 첫 줄 베타 안내, CHANGELOG 머리. PR #17은 병합돼 본문을 고칠 수 없어 열린 PR #18 본문에 적는다.
- 점수 전후: 별도 에이전트가 쓴 holdout13(12 case·168문장) 기준선 **F1 63.9 → 67.1**, 오표시율 19.0 → 15.5. **보지 않고 잰 holdout13 63.9 → 63.9**(개선 1, 효과 없음). 눈가림 holdout8b 63.5 → 64.5(오표시 22.6 → 19.4), holdout9 80.9 → 81.5, holdout12 58.7 → 66.7(개선 1 설계용). 전체 75.8 → 76.7. 새로 틀린 문장 없음, 고정 32 case 99.9. 상세는 `docs/QUALITY-LOG.md`.
- 한 일: holdout13 먼저(`ab94596`) → 계획→실적 수동 완료·결정 동사(`cc107aa`) → 단위당 값×개수 계산 값(`90ff118`) → 재원 몫 뒤바뀜(`c9cc75c`) → 기록, CI holdout13 `--min-f1 60`. 백로그 'holdout12 남은 놓침' 진행, 새 항목 3건.
- 돌린 시험: `HPR_BACKEND=mock python -m unittest discover -s tests -p 'test*.py'` → 636개 통과(Python 3.11 venv, httpx·pypdf 설치). 새 시험 3개는 옛 코드에서 실패를 확인했다. `evals.run` 99.9, 라벨 평가 열네 묶음. 실제 `codex exec`는 로그인이 없어 돌리지 않았다. 병합·태그·릴리스·PyPI 게시는 하지 않았다. 푸시들의 GitHub CI 결과는 이 기록 시점에 확인하지 못했다.
- 남은 한계: 개선 1은 보지 않은 묶음에 효과가 없었다(낱말 목록 밖 완료 표현). 방법 바꿈·영어 재원 주체·빈도·시간대 바꿈이 가장 큰 약점이다. 사람 라벨 검토는 아직 없다.
- Mac에서 실제 codex로 확인할 명령 3줄:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && python3 hpr.py doctor
  python3 hpr.py run "드론 병해충 방제 사업의 비용은 누가 얼마씩 냈고, 위원회 권고는 실제로 반영됐나? 근거와 한계를 밝혀라"
  grep -h -A8 '"plan_conflict"\|"subject_conflict"\|"mismatch"' research/runs/*/report_marks.json   # 계획→실적·재원 몫 표시를 원문과 대조
  ```

## 2026-10-13 (품질 회차 16)

- 최우선 B1~B4(베타 0.5.0b1): 9회차에 끝나 PR #17로 main에 병합됐고 태그 `v0.5.0b1`도 있다(B1 `ce60e80`·B2 `5fdbbab`·B3 `7c42fee`). 다시 고치지 않고 확인만 했다: pyproject·`__version__` `0.5.0b1`, classifier Beta, README 첫 줄 베타 안내, CHANGELOG 머리. PR #17은 병합돼 본문을 고칠 수 없어 열린 PR 본문에 적는다.
- 점수 전후: 별도 에이전트가 쓴 holdout12(12 case·169문장) 기준선 **F1 56.7 → 58.7**, 오표시율 20.0 → 20.0. **보지 않고 잰 holdout12 56.7 → 58.3**(개선 2 첫 측정). holdout11 59.0 → 61.0, holdout10 67.2 → 69.2, holdout6 80.3 → 82.0, holdout5 74.0 → 74.6(오표시 13.3 → 11.7). 전체 76.2 → 76.8. 새로 틀린 문장 없음, 고정 32 case 99.9. 상세는 `docs/QUALITY-LOG.md`.
- 한 일: holdout12 먼저(`6c25974`) → 한국어 낱말 몫 오표시(`3f821e6`) → 일 맡은 주체 바꿈(`946fb13`) → 기록, CI holdout12 `--min-f1 55`. 백로그 '대상 바꿈 — 주어 대응' 진행, 새 항목 3건.
- 돌린 시험: `HPR_BACKEND=mock python -m unittest discover -s tests -p 'test*.py'` → 633개 통과(Python 3.11 venv, httpx·pypdf 설치). 새 시험 2개는 옛 코드에서 실패를 확인했다. `evals.run` 99.9, 라벨 평가 열네 묶음. 실제 `codex exec`는 로그인이 없어 돌리지 않았다. 병합·태그·릴리스·PyPI 게시는 하지 않았다. 푸시들의 GitHub CI 결과는 이 기록 시점에 확인하지 못했다.
- 남은 한계: 개선 1은 효과가 작다(1문장). holdout12의 방법(0/7)·역할 바꿈(0/4)·재원(2/8)·계획→실적(4/11)이 가장 큰 약점이다. 눈가림 8b는 움직이지 않았다. 사람 라벨 검토는 아직 없다.
- Mac에서 실제 codex로 확인할 명령 3줄:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && python3 hpr.py doctor
  python3 hpr.py run "길고양이 중성화 사업에서 포획·수술·사후 관리는 누가 맡고 비용은 누가 내나? 근거와 한계를 밝혀라"
  grep -h -A8 '"subject_conflict"\|"wording_conflict"' research/runs/*/report_marks.json   # 주체 바꿈 표시를 원문과 대조
  ```

## 2026-10-13 (품질 회차 15)

- 최우선 B1~B4(베타 0.5.0b1): 9회차에 끝나 PR #17로 main에 병합됐고 태그 `v0.5.0b1`도 있다(B1 `ce60e80`·B2 `5fdbbab`·B3 `7c42fee`). 다시 고치지 않고 확인만 했다: pyproject·`__version__` `0.5.0b1`, classifier Beta, README 첫 줄 베타 안내, `scripts/check_release_version.py v0.5.0b1` 통과. PR #17은 병합돼 본문을 고칠 수 없어 열린 PR 본문에 적는다.
- 점수 전후: 별도 에이전트가 쓴 holdout11(12 case·168문장) 기준선 **F1 56.5 → 59.0**, 오표시율 17.9 → 16.7. **보지 않고 잰 holdout11 56.5 → 58.6**(개선 1). holdout10 61.7 → 67.2(오표시 12.3 → 5.5, 본 묶음), 보지 않은 holdout2 오표시 7.1 → 5.7, holdout7 76.8 → 77.8. 전체 77.1 → 78.0. 새로 틀린 문장 없음, 고정 32 case 99.9. 상세는 `docs/QUALITY-LOG.md`.
- 한 일: holdout11 먼저(`86afc9a`, 이름 겹침 수정 `b9efc30`) → 제외 항목을 포함으로(`3bc0949`) → 두 단계 계산 값(`6bf5a4d`) → 시각 범위 길이(`5e0d5ad`) → 기록, CI holdout11 `--min-f1 55`. 백로그 '시간 합·합의 몫' 완료, 새 항목 2건.
- 돌린 시험: `HPR_BACKEND=mock python -m unittest discover -s tests -p 'test*.py'` → 631개 통과(Python 3.11 venv, httpx·pypdf 설치). 새 시험 3개는 옛 코드에서 실패를 확인했다. `evals.run` 99.9, 라벨 평가 열세 묶음. 실제 `codex exec`는 로그인이 없어 돌리지 않았다. 병합·태그·릴리스·PyPI 게시는 하지 않았다. 푸시들의 GitHub CI 결과는 이 기록 시점에 확인하지 못했다.
- 남은 한계: 대상·재원 바꿈(holdout11 5/11·0/2)과 순서·방법 바꿈(0/3·0/2)이 가장 큰 약점이다. 눈가림 8b는 움직이지 않았다. 사람 라벨 검토는 아직 없다.
- Mac에서 실제 codex로 확인할 명령 3줄:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && python3 hpr.py doctor
  python3 hpr.py run "저소득층 바우처는 어떤 품목에 쓸 수 있고 무엇이 제외되나? 근거와 한계를 밝혀라"
  grep -h -A8 '"negation_conflict"\|"mismatch"' research/runs/*/report_marks.json   # 제외 항목·계산 값 표시를 원문과 대조
  ```

## 2026-10-12 (품질 회차 14)

- 최우선 B1~B4(베타 0.5.0b1): 9회차에 끝나 PR #17로 main에 병합됐고 태그 `v0.5.0b1`도 있다(B1 `ce60e80`·B2 `5fdbbab`·B3 `7c42fee`). 다시 고치지 않고 확인만 했다: pyproject·`__version__` `0.5.0b1`, classifier Beta, README 첫 줄 베타 안내, release.yml이 `scripts/check_release_version.py`로 태그·버전 일치를 검사하고 `tests/test_release_version.py`가 `v0.5.0b1`을 받는다. PR #17은 병합돼 본문을 고칠 수 없어 열린 PR #18 본문에 적었다.
- 점수 전후: 별도 에이전트가 쓴 holdout10(12 case·156문장) 기준선 **F1 55.2 → 61.7**, 오표시율 19.2 → 12.3. 보지 않고 잰 수치: holdout10 +0.0(개선 1~3), **눈가림 holdout8b 62.5 → 63.5·오표시 25.8 → 22.6**. 전체(all) 77.5 → 79.2, 오표시 11.6 → 9.1. 오표시는 dev·holdout2·5·6·7·9에서도 줄었고, 새로 틀린 문장은 없다. 고정 32 case 99.9. 상세는 `docs/QUALITY-LOG.md`.
- 한 일: holdout10 먼저(`9a42af0`) → 나열 주어 부정·나열 항목 바꿈(`be5fa3a`) → 오표시 줄이기(`5bafbd8`) → 순위 바꿈·세는 말·몫 표현(`d64e841`) → 기록, CI holdout10 `--min-f1 55`. 백로그 '다음 독립 묶음은 코드 수정 전에' 이어 감, 새 항목 3건.
- 돌린 시험: `HPR_BACKEND=mock python -m unittest discover -s tests -p 'test*.py'` → 628개 통과(Python 3.11 venv, httpx·pypdf 설치). 새 시험 5개는 옛 코드에서 실패를 확인했다. `evals.run` 99.9, 라벨 평가 CI 문턱 모두 통과, compileall 통과. 실제 `codex exec`는 로그인이 없어 돌리지 않았다. 병합·태그·릴리스·PyPI 게시는 하지 않았다. 푸시들의 GitHub CI 결과는 이 기록 시점에 확인하지 못했다.
- 남은 한계: 보지 않은 holdout10에는 개선 1~3이 효과가 없었다. 대상·주체 바꿈(1/9)과 부정(4/13)·범위(2/9)가 가장 큰 약점이다. 사람 라벨 검토는 아직 없다.
- Mac에서 실제 codex로 확인할 명령 3줄:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && python3 hpr.py doctor
  python3 hpr.py run "주거 집수리 지원사업에서 가장 많이 한 공사는 무엇이고 비용은 누가 냈나? 근거와 한계를 밝혀라"
  grep -h -A8 '"subject_conflict"\|"negation_conflict"\|"mismatch"' research/runs/*/report_marks.json   # 표시된 문장을 원문과 대조
  ```

## 2026-10-12 (품질 회차 13)

- 최우선 B1~B4(베타 0.5.0b1): 9회차에 끝나 PR #17로 main에 병합됐고 태그 `v0.5.0b1`도 있다(B1 `ce60e80`·B2 `5fdbbab`·B3 `7c42fee`). 다시 고치지 않고 확인만 했다: pyproject·`__version__` `0.5.0b1`, classifier Beta, README 첫 줄 베타 안내, `scripts/check_release_version.py v0.5.0b1` 통과. PR #17은 병합돼 본문을 고칠 수 없어 열린 PR #18 본문에 적었다.
- 점수 전후: 별도 에이전트가 쓴 holdout9(12 case·147문장) 기준선 **F1 65.6 → 76.3**, 오표시율 13.7 → 9.6. 보지 않고 잰 수치: holdout9 +0.0(개선 1·2), **눈가림 holdout8b 60.3 → 62.5**. 설계 때 보지 않은 묶음 dev 88.4→89.7, holdout 83.2→84.2, holdout5 72.9→73.8, holdout6 77.7→78.6, holdout7 74.6→75.6. 오표시가 늘어난 묶음 없음, 고정 32 case 99.9. 상세는 `docs/QUALITY-LOG.md`.
- 한 일: holdout9 먼저(`0d26741`) → 작은 합·차 우연 일치(`ec2c50d`) → 비교 오표시(`7db4886`) → 재원 바꿈(`52134bb`) → 완료 단정(`eca9dde`) → 단위·달 범위·'rather than'(`34ce322`) → 기록, CI holdout9 `--min-f1 70`. 백로그 '판정 동사 바꿈("결정하지 않았다"→"확정했다")' 진행.
- 돌린 시험: `HPR_BACKEND=mock python -m unittest discover -s tests -p 'test*.py'` → 623개 통과(Python 3.11 venv, httpx·pypdf 설치; 시스템 python엔 httpx가 없어 26개 import 오류). 새 시험 5개는 옛 코드에서 실패를 확인했다. `evals.run` 99.9, 라벨 평가 CI 문턱 모두 통과. 실제 `codex exec`는 로그인이 없어 돌리지 않았다. 병합·태그·릴리스·PyPI 게시는 하지 않았다. 푸시들의 GitHub CI 결과는 확인하지 못했다.
- 남은 한계: 눈가림 8b 오표시율 25.8이 그대로다. 낱말 목록 방식이라 보지 않은 묶음 효과가 작다(개선 4만 넓게 일반화). 사람 라벨 검토는 아직 없다.
- Mac에서 실제 codex로 확인할 명령 3줄:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && python3 hpr.py doctor
  python3 hpr.py run "시장 화재 감지기 시범사업의 설치비는 누가 냈고, 소방서가 제안한 개선안은 도입됐나? 근거와 한계를 밝혀라"
  grep -h -A8 '"plan_conflict"\|"subject_conflict"\|"negation_conflict"' research/runs/*/report_marks.json   # 표시된 문장을 원문과 대조
  ```

## 2026-10-11 (품질 회차 12)

- 점수 전후: 별도 에이전트가 쓴 holdout8(12 case·135문장)을 설계용 8a·눈가림 8b로 나눴다. **눈가림 8b F1 60.3 → 60.3(변화 없음)**, 설계용 8a 62.5 → 73.0, holdout8 전체 61.4 → 66.7(오표시율 24.2 → 17.7). 바깥 묶음 holdout5 70.9 → 72.9, 나머지는 그대로이고 오표시가 늘어난 묶음은 없다. 상세는 `docs/QUALITY-LOG.md`.
- 한 일: holdout8 먼저(`5135247`) → 어림 낱말·합계·'없이' 오표시(`aa7877e`) → '이미' 시행 단정(`a6541aa`) → 재원 주체 바꿈(`c47aef1`) → 기록, CI holdout8 `--min-f1 60`.
- 돌린 시험: `HPR_BACKEND=mock python -m unittest discover -s tests -p 'test*.py'` → 618개 통과. 새 시험 3개는 옛 코드에서 실패를 확인했다. `evals.run` 99.9, CI 라벨 평가 문턱 통과. 실제 `codex exec`는 로그인이 없어 돌리지 않았다. 병합·태그·릴리스는 하지 않았다.
- 남은 한계: 눈가림 절반이 움직이지 않았다 — 낱말 목록 방식은 설계에 쓴 표현 밖으로 일반화가 약하다는 11회차 결론을 다시 확인했다. 8b는 다음 회차에도 눈가림으로 쓰도록 오판 목록을 열지 않았다.
- Mac에서 실제 codex로 확인할 명령 3줄:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && python3 hpr.py doctor
  python3 hpr.py run "지하 주거 곰팡이 개선 공사 지원사업은 습도를 얼마나 낮췄고 비용은 누가 냈나? 근거와 한계를 밝혀라"
  grep -h -A8 '"plan_conflict"\|"subject_conflict"\|"mismatch"' research/runs/*/report_marks.json   # 표시된 문장을 원문과 대조
  ```

## 2026-10-11 (품질 회차 11)

- 최우선 B1~B4(베타 0.5.0b1): 9회차에 끝나 PR #17로 main에 병합됐고 태그 `v0.5.0b1`도 이미 있다(B1 `ce60e80`·B2 `5fdbbab`·B3 `7c42fee`). 이번에는 다시 고치지 않고 확인만 했다: pyproject·`__version__`·CITATION `0.5.0b1`, classifier Beta, README 첫 줄 베타 안내, `scripts/check_release_version.py v0.5.0b1` 통과. PR #17은 병합돼 본문을 고치지 않았다. 태그 뒤 CHANGELOG의 `0.5.0b1` 아래에 들어간 10회차 줄은 실제 태그에 없어서 새 `## [Unreleased]`로 옮겼다.
- 점수 전후: 별도 에이전트가 쓴 holdout7(12 case·134문장) **F1 66.1 → 74.6**, 오표시율 21.0 → 11.3. 덜 편향된 수치는 holdout7을 보지 않고 만든 개선 1·2 뒤의 **67.2(+1.1)**. 다른 묶음: holdout5 66.1→70.9, holdout6 73.1→77.7, holdout4 81.2→82.0, 나머지는 그대로이고 오표시가 늘어난 묶음은 없다. 상세는 `docs/QUALITY-LOG.md`.
- 한 일: holdout7 먼저(`4d891c9`) → 유보→단정(`db9d22f`) → 조건 뒤집기(`b3671a8`) → holdout7 오판을 본 뒤 조건 확장·계산 값(`be40352`) → 기록, CI holdout7 `--min-f1 70`. 백로그 '유보 탈락' 완료, '조건·자격 바꿈' 진행, 새 항목 3건.
- 돌린 시험: `HPR_BACKEND=mock python -m unittest discover -s tests -p 'test*.py'` → 615개 통과(Python 3.11 venv). 새 시험 3개는 옛 코드에서 실패를 확인했다. `evals.run` 99.9, CI 라벨 평가 여덟 문턱 통과. 실제 `codex exec`는 로그인이 없어 돌리지 않았다. 태그·릴리스·PyPI 게시는 하지 않았다. 이 푸시들의 GitHub CI 결과는 확인하지 못했다.
- 남은 한계: 조건 개선은 보지 않은 묶음에서 효과가 0이었다. 낱말 목록 방식은 묶음마다 일반화가 약하다. 어느 묶음도 아직 사람이 검토하지 않았다.
- Mac에서 실제 codex로 확인할 명령 3줄:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && python3 hpr.py doctor
  python3 hpr.py run "버스정류장 쿨링포그 시범사업은 기온을 얼마나 낮췄고 어떤 조건에서 작동했나? 근거와 한계를 밝혀라"
  grep -h -A8 '"causal_conflict"\|"scope_conflict"\|"mismatch"' research/runs/*/report_marks.json   # 표시된 문장을 원문과 대조
  ```

## 2026-10-11 (품질 회차 10)

- 점수 전후: 별도 에이전트가 코드 수정 전에 쓴 holdout6 라벨 평가(`python -m evals.labeled --set holdout6`, 12 case·135문장) **F1 63.6 → 73.1**(recall 56.8→66.2, precision 72.4→81.7, 맞는 문장 오표시율 26.2→18.0). 설계 때 보지 않은 묶음: holdout3 83.1→83.7, holdout4 80.3→81.2, dev·holdout·holdout2·holdout5 변화 없음, 오표시 증가 0. 고정 32 case 99.9 그대로. 상세는 `docs/QUALITY-LOG.md`.
- 한 일(항목마다 커밋·푸시): holdout6 먼저(`e12a22e`) → 계산 값 읽기(`11f3ded`) → 'of' 없는 설문 몫(`497660a`) → 검토 중인 방안(`47a8419`) → 주된 이유 바꿈(`84d37e7`) → 기록·CI holdout6 `--min-f1 65`(`2b7f46c`).
- 돌린 시험: `HPR_BACKEND=mock python3 -m unittest discover -s tests -p 'test*.py'` → 612개 통과(Python 3.13). 새 시험 4개는 옛 코드에서 실패 확인. `evals.run --min-total 97`, CI의 라벨 평가 일곱 문턱, `compileall`, `scripts/check_release_version.py v0.5.0b1` 통과, walkthrough 변화 없음. 실제 `codex exec`는 로그인이 없어 돌리지 않았다. 태그·릴리스는 만들지 않았다.
- 남은 한계: 개선은 holdout6 오판 목록을 본 뒤 만들어 끝 점수는 과대평가. holdout5는 이번 개선으로 변하지 않았다(묶음마다 결함 유형이 달라 일반화가 약함). 조건·자격 바꿈과 수치 비교 뒤집기가 큰 남은 약점.
- Mac에서 실제 codex로 확인할 명령 3줄:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && python3 hpr.py doctor
  python3 hpr.py run "수리 카페 시범사업에서 수리가 실패한 주된 이유와 참여자 설문 결과는 무엇인가? 근거와 한계를 밝혀라"
  grep -h -A8 '"causal_conflict"\|"share_conflict"\|"plan_conflict"' research/runs/*/report_marks.json   # 표시된 문장을 원문과 대조
  ```

## 2026-10-11 (품질 회차 9) — v0.5.0b1 베타 준비 + holdout5

- 최우선 B1~B4(샘님 10/11 승인, 베타 PyPI 공개 준비): **B1 `ce60e80`** 버전 `0.5.0b1`(pyproject·`__version__`·CITATION·README 배지·이슈 템플릿, CHANGELOG 머리 `## [0.5.0b1] - 2026-10-11 (베타)`) · **B2 `5fdbbab`** README·README.ko·PYPI.md 맨 위 베타 안내(classifier는 이미 Beta) · **B3 `7c42fee`** `release.yml` 태그 검사를 `scripts/check_release_version.py`로 옮겨 `v0.5.0b1`·`aN`·`rcN` 허용, pyproject·`__version__`·CITATION 셋 대조, `tests/test_release_version.py`. `python -m build` → `hyperresearch_codex-0.5.0b1` sdist·wheel, `twine check` PASSED. 태그·릴리스·PyPI 게시는 하지 않음.
- 점수 전후: 새 독립 묶음 holdout5(별도 에이전트 작성, 12 case·132문장) **F1 57.9 → 66.1**(recall 48.6→56.9, precision 71.4→78.8, 오표시율 23.3→18.3). holdout4 77.6→80.3, holdout3 82.2→83.1, holdout2 86.8→87.5, dev·holdout 그대로, 고정 32 case 99.9 그대로. 상세·한계는 `docs/QUALITY-LOG.md`.
- 한 일: holdout4로 기간 합계·값 비교 개선(`c5b60cb`, holdout5에선 효과 0 — 정직하게 기록) → holdout5 커밋(`7eac323`)·제목 픽스처 수정(`7438c2b`, 내 지시문 오류) → 날짜 오인 "2월 120곳"·맨 숫자·배수(`e20e11a`) → 비교 뒤집기 확장(`cc7ce4c`). CI에 holdout5 `--min-f1 60`. 백로그 'CHANGELOG와 다음 버전 준비' 완료, 새 항목 5건.
- 돌린 시험: 전체 mock 단위 시험 608개 통과(Python 3.11 venv, 클라우드; 시스템 pip/python 불일치로 venv 사용), `evals.run`(99.9)·`evals.labeled` 여섯 묶음 CI 문턱 통과, 패키지 빌드·twine check. 이 푸시들의 GitHub CI 결과는 확인하지 않았다. 커밋 댓글 도구가 없어 AGENTS.md 커밋 댓글 대신 PR #17 본문과 이 기록에 남긴다.
- Mac에서 실제 codex로 확인할 것:
  - `pip install -e . && python3 -c "import hprc; print(hprc.__version__)"` → `0.5.0b1`, `python3 scripts/check_release_version.py v0.5.0b1`
  - `python3 hpr.py doctor && python3 hpr.py run "<한국어 정책 질문>"` 후 `report_marks.json`의 `antonym_conflict`·`period_conflict` 문장을 사람이 판정(오표시율)

## 2026-10-10 (품질 회차 8)

- 점수 전후: 검사 코드·이전 라벨을 읽지 않은 별도 에이전트가 코드 수정 전에 쓴 holdout4 라벨 평가(`python -m evals.labeled --set holdout4`, 12 case·135문장) **F1 65.2 → 77.6**(recall 60.8→70.3, precision 70.3→86.7, 맞는 문장 오표시율 31.1→13.1). 설계 때 보지 않은 묶음: holdout 81.4→83.2, holdout2 86.2→86.8, holdout3 80.0→82.2, dev 88.4 그대로. 고정 32 case `evals.run` 100.0→99.9(유보 문장 규칙의 대가, QUALITY-LOG). 상세는 `docs/QUALITY-LOG.md`.
- 한 일(항목마다 커밋·푸시):
  - 코드 수정 전 먼저: holdout4 12 case(`024cf77`). 이전 회차 holdout은 고치는 세션이 직접 썼다 — 기준선이 holdout3 끝보다 15점 낮아 그 점수들이 과대평가였음을 확인.
  - 개선 1 계산 값 읽기(`ca92bd1`): ㎏·㎞·마일, 단위당 값 환산, 세는 말이 다른 몫, 1건당, '10명 중 약 8명', 건수×건당 금액.
  - 개선 2 유보·부정 문장은 `wording_conflict`로 표시하지 않음(`3853221`) — 3회차에 내가 넣은 이 검사가 독립 라벨에서 가장 약했다.
  - 개선 3 설문 몫→주민 전체 몫(`12ae321`), 개선 4 원문이 유보한 귀속을 결론처럼(`76c367b`).
  - 기록: QUALITY-LOG·백로그(1건 완료·6건 추가)·CHANGELOG·evals README, CI에 holdout4 `--min-f1 70`(`c25fdec`).
- 돌린 시험: `HPR_BACKEND=mock python3 -m unittest discover -s tests -p 'test*.py'` → 598개 통과(Python 3.13, `pip install -e .`). 새 시험 5개 중 4개는 옛 코드에서 실패 확인(km→mile 상쇄 방지 시험은 회귀 감시용). `evals.run --min-total 97`, `evals.labeled` 다섯 묶음 CI 문턱, `compileall` 통과, walkthrough 변화 없음. 3.11/3.12·Windows는 클라우드 CI에 맡겼다. 실제 `codex exec`는 로그인이 없어 돌리지 않았다.
- PR #17에 이어 푸시하고 PR 본문 맨 위에 이번 회차 표를 더한다. AGENTS.md의 커밋 댓글 규칙은 이 세션의 GitHub 도구에 커밋 댓글 기능이 없어 PR 댓글로 대신한다.
- 남은 한계: holdout4도 개선 전에 오판 목록을 봤으므로 끝 점수는 과대평가. 사람 라벨 검토 전. 대상 바꿈(수치 없는 집단·요인 바꿈)은 8 중 2만 잡는다.
- Mac에서 실제 codex로 확인할 명령 3줄:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && python3 hpr.py doctor
  python3 hpr.py run "공유우산 시범사업은 시민 만족도와 우산 회수율에 어떤 결과를 냈나? 근거와 한계를 밝혀라"
  grep -h -A8 '"scope_conflict"\|"causal_conflict"\|"wording_conflict"' research/runs/*/report_marks.json   # 표시된 문장을 원문과 대조
  ```

## 2026-10-10 (품질 회차 7)

- 점수 전후: 코드 수정 전에 만든 새 holdout3 라벨 평가(`python -m evals.labeled --set holdout3`, 12 case·128문장) **F1 70.1 → 80.0**(recall 64.4→71.2, precision 77.0→91.2, 맞는 문장 오표시율 25.5→9.1). 설계 때 보지 않은 묶음: holdout2 80.9→86.2(오표시율 17.1→11.4), holdout 80.0→81.4(10.8→7.7), dev 88.4 그대로. 고정 32 case(`evals.run`) 100.0 그대로. 상세는 `docs/QUALITY-LOG.md`.
- 한 일(항목마다 커밋·푸시):
  - 코드 수정 전 먼저: 기존과 겹치지 않는 holdout3 case 12개(부정 23·범위 12·방향 8·단위 바꿔치기 7·인과 역전·순서 4, 맞는 문장: 반올림·계산 값 32·동의어 16·단위 환산 4)와 `--set holdout3`(`0a06645`).
  - 개선 1 계산 값·단위·제외 낱말(`dc972d0`): 범위 앞 값 단위 물려받기, 넓이·온도·낱말 전력량·개월 단위, 차·곱·화씨↔섭씨·기간당 평균·증감률, left out·빠졌·제외를 부정으로. 개선 2 전후 쌍·비교 기준 뒤집기(`1079b8f`, `antonym_conflict`). 시험 3개(모두 옛 코드에서 실패 확인).
  - 백로그: '10개월'을 '10개'로 읽던 결함과 달 범위 길이. 항목 2건 진행 기록, 새 항목 4건. CI에 holdout3 `--min-f1 75`. CHANGELOG·evals README.
- 돌린 시험: `HPR_BACKEND=mock python3 -m unittest discover -s tests -p 'test*.py'` → 594개 통과(Python 3.11; `httpx`·`pypdf`·`cffi`를 따로 설치). `evals.run`(100.0)·`evals.labeled`(dev 88.4, holdout 81.4, holdout2 86.2, holdout3 80.0)·`compileall` 통과, walkthrough 재생성 변화 없음. 3.12/3.13·Windows·휠 빌드와 실제 `codex exec`는 돌리지 않았다.
- 한계: holdout3도 이 세션이 쓰고 라벨을 달았고 개선 1·2는 그 기준선 오판을 본 뒤 만들었다 — holdout3 끝 점수는 과대평가다. 개선 2는 다른 세 묶음에서 변화가 없어 일반화 근거가 아직 없다. 남은 최저 유형은 낱말을 바꾼 부정(holdout3 15/23)과 인과 역전(0/4). 커밋 댓글 규칙은 이 세션 GitHub 도구에 커밋 댓글 기능이 없어 PR 본문·이 기록으로 대신한다. CI 결과는 푸시 직후라 확인하지 못했다.
- Mac에서 실제 codex로 확인할 명령 3줄:
  ```bash
  git fetch origin claude/cloud-work && git checkout claude/cloud-work && python3 hpr.py doctor
  python3 hpr.py run "열펌프 보조금은 저소득 가구 난방비를 얼마나 줄였나? 단위와 근거를 밝혀라"
  grep -h '"mismatch"\|"antonym_conflict"' -A8 research/runs/*/report_marks.json   # 환산·계산 문장 오표시와 전후 뒤집기 표시를 원문과 대조
  ```

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
