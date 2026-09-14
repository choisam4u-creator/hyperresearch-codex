# 입력 패킷 보류 질문 실측 — 2026-09-14

실제 연구 실행 12/12회. 개발 질문에서 사용하지 않은 고정 합성 질문2개를 baseline/packet 각각3회 반복했다. 이 표본에서 packet 총 입력+출력 토큰 변화는 **-3.18%**다. 토큰 결과만으로 같은 품질의 절감이나 일반 성능을 주장하지 않는다.

| 조건 | 입력+출력 토큰 | 순차 실행 시간 합 | Astra 통과/미확정/실패 |
|---|---:|---:|---|
| baseline | 1,476,625 | 1216.7초 | 1/5/0 |
| packet | 1,429,713 | 966.2초 | 0/5/1 |

총 2,906,338토큰. 캐시 입력은 입력 합계에 이미 포함된다. 유지보수·독립 검토 대화의 토큰과 시간, 구독 잔량·청구액은 측정 범위 밖이다.

## 실행별 결과

| 질문/반복 | 조건 | 입력+출력 | 문자 수 | 공백 분리 단어 수 | 품질 | 보고서 |
|---|---|---:|---:|---:|---|---|
| real-ko-missing / 1 | baseline | 227,919 | 2,738 | 636 | 미확정 | [원본](real-ko-missing-r1-baseline.md) |
| real-ko-missing / 1 | packet | 230,472 | 2,816 | 665 | 미확정 | [원본](real-ko-missing-r1-packet.md) |
| real-ko-missing / 2 | packet | 210,993 | 2,810 | 644 | 미확정 | [원본](real-ko-missing-r2-packet.md) |
| real-ko-missing / 2 | baseline | 226,562 | 2,588 | 611 | 통과 | [원본](real-ko-missing-r2-baseline.md) |
| real-ko-missing / 3 | baseline | 285,110 | 2,641 | 607 | 미확정 | [원본](real-ko-missing-r3-baseline.md) |
| real-ko-missing / 3 | packet | 229,901 | 2,631 | 630 | 미확정 | [원본](real-ko-missing-r3-packet.md) |
| real-en-long / 1 | packet | 253,521 | 5,489 | 730 | 미확정 | [원본](real-en-long-r1-packet.md) |
| real-en-long / 1 | baseline | 251,077 | 4,902 | 673 | 미확정 | [원본](real-en-long-r1-baseline.md) |
| real-en-long / 2 | baseline | 233,508 | 5,440 | 765 | 미확정 | [원본](real-en-long-r2-baseline.md) |
| real-en-long / 2 | packet | 252,345 | 5,130 | 712 | 실패 | [원본](real-en-long-r2-packet.md) |
| real-en-long / 3 | packet | 252,481 | 5,354 | 743 | 미확정 | [원본](real-en-long-r3-packet.md) |
| real-en-long / 3 | baseline | 252,449 | 4,914 | 655 | 미확정 | [원본](real-en-long-r3-baseline.md) |

목표는 동일한700단어다. 한국어와 영어의 공백 분리 단어 수는 같은 언어학적 분량 지표가 아니다. 원본 보고서에는 오류가 있을 수 있고, 출처는 실재 기관·제품에 관한 조사 결과가 아닌 합성 자료다.

## 쌍별 토큰 변화

| 질문 | 반복 | packet 변화 |
|---|---:|---:|
| real-ko-missing | 1 | +1.12% |
| real-ko-missing | 2 | -6.87% |
| real-ko-missing | 3 | -19.36% |
| real-en-long | 1 | +0.97% |
| real-en-long | 2 | +8.07% |
| real-en-long | 3 | +0.01% |

6쌍 중4쌍은 증가하고2쌍은 감소했다. 질문2개의 합계 감소를 일반 절감률로 해석하지 않는다.

## 고정 조건과 재현

