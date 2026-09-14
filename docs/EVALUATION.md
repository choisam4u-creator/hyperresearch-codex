# 합성 평가 harness

`tests/fixtures/evaluation_cases.json`은 한국어 사실형·영어 비교형·한국어 논쟁형의 고정 합성 입력이다. 각 case는 질문, 합성 출처, 보고서에 문자 그대로 있어야 하는 문장, 기대 검사 수를 가진다. 이 파일은 실제 웹 출처나 실제 모델 평가 결과가 아니다.

평가는 네트워크와 모델 호출 없이, 명시한 실행 폴더의 `final_report.md`(없으면 `report.md`), `manifest.json`, `sources.json`과 연결 노트, 선택적 `quality.json`을 읽는다.

CLI는 case의 `prompt`가 `manifest.json`과 같고, `sources.json`이 가리키는 각 노트 원문이 case의 합성 출처와 같을 때만 실행한다. 따라서 임의 실행 폴더에 case 이름만 덮어써 비교할 수 없다. 노트의 자동 제목 래퍼와 끝 개행만 제거한 본문을 비교한다.

```bash
python -m hprc.evaluation \
  --cases tests/fixtures/evaluation_cases.json \
  --case facts-ko-v1 \
  --run-dir /absolute/path/to/research/runs/example \
  --output /absolute/path/to/review/evaluation.json \
  --model-config '{"label":"candidate-a"}'
```

`--model-config`는 사용자가 붙이는 비교 라벨이며 실제 실행 설정을 검증하지 않는다. 결과에는 manifest usage에서 읽은 backend·model·effort 목록도 별도로 남긴다. `required_text_coverage`는 required 문구가 보고서에 문자열로 관찰된 비율일 뿐 사실 정확도 검증이 아니다. `compare(left, right)`는 `case_id`, 입력 해시, 라벨, 실제 usage 모델 목록이 모두 같을 때만 토큰·시간·검사 수 차이를 계산한다. 완료 시각이 없는 manifest의 elapsed 값은 `null`이며 비교 차이도 계산하지 않는다. 합성 case의 전후 비교는 실제 성능 향상이나 실제 비용 절감을 증명하지 않는다.

실제 비용·품질 평가는 새 입력과 예산이 필요하며, 모델 호출 전 사용자 승인이 필요하다. Phase 6에서는 harness와 fixture만 검증했고 실제 모델 실측은 수행하지 않았다.

## Phase 8 고정 입력과 토큰당 품질 평가

`benchmark_inputs.json`은 한국어 12개·영어 12개(개발 16/보류 8)의 합성 질문·출처·기준 시각을 갖는다. `benchmark_answers.json`은 별도 정답이며 모델 입력에 넣지 않는다. 정상/오류 각 100개의 변형 자료도 입력과 정답을 분리했다. 공개 저장소의 보류 자료는 개발 규약상 분리이며 비공개 블라인드 평가를 보장하지 않는다.

```bash
HPR_BACKEND=mock hpr run "두 고정 사실을 출처별로 짧게 확인하라." \
  --tier light --lang ko --replay tests/fixtures/benchmark_inputs.json --case fact-ko-01
```

이 명령은 mock으로 고정 원문을 넣어 실행한다. `HPR_BACKEND=mock`을 빼면 실제 모델을 호출하므로 별도 실험 예산이 필요하다. replay는 질문·언어·출처 해시·기준 날짜를 확인하며 검색/HTTP 수집 없이 같은 자료를 사용한다. 재개도 저장한 입력을 사용한다. 짧은 합성 원문은 일반 수집 길이 필터로 버리지 않는다.

새 benchmark의 의미 판정 평가는 Python API `load_benchmark`, `evaluate_adjudications`, `evaluate`, `runtime_metadata_from_manifest`, `compare`, `summarize_reports`로 제공한다. 기존 CLI는 구형 문자열 평가도 유지하며 아래 선택 옵션으로 새 benchmark 판정을 지원한다. 호출 예시는 `tests/test_benchmark.py`에 있다.

`evaluate`에는 `benchmark_answer`, `submitted_adjudications`, `adjudication_report_sha256`를 전달한다. 판정의 해시가 보고서와 다르면 거부하고, 해시가 없으면 품질 통과 여부를 `null`로 둔다. 중복·미등록 판정 ID를 거부하며 필요한 근거 ID도 검사한다. 정답 문자열 포함 여부를 사실 정확도로 계산하지 않는다. 판정 자체의 정확성을 보장하려면 독립 검토가 필요하다.

`compare(..., mode="code_only")`는 동일 입력·시각·모델·프롬프트·출력 요구·유효 설정에서 코드 차이만 비교한다. `mode="model_routing"`은 코드·프롬프트·모델 외 설정을 고정한 역할 배정 비교다. 명시 모드는 완전한 실행 메타와 호출별 구성 일치를 요구한다. 실행 중 예산 변경, 누락된 구성 기록 등으로 조건을 확인할 수 없으면 거부한다. 기본 구형 비교 모드는 이전 호환 규칙을 유지하므로 통제 실험에는 명시 모드를 사용한다.

`total_tokens_per_quality_qualified_report`의 분자는 제출된 모든 실행의 입력+출력이며 실패·재시도·품질 미달도 포함한다. 캐시는 입력에 포함되므로 중복 합산하지 않는다. 미측정 호출이 하나라도 있거나 통과 보고서가 없으면 이 값은 `null`이다. `known_total_tokens_per_quality_qualified_report`는 측정된 부분만 나타내는 별도 값이다. 자동 `quality.json` 통과만으로 benchmark 의미 품질 통과를 선언하지 않는다.

현재 검증은 자료 생성·계약·모의 통합 실행이다. 24개 실제 모델 평가나 200개 오류 판별 성능을 측정한 결과가 아니다.


## 분리 정답과 독립 판정 CLI

```bash
python -m hprc.evaluation \
  --cases tests/fixtures/benchmark_inputs.json \
  --answers tests/fixtures/benchmark_answers.json \
  --case fact-ko-01 --run-dir /absolute/research/runs/RUN_ID \
  --adjudications /absolute/review/adjudications.json \
  --output /absolute/review/evaluation.json
```

판정 파일은 정확히 `{"report_sha256":"보고서 SHA-256","items":[...]}` 형태다. 각 item은 독립 검토자가 기록한 `item_id`, `verdict`, `evidence_ids`다. 정답 파일에서 판정을 자동 복사하지 않는다. `--adjudications`를 생략하면 품질은 unknown으로 남는다. 정답은 평가 프로세스만 읽으며 리서치 입력에 넣지 않는다.

`--answers`를 지정하면 선택 case와 실행의 질문·언어·기준 시각·저장 원문·frozen_input.json·입력 해시를 대조한다. `--compare /absolute/review/baseline.json --comparison-mode model_routing` 또는 `code_only`를 함께 지정하면 엄격한 구성 비교를 저장한다. 모델이나 네트워크는 호출하지 않는다. 불일치는 종료코드 2이며 보고서의 사실 정확도를 임의로 인증하지 않는다.
