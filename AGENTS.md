# hyperresearch-codex Agent Rules

이 폴더는 Codex 전용 리서치 도구다. 리서치는 `python3 hpr.py run "질문"` 으로만 시작하고, 단계를 모델이 직접 밟지 않는다.

- 산출물은 `research/runs/<run_id>/` 와 `research/notes/` 아래에만 생긴다. 다른 프로젝트 파일을 고치지 않는다.
- 게시·전송·CMS·캘린더·계정·결제는 이 도구의 범위 밖이다. 보고서는 후보이며 사람이 읽고 채택한다.
- 모델 호출은 `codex exec` 읽기전용 샌드박스 + JSON 스키마로만 한다. 파일 쓰기는 파이썬(`hprc/`)만 한다.
- 실행 전 `python3 hpr.py doctor`. 사용량 한도에 걸리면 우회하지 않고 멈춘다.
- 모델 단계 동시 실행은 기본 최대 2개다. 현재 `hprc/pipeline.py`는 조사·초안·비평을 `ThreadPoolExecutor`로 병렬 처리하며, `hprc/config.py`의 tier별 `parallel=2`를 사용한다. HTTP 수집의 별도 `fetch.parallel=4`와 구분한다. 새 설정으로 한도를 늘리지 않는다.