- 연구 코드 `53e6b790c79048edd782240e20374fc27cb6fec2`, CLI `0.154.0-alpha.6.2`, macOS.
- `realistic-synthetic-v1` holdout `real-ko-missing`, `real-en-long`. 외부 검색·다운로드 없는 replay. 정답은 실행 입력과 분리.
- Light lean,700단어, comparison 형식, economy 역할 고정, routing OFF. packet_inputs만 false/true이며 나머지 설정 동일.
- 질문별 반복마다 첫 조건을 교대하고 두 번째 질문에서는 시작 조건을 뒤집었다. 완전 무작위 실험은 아니다.
- 실행당50만·합계600만 토큰 중단 기준, 최대8호출, 재시도0. 진행 중 호출의 초과 가능성이 있으므로 강제 청구 상한이 아니다.
- `status=ok`는 보고서 생성 상태이고 정확성 통과가 아니다. 파이프라인 경고와 블라인드 판정은 records.json에서 별도로 보존한다.
- 사전 계획과 실제 원문·설정·모델/역할·사용량을 검사했다. 실패/중단을 제외하지 않으며 자동 집계는 품질을 승인하지 않는다.

공개 [plan.json](plan.json)은 개인 입력 경로를 바꾼 사본이다. 원본 계획의 해시는 `original_plan_sha256`으로 남겼다. 외부 사전등록 서비스에 등록한 실험은 아니다.

`harness/execute_followup.py`와 `harness/followup_runner.py`는 실측 당시 비공개 보조 실행기의 바이트를 그대로 공개한 사본이다. 두 SHA는 계획의 harness_hashes와 일치한다. 재현하려면 위 연구 코드를 별도 깨끗한 checkout에 준비하고 두 파일을 그 checkout의 무시되는 `docs/internal/reproduction/`에 복사한다. 현재 공개 사본 계획을 직접 실행하지 말고 해당 환경에서 새 계획을 만든다.

```sh
python3 docs/internal/reproduction/execute_followup.py --study phase3_holdout_packet > docs/internal/reproduction/plan.json
# 아래 실제 호출은 새로운 사용자 예산 승인 및 doctor 확인 후에만 실행한다.
python3 docs/internal/reproduction/execute_followup.py --study phase3_holdout_packet --execute --plan docs/internal/reproduction/plan.json --approved-total-tokens 6000000 --output research/experiments/holdout-new
```

모델 출력·서비스 변화로 수치의 완전 일치는 보장하지 않는다. 현재 버전에서 새 계획을 만들면 새로운 코드 조건의 별도 실험이다.

## 품질과 해석 한계

조건 이름을 숨긴 질문·원문·보고서를 단일 Astra가 전체 본문 단위로 검토했다. 반복 등장한 원자 사실도 각각 세었으므로 항목 수를 독립 사실 수나 일반 정확도로 바꾸지 않는다. 보고서·출처 SHA와 모든 인용 위치의 결속 검사는 의미 판단의 완전성이나 정확성을 증명하지 않는다.

이 질문2개에서 얻은 결과는 개발 질문 실험과 분리한다. 보류 결과를 보고 코드를 튜닝한 뒤 같은 자료를 새로운 독립 평가로 재사용하지 않는다. 원본 Hyperresearch 대비 우위, 다른 모델·실제 웹 검색·블로그 운영 품질은 검증하지 않았다.

보류 baseline은 통과1·미확정5, packet은 미확정5·실패1이었다. packet 보고서1개는 원문에 있는21·17·12·8건의 교정 내역을 충분히 제공되지 않았다고 잘못 설명했다. 일부 보고서에는 제공된 본문만으로 확인할 수 없는 ‘자료가 잘렸다’ 진술이나 통계의 전문창구 이동 제외 조건 누락도 있었다. 따라서 이 합계 토큰 감소를 품질 동등성이나 품질 향상으로 표시하지 않는다.

## 감사 자료

- [실행별 원시 사용량·호출·길이·판정 연결](records.json)
- [쌍별 토큰 차이와 조건 검사](summary.json)
- [블라인드 판정 목록과 파일 해시](quality.json)
- `reviews/`: 검토 입력과 전체 판정. 원본 실행 로그와 블로그 운영 자료는 비공개 보존.
