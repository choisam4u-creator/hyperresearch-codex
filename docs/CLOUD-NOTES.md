# 클라우드 회차 기록

최신 회차가 맨 위에 온다.

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
