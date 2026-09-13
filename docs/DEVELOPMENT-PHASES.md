# 페이즈별 개발 계획

2026-09-14 기준. 원본의 기능을 그대로 늘리기보다 짧고 검증 가능한 Codex 브리핑이라는 목적을 유지한다. Phase 1–7은 구현·로컬 검증·외부 검증 대기 범위를 각각 구분한다. 실제 리서치 호출·배포는 구현 승인과 구분한다.

현재 문서는 Phase 2–7의 구현·로컬 검증 범위와 남은 외부 증거를 구분한다. 각 Phase를 일괄 완료로 선언하지 않는다. 실제 리서치 benchmark, 외부 2~3명 설치 피드백, 새 릴리스는 pending이며 Windows run/resume은 CI 실행·검토 전이다.

| 페이즈 | 목표·작업 | 완료 조건 | 실행 비용·의존성 |
|---|---|---|---|
| **1. 근거 보존과 경로 정정** | 불변 출처 스냅샷·실행별 S번호 매핑, run/resume/status/MCP 실행 ID 경계, 날짜 전달, 원본 비교표 정정 | 두 실행의 같은 S1/제목도 이전 본문 보존. 날짜가 모델 입력에 전달. 상위경로·절대경로·외부 symlink 거부. 기존 정상 실행·구형 노트 호환 | mock/임시 파일 검증. 실제 리서치 호출 없음 |
| **2. 외부 자료 처리** | 웹 본문을 데이터로 구분, 위조 경계문자 무력화, URL·redirect·사설주소 정책 | safe source wrapping, redirect·DNS·peer 검사, 정확한 private-host allowlist 회귀 구현. 실제 모델 효과는 pending | 기본은 오프라인 fixture. |
| **3. 최종 보고서 검증** | 생성 완료/검증 통과 상태 분리 | `quality.json`, `review_required`, CLI exit 3, 오프라인 evaluator 구현. evaluator는 사실성 판정기가 아님 | 실제 모델 benchmark pending |
| **4. 누락 근거 보충** | Full에서 중요 gap에 대한 제한적 검색·수집 | 기본 OFF, 명시 시 최대 2 gaps·3 sources, no-search·HardStop·예산 유지 | 고정 질문 실제 검증 pending |
| **5. 기존 자료 재사용** | 새 조사 전 FTS 검색과 immutable note 검증 | 기본 OFF, 신선도·hash·snapshot ID·URL 검증, 색인 재생성 없음 | 적중률·절감량 실측 pending |
| **6. 품질·비용 평가** | 한영 고정 fixture와 실행 메타데이터 비교 | 오프라인 evaluator·합성 fixture 구현. truth/accuracy 보장 없음 | 실제 연구 benchmark와 비용 비교 pending |
| **7. 설치·공개 운영** | wheel skill resource·install-skill, Linux/Windows CI, 피드백 양식 | package resource와 source 원본 동기화 테스트, Windows CI 설정 추가 | Windows CI 실행·검토, 외부 피드백, 릴리스 pending |

각 페이즈는 관련 회귀 테스트와 Astra 최종 검수를 거쳐 로컬 커밋으로 묶는다. GitHub 푸시는 사용자 요청 범위에서 수행한다. 모델 배정은 실행·무결성 수정에 Sol, 자료 처리·파이프라인에 Terra, 문서·설치 보조에 Luna를 기본으로 삼되 실제 난도에 따라 조정한다.

나중에 검토할 확장은 목적별 설명/비교/분석 모드와 DOI·철회 여부·출처 종류의 품질 메타다. 대형 대시보드·수백 출처·장문 전용 모드는 위 검증보다 우선하지 않는다.

기존 노트는 이동하거나 다시 쓰지 않는다. 과거에 이미 덮어쓴 내용은 이 변경만으로 복구되지 않는다. Phase 5 재사용은 기본 OFF이며 fresh immutable note 검증 범위로만 제공한다. 적중률·절감량과 실제 연구 품질은 별도 실측이 필요하다.
