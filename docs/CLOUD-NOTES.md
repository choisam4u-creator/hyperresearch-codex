# 클라우드 회차 기록

최신 회차가 맨 위에 온다.

## 2026-10-02

- 한 일: `docs/CLOUD-BACKLOG.md` 생성. README.md에 "At a glance", README.ko.md에 "한눈에 보기" 절 추가(한 줄 설명·설치 3줄·첫 실행·실측 예시 보고서 발췌). 시험·CI 항목은 기존 463개 mock 시험과 `tests.yml`로 이미 충족됨을 확인하고 표시만 바꿈.
- 돌린 시험: `python3 -m unittest discover -s tests` → 463개 통과(Python 3.11, 클라우드, 모델·네트워크 호출 없음). 실제 `codex exec` 조사는 로그인이 없어 돌리지 않음.
- Mac에서 확인할 것:
  ```bash
  git fetch origin claude/cloud-work && git diff main...origin/claude/cloud-work -- README.md README.ko.md
  hpr doctor && hpr run "테스트 질문" --dry-run
  ```
