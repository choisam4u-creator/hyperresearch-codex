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
