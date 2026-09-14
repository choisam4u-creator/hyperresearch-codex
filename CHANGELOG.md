# Changelog

## 2026-09-14 공개 근거 줄바꿈 보존

- Git checkout의 자동 줄바꿈 변환이 실측 원문·검토 JSON·동결 실행기 해시를 바꾸지 않도록 공개 결과 경로를 바이트 그대로 보존. `core.autocrlf=true` 재현 회귀 추가.

## 2026-09-14 효율 데이터와 실측 도구 보완

- 입력 패킷 개발8회·보류12회 실측 사용량, 원본 보고서 및 전체 본문 블라인드 판정 공개. 일반적인 절감·품질 향상 주장은 보류.
- 실제 실행에 사전 고정 계획을 요구하고 호출 후 조건 변화를 감지하며, 불완전 사용량을 미측정으로 기록.
- 재사용·갱신·Full의 mock 관찰과 두 블로그 자료의 근거 메모·계산 검증 범위 정리. 근거 선택4회 실제 호출은 입력 차이가 없는 사전 점검 후 미실행.

## 효율 실측 준비 (2026-09-14)

- 입력 패킷만 바꾸는 8회(축소 탐색 4회) 사전 계획과 실행 도구를 추가했다. 기본 동작은 계획 출력이며 실제 모델 호출은 명시적 예산 지정이 필요하다.
- 실행 설정·고정 입력·코드 결속, 실패와 미측정 사용량 보존, 재실행 방지 및 블라인드 검토 자료 생성을 준비했다. 이 변경은 실제 절감률이나 품질 향상을 입증한 결과가 아니다.

