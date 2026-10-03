# 클라우드 회차 작업 목록

위에서부터 한 회차에 1~2개씩 처리한다. 끝난 항목은 [x]로 바꾸고 회차 요약은 `docs/CLOUD-NOTES.md`에 적는다.

- [x] README 첫 화면: 무엇을 해 주나 한 줄 / 설치 3줄 / 첫 실행 예시 / 결과 예시, 한국어는 README.ko.md (2026-10-02, "At a glance"/"한눈에 보기" 절 추가)
- [x] API 키 없이 도는 단위 시험(오케스트레이션·예산·원장·cite-check 로직, codex exec는 가짜로 대체) + GitHub Actions CI (2026-10-02 확인: 기존 `tests/` 463개가 `HPR_BACKEND=mock`으로 통과, `.github/workflows/tests.yml`이 3.11~3.13에서 실행. 새 코드 없음)
- [x] LICENSE·CONTRIBUTING·SECURITY·이슈 템플릿 점검 (2026-10-03: SECURITY 지원 버전 0.5.x로 갱신, 보안 신고용 `ISSUE_TEMPLATE/config.yml` 추가, PR 템플릿 시험 명령을 전체 mock 묶음으로, 피드백 템플릿 버전 예시 갱신. LICENSE MIT·pyproject 일치 확인)
- [ ] examples/: 작은 질문 1개로 파이프라인 단계별 산출물 예시(가짜 응답 사용)
- [ ] CHANGELOG와 다음 버전 준비
- [ ] 공개 전 점검: 비밀 값·개인 경로가 저장소나 git 기록에 있는지 목록 보고(지우지 말고 보고만)
