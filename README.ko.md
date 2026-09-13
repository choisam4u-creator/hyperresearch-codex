# hyperresearch-codex (한국어)

영문 README(기본): [README.md](README.md) · 상태: 베타 0.3.1 · 저자 samchoi

Codex 전용 리서치 파이프라인. 질문 하나 → 출처 수집(Codex 정찰 검색·DuckDuckGo·학술 API) → 분석 → (Full: 깊이 조사·초안 3개·종합) → 비평 → 부분 수정 → 인용 표본 검사 → 다듬기 → 출처 상세표가 붙은 보고서. 이전 조사는 창고(vault)에 남아 다음 조사와 Codex 세션(MCP)에서 재사용된다.

[jordan-gibbs/hyperresearch](https://github.com/jordan-gibbs/hyperresearch) (MIT, Claude Code 전용)에서 영감을 받아 samchoi 가 Codex 전용으로 새로 만들었다. 지휘 장치를 파이썬으로 옮기고 모델 호출을 `codex exec` 로 바꾼 별도 구현이며 코드·프롬프트를 공유하지 않는다.

## 원리 세 줄

1. **지휘자는 파이썬, 모델은 일꾼.** 단계 순서·병렬·재시도·중단 복구는 `hprc/pipeline.py` 와 `manifest.json` 이 맡는다.
2. **모델은 읽기만, 쓰기는 파이썬만.** 모든 호출이 `codex exec -s read-only --output-schema` 다. 수정도 "find→replace 덩어리"로 받아 파이썬이 적용하고 상한을 검사한다.
3. **모델 출력은 게이트를 통과해야 한다.** 질문 원문 보존, 없는 출처 인용 차단, 초안에 없는 문장을 인용한 비평 폐기, 수정 비율 상한(부분 수정 30%·다듬기 15%), 인용 표본 검사, 다듬기가 인용 표시를 지우면 거부.

## 다른 도구와 비교

2026-09-13 확인. 이 도구의 수치는 실측(아래 *비용*), 다른 도구의 수치는 각자의 README·예시에서 가져왔다.

| | **hyperresearch-codex** (이 도구) | [jordan-gibbs/hyperresearch](https://github.com/jordan-gibbs/hyperresearch) | [insane-research-codex](https://github.com/fivetaku/gptaku-plugins-codex) | ChatGPT Deep Research |
|---|---|---|---|---|
| 돌아가는 곳 | Codex CLI(구독·API) + Python 3.11 | Claude Code. 원본에도 Codex 설치 경로가 검토 중([PR #63](https://github.com/jordan-gibbs/hyperresearch/pull/63), 2026-09-11 원칙 수락) | Codex 플러그인 마켓(`codex plugin marketplace add …`) | ChatGPT 앱 |
| 단계를 누가 밟나 | 파이썬. 모델은 읽기 전용 `codex exec` + JSON 스키마 안에서 판단만 | Claude Code 스킬·서브에이전트 | Codex 스킬 + 보조 스크립트, 조사 에이전트 병렬 가능 | 서비스 |
| 결과물 | 1천~3.5천 단어 출처 브리프 + 출처 상세표 + 인용 검사 줄. 노트는 디스크의 FTS5 창고에 남고 읽기 전용 MCP 로 재사용 | 1만 단어급 서베이(예시 보고서 11,209단어·출처 97개) | 주장 장부·출처 등급 A–E·`RESEARCH/` 상태가 붙은 인용 중심 보고서 | 인용 달린 채팅 답 |
| 눈으로 확인 가능한 검증 | 없는 출처 인용 차단, 비평 인용문 존재 확인, 수정 ≤30%·다듬기 ≤15%, (판단) 표시, 인용 표본 검사, 린트 | 다단계 비평 | `validate_ledger.py` → `verify_report.py` → `eval_report.py` | 없음 |
| 실측 비용·시간 | Light lean 입력 53만~69만 토큰·5~6분, Full lean 127만·11분, Full 표준 258만·29분 | Full 1회 약 2시간(저자 예시), 토큰 미공개 | 미공개 | 구독에 포함 |
| 사용량 통제 | 실행별 예산 정지→재개, 토큰 장부, `--at HH:MM` 리셋 예약 | – | – | – |
| 언어 | 한국어·영어 프롬프트 세트 | 영어 | 영어(채팅 우선) | 다수 |
| 이럴 때 고른다 | Codex 로 몇 분 안에 재현·감사 가능한 브리프가 필요하고 구독 한도를 지켜봐야 할 때 | Claude Code 를 쓰고 긴 서베이가 필요할 때 | 마켓 한 줄 설치와 더 넓은 단계 모델을 Codex 안에서 원할 때 | 설치 0 을 원할 때 |

## 필요한 것

- Codex CLI 로그인 상태(`codex login`). Codex CLI 0.153.4 와 `gpt-6-astra` 로 실측. 다른 버전은 프롬프트 손질이 필요할 수 있다.
- `hpr doctor`에서는 `codex --version`와 `codex login status`를 timeout 제한으로 검사해 `0.153.4`와 버전 불일치 시 경고를 띄우고, 버전/로그인 진단 실패는 실패 사유를 명확히 표시합니다.
- Python 3.11 이상, `httpx`·`pypdf`(`pip install` 로 자동), FTS5 가 있는 SQLite(macOS·대부분의 Linux 기본).
- macOS 에서 실측. Linux 는 CI 로만, Windows 는 미확인.

## 사용

```bash
python3 hpr.py doctor
python3 hpr.py run "질문 원문" --dry-run             # 실행 전 단계·호출 수·대략 비용 보기
python3 hpr.py run "질문 원문"                       # Light (기본): Codex 정찰 + DuckDuckGo. 진행은 화면에 바로 표시
python3 hpr.py run "질문 원문" --budget 1500000      # 누적 입력 토큰 상한. 넘으면 다음 단계 전에 멈춤(resume 가능)
python3 hpr.py run "질문 원문" --tier full            # Full: 깊이 조사·초안 3개·비평 4·다듬기
python3 hpr.py run "질문" --urls urls.txt --no-search  # 출처를 직접 줄 때
python3 hpr.py run "질문" --scholar                    # arXiv·OpenAlex 후보 추가(키 없음)
python3 hpr.py resume <run_id>                       # 중단 지점부터
python3 hpr.py status                                # 실행별 호출 수·시간·토큰
python3 hpr.py search "키워드"                        # 창고 검색
python3 hpr.py mcp-config                            # Codex 에 창고 MCP 서버 등록용 TOML 출력(등록은 사용자)
python3 hpr.py install-skill --yes                   # ~/.codex/skills 에 스킬 복사
```

결과: `research/runs/<run_id>/final_report.md`. 첫 주석 줄에 출처 수(독립 묶음)·지적 수·인용 미지지 수·린트·호출 수·토큰이 있고, 끝에 "출처 상세(자동 생성)" 표(제목·도메인·게시일·조회일·독립 묶음·경로·1차 여부)가 붙는다.

## 실행 화면

![실제 Light lean 실행의 진행 표시(24초로 압축)](docs/assets/run-light-lean.svg)

## 예시 보고서

실제 실행 결과를 손대지 않고 넣었다(머리 주석 한 줄만 추가). 출처 제목·URL 만 있고 가져온 본문은 없다.

| 파일 | 언어·계층 | 질문 | 실행 요약 |
|---|---|---|---|
| [examples/report-en-light-lean.md](examples/report-en-light-lean.md) | en · light lean | Apple Silicon 통합 메모리로 로컬 이미지 생성 모델을 돌릴 때의 한계와 GGUF 양자화 | 출처 8(1차 8), 지적 7, 인용 미지지 1/5, 판단 2, 호출 7회, 4.8분, 입력 604,783 |
| [examples/report-ko-light-lean.md](examples/report-ko-light-lean.md) | ko · light lean | 티스토리 블로그에 JSON-LD 구조화 데이터를 넣으면 Google 노출에 어떤 영향이 있고 무엇을 주의해야 하나 | 출처 8(1차 6, 실제 인용 5), 지적 3, 인용 미지지 1/5, 판단 2, 호출 7회, 4.6분, 입력 382,829, 도메인 편중 경고(developers.google.com 75%) |
| [examples/report-codex-exec-light.md](examples/report-codex-exec-light.md) | ko · light (v0.1) | `codex exec` 비대화 사용법 | 초기 데모, 형식 변천 참고용 |

## 단계

| 단계 | Light | Full | 누가 |
|---|---|---|---|
| 정찰 검색 (`codex --search`) → 1차 출처 URL | ○ | ○ | Codex(웹 검색) |
| DuckDuckGo 변형 검색 3종, 학술(`--scholar`) | ○ | ○ | 파이썬 |
| 가져오기·본문 추출·게시일·정본 URL·독립성 묶기 | ○ | ○ | 파이썬 |
| 분석(주장·모순·빈틈) | ○ | ○ | Codex |
| 깊이 지점 선정 → 지점별 조사(병렬 2) → interim 노트 | – | ○ | Codex |
| 초안 | 1개 | 3개 관점(병렬 2) → 종합(2회 읽기) | Codex |
| 비평 | 반론·깊이·지시 | + 폭 (병렬 2) | Codex |
| 부분 수정 (30% 상한) | ○ | ○ | Codex 제안 → 파이썬 적용 |
| 인용 표본 검사 | 6 | 10 | Codex |
| 다듬기 (15% 상한, 인용 표시 보존) | – | ○ | Codex 제안 → 파이썬 적용 |
| 린트·출처 상세표·토큰 집계 | ○ | ○ | 파이썬 |

## 언어·프리셋·예산·장부 (v0.3)

- `--lang ko|en`: 프롬프트 세트(`hprc/prompts/<lang>/`)와 보고서 언어·절 이름·"(판단)"/"(judgment)" 표시·린트가 함께 바뀐다. 실행마다 고정되고 resume 때 유지.
- `--preset lean`: 구독 계정용. 비평 2종·초안 2개(Full)·출처 수와 노트 상한 축소·일부 추론 강도 하향. 기본은 standard.
- 실행별 기본 입력 토큰 상한: light 120만, full 350만. 넘으면 **다음 단계 전에** 멈추고 `hpr resume <id> --budget <더 큰 값>`으로 이어 간다.
- 모든 모델 호출은 `research/usage-ledger.jsonl`에 기록된다. `hpr usage [--days N] [--json] [--backfill]`로 날짜별·실행별 합계를 본다. 구독 사용량 창을 관리하는 기준이다.

## 토큰 다이어트 (v0.3)

| 단계 | 받는 입력 |
|---|---|
| 분석가 | 노트 전부(12,000자 상한, 잘리면 truncated 표시) |
| 깊이 지점·초안 | 분석가가 **실제로 인용한 출처만**(초안 8,000자 상한) |
| 종합 | 초안 3개 + interim + 주장 요약 + 발췌. 노트 원문 없음 |
| 비평·수정 | 주장 요약 + 2,500자 발췌 |
| 인용 검사 | 인용된 노트만(6,000자) · "(판단)" 문장 제외 |
| 다듬기 | 보고서만 |

## 비용 (실측, 2026-09-13)

- 호출당 입력 토큰: 사용자 설정 그대로 119,520 → `--ignore-user-config` + 모델 명시 18,781. **6.4배 절감.** 기본값으로 켜져 있다(`codex.ignore_user_config`). 스킬·AGENTS 주입이 빠지므로 모델은 `research/config.json` 의 `default_model`(기본 gpt-6-astra)로 지정된다.
- 정찰 검색 1회: 74.5초, 웹 검색 6회, 입력 380,440(캐시 309,248)·출력 952. 검색 결과 본문이 크다. 정찰이 가장 비싼 단계이므로 출처를 아는 조사는 `--urls --no-search`.
- Light 데모(v0.1, 설정 무시 전): 7분 56초, 호출 7회. v0.2 기본값이면 입력 토큰은 그보다 훨씬 적다(실측은 다음 실행에서 `status` 로 확인).
- **v0.3 Light 실측**(출처 10개, 정찰 제외, 같은 질문): 호출 7회, 6.5분, 입력 539,759(캐시 317,056)·출력 10,777, 요금 상한 ≈$5.9. v0.2 Full 같은 단계 대비 분석 −58%, 초안 −58%, 비평 −86~−88%, 수정 −55%, 인용 검사 −31%.
- **Full v0.3 vs v0.2 (같은 질문, 출처 20, 정찰 포함)**: 호출 18회 동일. 입력 5,181,822 → **2,578,112(−50%)**, 모델 시간 35.6 → 29.4분, 요금 상한 $54.6 → $28.3. 정찰 −73%, 지점·조사 −77~−81%, 비평 −60~−71%, 인용 검사 −72%, 초안 −24~−28%, 종합 −28%. 분석 +30%·수정 +18%는 다이어트 대상이 아닌 단계(노트 길이·지적 18개 증가).
- **v0.2 Full 실측 2건**: 각 호출 18회, 모델 시간 33~36분, 입력 약 505만~518만 토큰(캐시 79~80%), 출력 약 5.2만~5.6만. 노트 20개를 매 단계에 넣는 구조가 원인이며 v0.3에서 줄인다.
- 구독 사용량 한도에 걸리면 멈추고 우회하지 않는다.

## 창고(vault)와 MCP

- 노트 `research/notes/S*.md` (YAML 머리말: id·url·title·domain·published·fetched_at·sha256). 색인 `research/index.sqlite`(FTS5)는 지워도 `sync` 로 복구.
- `python3 hpr.py mcp` 는 표준 라이브러리만 쓰는 stdio MCP 서버다. 도구 6개: search_notes, read_note, list_notes, vault_status, list_runs, read_report. 쓰기 도구는 없다. `read_note` 는 `research/` 밖 경로를 거부한다.
- 등록은 `mcp-config` 출력을 `~/.codex/config.toml` 에 사용자가 직접 넣는다.

## 설정 예 (`research/config.json`)

```json
{"default_model": "gpt-6-astra",
 "models": {"synth": {"effort": "high"}, "critic": {"effort": "medium"}},
 "search": {"providers": ["codex_scout", "duckduckgo"], "preferred_domains": ["developers.openai.com"]},
 "full": {"max_sources": 16, "drafts": 3, "parallel": 2},
 "gates": {"patch_max_ratio": 0.25}}
```

## 검증 상태 (2026-09-13)

| 검사 | 결과 |
|---|---|
| mock 백엔드 + 로컬 HTTP 고정 페이지: Light 8단계, Full 11단계(깊이·초안 3·종합·폭 비평·다듬기), resume 무호출, 게시일 우선순위, 독립성 묶기, 우선순위·중복 제거, 토큰 파싱·명령 조립, MCP 핸드셰이크·경로 거부 | `tests/test_pipeline_mock.py` 28개 통과(실패 경로 7개 포함: 네트워크 차단·잘못된 URL·사용량 한도·로그인 만료·codex 없음·시간 초과) |
| 실제 `codex exec` 최소 호출(읽기전용·스키마) | PASS 12.4s |
| 실제 `codex exec --json --ignore-user-config` 토큰 비교 | 18,781 vs 119,520 |
| 실제 `codex --search exec` 정찰 | 공식 문서 3건(developers.openai.com/codex/noninteractive 등) |
| Light 실제 실행(v0.1 설정) | demo-01: 8분, 출처 8, 지적 4, 표본 6 중 미지지 2 |
| Light lean 실제 실행 5회(v0.3/0.3.1, 예산 70만·80만) | 완주 5/5, 호출 7회, 4.6–6.3분, 입력 38.3만–68.6만(캐시 51–66%), 출력 6.8천–9.4천, 회당 ≈$4.2–7.3 상한. 같은 질문 3회: 지적 8→4→3, 인용 미지지 1→4→1(0.3.1 수정 뒤) (docs/TEST-PLAN.md) |
| Full 실제 실행 | v0.2 2회(ComfyUI·AdSense 질문), v0.3 1회(입력 2,578,112 · v0.2 대비 −50% · 29.4분), 영어 Full lean 1회(1,273,850 · 11.2분 · 미지지 0/6) |
| arXiv·OpenAlex 실제 호출 | 영어 Full lean 실행(`--scholar`)에서 사용. PDF 본문은 pypdf 로 읽음(arXiv 논문 1편 161,228자 확인) |

## 개선 예정

`ROADMAP.md` 참고. 남은 것: 0.3.1 인용 검사 수정의 실제 실행 확인, Windows 확인, PyPI 배포.

## 한계

- 검색 품질은 정찰(Codex 웹 검색)에 크게 의존한다. 정찰이 실패하면 DuckDuckGo 로만 가서 2차 자료가 많아진다.
- 로그인·페이월 자료는 못 읽는다. 오픈액세스 복구(Unpaywall 등)는 없다. PDF 는 `pypdf` 설치 시만.
- 게시일은 페이지 메타 태그 기준이라 없으면 "미표기". 사람이 확인해야 하는 시점 민감 정보다.
- 품질 점수는 없다. 같은 질문을 두 번 돌리면 비평 지적 수가 8→4 로 흔들렸다(실측). 보고서 길이·비용은 안정적이다.

## 구조

```
hpr.py                  CLI
hprc/pipeline.py        Run 클래스: Light/Full 단계, 병렬(2), 재시도 1회, 출처 상세표
hprc/codex_runner.py    codex exec 호출(임시 폴더·읽기전용·스키마·--json 토큰·--search)
hprc/gates.py           게이트
hprc/search.py          DuckDuckGo·URL 목록·우선순위·정규화 중복 제거
hprc/scholar.py         arXiv Atom·OpenAlex
hprc/fetch.py           httpx·html.parser·게시일·정본 URL (+pypdf 선택)
hprc/cluster.py         출처 독립성(정본 URL·8단어 조각 Jaccard)
hprc/vault.py           노트·FTS5
hprc/mcp_server.py      창고 MCP(stdio)
hprc/prompts/*.md       14개 프롬프트 (모델을 바꾸면 여기만 손본다)
hprc/schemas.py         단계별 JSON 스키마
hprc/mock.py            테스트용 가짜 모델
skill/hyperresearch-codex/SKILL.md   Codex 스킬 후보
docs/                   테스트 계획(TEST-PLAN.md)·원본 비교(COMPARISON-drb67.html). docs/internal/ 은 미추적
```