## Unreleased
- [입력 효율과 조사 갱신](docs/EFFICIENCY.md): 준비 입력 진단, 선택 입력 패킷·주장별 근거 coverage, 정확 조건 분석 캐시, facts 단일 초안 경로, 변경분 분석, 근거/변경 비교표와 원문 결속 계산 검산을 추가했다. 실행 변경은 선택 기능이며 실제 토큰 절감률·품질 우위는 미측정이다.
- 날짜의 명백한 병렬 표현에만 생략 연도를 보충하고, 부호가 반대인 값은 별도 의미 검토 신호로 구분한다. 한국어 수량 단위 곳/개소·개·대·회·종을 구분하며 [검증 범위](docs/VERIFICATION-BOUNDARIES.md)를 명시했다. 푸시 후 GitHub 커밋 댓글에 수정·검증 내역을 남기는 유지보수 규칙을 추가했다.
- 내부 후속 개선: `status` 비용은 실행에 저장된 단가로 추정하고 구형 기록의 현재 단가 대체를 명시한다. 정책 비교는 미검증 품질과 사용량 누락을 미확정으로 보존한다. 한국어 날짜 범위의 숫자 조각 오경고를 줄이되 연도 생략·잘못된 날짜는 검토 대상으로 남기고, 전력(W/kW)과 에너지(Wh/kWh)를 구분한다. 실제 정확도·토큰 절감률 재실측은 하지 않았다.
- 승인된 고정 합성 입력 실측 4회 완료: 808,255토큰, 실패·재시도·미측정 0회. 역할별 배정은 Astra 대비 총 토큰이 6.3% 늘어 절감 목표를 달성하지 못했다. 기본값을 유지하며 [판정 범위와 결과](docs/PILOT-20260914.md)를 기록했다.
- 남은 작업 Goal: 선택적 세부 의미 인용 계약을 같은 검사 호출에 연결하고 발췌·원문 이중 결속과 스냅샷별 원장 연결을 추가했다. 기본 OFF이며 실제 의미 정확도는 미검증이다.
- `--total-budget` 입력+출력 중단·예약·미측정 중단, `--format` 사실/비교/분석 형식, 독립 판정과 엄격 비교를 받는 benchmark 평가 CLI를 추가했다. [후속 범위와 실측 계획](docs/REMAINING-GOAL.md)을 참고한다.
- Phase 8–13 로컬 기반: 정답 분리 고정 입력 replay·엄격한 구성 비교·품질 통과 보고서당 전체 토큰 평가, 문장/출처/발췌 해시 원장, 날짜·단위·표 문맥 보존, 선택적 변경 인용 재검사, vault 우선 gap 순위, 호출 예약·총 시도 상한·실험 economy 역할 배정, 호출 없는 review.md를 추가했다. [완료 범위와 남은 작업](docs/TOKEN-FIRST-PHASES.md)을 구분하며 실제 품질·절감률과 원본 우위는 미측정이다.
- 재개 호출의 코드·프롬프트 변경을 차단하고 유효 예산 설정 및 호출별 구성 해시를 남긴다. 오래된 인용 판정은 최종 통과 근거로 인정하지 않는다.
- Phase 2–7 최종 로컬 회귀 166개와 격리 wheel mock 실행·재개를 통과했다. Astra 검수 지적을 수정하고 관련 회귀를 추가했다.
- Phase 2–7 구현 범위를 문서화했다: 안전한 source wrapping과 정확한 private-host allowlist, `quality.json`과 검토 필요 시 CLI exit 3, 기본 OFF인 Full gap 보충(최대 2 gaps/3 sources)과 immutable vault reuse, 오프라인 evaluator, wheel package resource 기반 `install-skill`을 포함한다. 실제 모델 benchmark·외부 설치 피드백·릴리스는 아직 보류다.
- Windows 3.12 CI와 wheel smoke 단계를 추가했다. 구현 커밋 `346a82d`의 [CI](https://github.com/choisam4u-creator/hyperresearch-codex/actions/runs/34766135191)에서 Linux 3.11–3.13과 Windows 3.12가 모두 통과했다. Windows는 POSIX fixture 4개를 제외한 회귀·설치·mock 실행/재개·wheel 범위이며 실제 Codex 리서치는 미검증이다.
- 2026-09-14 Phase 1 후속 검증: 전체 회귀 112개 통과, 임시 wheel 설치·mock 실행·재개 확인. 이전 96개 기록은 앞선 구현 시점이다.
- 출처 노트를 영구 ID 기반 불변 스냅샷으로 저장해 실행 간 S번호·제목 충돌을 방지한다. 실행별 인용 별칭은 유지하고 구형 노트는 다시 쓰지 않는다.
- 게시일·수정일과 근거 메타를 노트와 모델 입력까지 전달한다. 구형 노트의 빠진 날짜는 해당 실행의 출처 메타로 보충한다.
- 실행 ID의 상위 경로·절대 경로·외부 symlink를 공통 경계에서 거부한다. 원본 비교표의 예산·재개·최종 검증 설명을 정정하고 후속 페이즈 계획을 추가했다.
- `doctor`에 검증된 Codex CLI 버전과의 불일치 경고, 버전·로그인 조회의 3초 제한, 실행 오류 진단을 추가했다. 버전 차이는 경고이며 조회 실패·로그인 미확인은 종료코드 1로 표시한다.
- 실패·재시도의 측정 가능한 사용량을 보존하고 미측정 호출을 비용 추정에서 구분한다. 시도별 로그를 덮어쓰지 않으며 구형 장부 backfill의 중복 방지를 검증한다.
- 양수 예산 입력과 호출·재시도 직전 검사를 추가했다. 진행 중·병렬 호출의 초과 가능성은 남는다. 동일 실행 잠금과 비평별 체크포인트로 중복 실행·완료된 비평 재호출을 줄인다. 이전 POSIX 전용 잠금은 이번 Phase 7에서 Windows msvcrt 지원으로 확장했다.
- HTML 본문 추출·인코딩·부분 다운로드·수집 오류 처리를 보완하고 게시일과 수정일 근거를 분리했다.
- 문서 전체의 표·목록까지 인용 표본을 분산하고, 다듬기 전 스냅샷 기준으로 미지지·미반환·표본 밖 범위를 표시한다. 다국어 합성 회귀 자료를 추가했다.
- 검색 오류 종류를 보존하고 명시적 SearXNG 주소가 있는 경우에만 빈 후보의 보조 검색을 제공한다. 기본 OFF이며 `--no-search`는 학술 검색도 막는다.
- CI에서 전체 테스트를 탐색하고 wheel 프롬프트 포함·비공개 폴더 제외·격리 설치를 검사하도록 준비했다. 실제 리서치 모델 호환성은 mock 검증에 포함하지 않는다.
- 앞선 유지보수 시점 로컬 회귀 96개 통과. macOS 임시 환경에서 최종 wheel 설치·저장소 밖 mock Light 완주·추가 호출 없는 재개를 확인했다. 원격 CI·Windows 결과와 구분한다.

## 0.3.1 - 2026-09-13
- Cite-check reads each cited note selected by the sentences that cite *that* source, not by all sample sentences at once (a Korean-vs-English mismatch left a 93-char note and produced false "unsupported" verdicts in the variance run). Verified with one more real run of the same question: unsupported 4/5 → 1/5, the English Google notes now reach the checker at 4–6k chars.
- Paragraph selection tokenizes Latin and Hangul runs separately ("Google은" now matches "Google") and, when nothing overlaps, fills the cap in document order instead of returning only the title.
- URL normalization maps developers.google.cn to developers.google.com and drops `hl=` on Google docs (a German translation had been fetched as a source).
- Test plan results for the four Light lean runs recorded in docs/TEST-PLAN.md.
- Failure paths are readable stops, not tracebacks: login expired → `state.json` `auth_required` with a `codex login` hint; codex binary missing → `codex_missing`; usage limit, auth and missing binary no longer retry or fall through to the next search provider (`HardStop`); a missing `--urls` file, an unknown `resume` id, and malformed URLs (`https://[::1`) are skipped or reported instead of crashing; a step that fails twice records `failed`.
- Timeout is enforced with the remaining time, not in 30-second heartbeat steps.
- Examples and a picture: `examples/report-en-light-lean.md` and `examples/report-ko-light-lean.md` are unedited real reports; `scripts/render-log-svg.py` turns a run log into the animated terminal SVG shown in the README (no external tools).
- Packaging for GitHub: author `samchoi`, project URLs, issue/PR templates, CI installs the package and runs the 28 mock tests on Python 3.11–3.13, comparison table and credits in both READMEs.
- 7 failure-path tests (network down, bad URLs, missing file, all search providers failing, usage limit mid-run then resume, auth error in scout, and a fake `codex` executable exercising the real subprocess path for ok/limit/auth/garbage/timeout/missing).

## 0.3.0 - 2026-09-13
- Token diet: per-step inputs. Analyst sees all notes; drafts see only sources the analyst actually cited; critics/patcher see a claims digest + 2,500-char excerpts; synthesis sees drafts + interim + digest only; cite-check sees only the cited notes; polish sees the report only.
- Live progress on stderr (`[hpr HH:MM:SS] step …`), per-run `state.json` (current step, pid, running cost) and `--quiet`.
- `--budget N` stops before the next step once cumulative input tokens exceed N; `resume --budget` continues. `status` shows an upper-bound USD estimate (configurable prices).
- `--dry-run` prints steps, expected calls and rough cost without running.
- Accuracy: truncated notes are flagged to the model; recommendation sentences are marked "(판단)" and skipped by cite-check; scout is told to stay on-topic and capped at N searches; Last-Modified header as a published-date fallback (marked with *); domain-skew warning when one domain exceeds 60 % of sources; provenance table shows which sources were actually cited.
- Prompts ask the model to read all files in one command (fewer turns → fewer re-sent tokens).
- Heartbeat every 30 s during a model call (elapsed, tool usage) and `[k/N]` step tags; final header line printed at the end.
- Relevance-based note selection (`hprc/text_select.py`): when a note exceeds its cap, keep the intro plus the paragraphs most related to the question/draft/findings instead of the head.
- `pip install .` installs the `hpr` command (CLI moved into `hprc/cli.py`; `hpr.py` is a thin wrapper); `HPR_HOME` selects the workspace; `hpr doctor` shows Codex login state.
- English README is now the default (`README.md`), Korean in `README.ko.md`; 60-second start, live-output sample, how-it-works diagram, troubleshooting table.
- `--lang ko|en`: full English prompt set (14 files) with language-aware sections, markers and lint; the language is fixed in the run manifest.
- `--preset lean` for subscription accounts (2 critics, 2 drafts, smaller caps); per-tier default budgets (light 1.2 M, full 3.5 M input tokens).
- Usage ledger `research/usage-ledger.jsonl` (every call) with `hpr usage` (per day / per run) and `--backfill` for older runs.
- Usage-limit detection: a Codex call that fails with a usage/rate-limit message stops the run without burning the retry, writes `state.json` (`usage_limit`, reset hint) and tells you how to resume; `run`/`resume --at 'HH:MM'` waits for the reset. `scripts/run-test-plan.sh` runs the pre-release test plan with lean presets and budgets.
- `install-skill --yes` copies the Codex skill; mock backend now reports approximate tokens so budget logic is testable (15 tests).

## 0.2.0 - 2026-09-13
- Full tier: depth loci → parallel investigators → 3 angle drafts → synthesis → 4 critics → patch → cite-check → polish.
- Codex scout search (`codex --search`), DuckDuckGo query variants, arXiv/OpenAlex (`--scholar`).
- Published-date and canonical-URL extraction; source independence clustering; provenance table in final report.
- Token accounting from `--json` events; `--ignore-user-config` default (measured 119,520 → 18,781 input tokens per call).
- Read-only vault MCP server (stdio, 6 tools).

## 0.1.0 - 2026-09-13
- Light tier MVP: search → fetch → analyst → writer → 3 critics → patch → cite-check → lint. Mock backend tests.

## 2026-09-14 후속 1–7

- 알려진 형식 오지적과 중복 비평을 줄이고 Light 비평 통합을 선택 기능으로 추가.
- 원자 주장 범위, 블라인드 검토 자료와 전체 주장 수동 판정 경계, 현실형 합성 입력 6건 추가.
- 허용한 정책만 바꾼 비교 검증과 실행별 단계 비용·중단 이유 표시 추가.
- 실제 정확도 및 토큰 절감률은 후속 통제 실험 결과와 구분.

## 2026-09-14 정책 실측 후속

- 승인된 정책 실측 6회 결과·비용·블라인드 모델 검토 한계 공개.
- 인용 뒤 판단 표식과 같은 줄 후속 사실 보존, 여러 공백 분리 회귀 수정.
- 통합 비평 일괄 파일 읽기, 세부 주장 범위 안내와 누락 사유 표시 보완. 수정 후 실제 절감률은 미측정.
