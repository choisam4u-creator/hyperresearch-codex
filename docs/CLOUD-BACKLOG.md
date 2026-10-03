# 클라우드 회차 작업 목록

위에서부터 한 회차에 1~2개씩 처리한다. 끝난 항목은 [x]로 바꾸고 회차 요약은 `docs/CLOUD-NOTES.md`에 적는다.

- [x] README 첫 화면: 무엇을 해 주나 한 줄 / 설치 3줄 / 첫 실행 예시 / 결과 예시, 한국어는 README.ko.md (2026-10-02, "At a glance"/"한눈에 보기" 절 추가)
- [x] API 키 없이 도는 단위 시험(오케스트레이션·예산·원장·cite-check 로직, codex exec는 가짜로 대체) + GitHub Actions CI (2026-10-02 확인: 기존 `tests/` 463개가 `HPR_BACKEND=mock`으로 통과, `.github/workflows/tests.yml`이 3.11~3.13에서 실행. 새 코드 없음)
- [x] LICENSE·CONTRIBUTING·SECURITY·이슈 템플릿 점검 (2026-10-03: SECURITY 지원 버전 0.5.x로 갱신, 보안 신고용 `ISSUE_TEMPLATE/config.yml` 추가, PR 템플릿 시험 명령을 전체 mock 묶음으로, 피드백 템플릿 버전 예시 갱신. LICENSE MIT·pyproject 일치 확인)
- [x] examples/: 작은 질문 1개로 파이프라인 단계별 산출물 예시(가짜 응답 사용) (2026-10-03, `examples/pipeline-walkthrough/`, `python -m evals.walkthrough`로 재생성)
- [ ] CHANGELOG와 다음 버전 준비
- [ ] 공개 전 점검: 비밀 값·개인 경로가 저장소나 git 기록에 있는지 목록 보고(지우지 말고 보고만)
- [x] 품질 평가 기반 `evals/`(고정 질문 6개·기록 응답·5개 항목 점수·CI) (2026-10-03, 기준선 76.0 → 95.6)
- [ ] 품질: 인용 문장의 수치가 인용 원문에 없으면 문장 끝에 `(출처 불일치)` 표시 — 근거: evals 주장-출처 일치 90.4가 최저, `verify_report`의 numeric 이슈가 검증 상태 절에만 있고 본문 문장에는 경고가 없음
- [ ] 품질: 답·근거·한계 절의 인용·표시 없는 사실 문장에 `(출처 없음)` 자동 표시 — 근거: evals 표시 없는 미검증 주장 90.6, ko-battery-recycling·en-hybrid-work에서 4문장
- [ ] 품질: 결정 검사가 빈 한계 절 제목만 붙일 때 분석 단계의 gaps·반대 근거로 한 줄 이상 채우거나 '확인된 한계 없음(검토 필요)'으로 명시 — 근거: en-hybrid-work 구조 83.3
- [ ] 평가: 실제 codex 응답을 익명화해 evals case로 추가(Mac에서 수집) — 근거: 현재 응답 픽스처는 손으로 쓴 결함 사례뿐
