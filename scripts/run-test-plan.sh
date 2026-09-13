#!/bin/sh
# 공개 전 테스트 계획(docs/TEST-PLAN.md)의 실제 실행분을 순서대로 돌린다. 사용량 리셋 직후 한 번에 걸어 두는 용도.
# 각 실행은 lean 프리셋·예산 상한을 쓰고, BLOCKED(한도·예산)면 거기서 멈춘다. 다시 실행하면 완료된 단계는 건너뛴다.
# 사용: sh scripts/run-test-plan.sh [--at HH:MM]
set -u
cd "$(dirname "$0")/.."
AT=""; [ "${1:-}" = "--at" ] && AT="--at $2"
LOG=research/logs/test-plan-$(date +%Y%m%d).log
run() { id="$1"; shift; echo "=== $id $(date '+%H:%M:%S')" | tee -a "$LOG"; python3 hpr.py run "$@" --run-id "$id" $AT >> "$LOG" 2>&1 || { echo "STOP at $id (exit $?)" | tee -a "$LOG"; exit 2; }; AT=""; }
run tp-light-ko-1 "티스토리 블로그에 구조화 데이터(JSON-LD)를 넣으면 Google 검색 노출에 어떤 영향이 있고 무엇을 주의해야 하나?" --tier light --preset lean --budget 700000
run tp-light-en-1 "What are the practical limits of Apple Silicon unified memory for running local image generation models, and how do GGUF quantizations change them?" --tier light --lang en --preset lean --budget 700000
run tp-light-ko-2 "Codex CLI 의 MCP 서버 설정은 어떻게 하고, 읽기 전용 도구만 노출하려면 무엇을 확인해야 하나?" --tier light --preset lean --budget 700000
run tp-light-ko-1b "티스토리 블로그에 구조화 데이터(JSON-LD)를 넣으면 Google 검색 노출에 어떤 영향이 있고 무엇을 주의해야 하나?" --tier light --preset lean --budget 700000
echo "=== 계획 실행 완료 $(date '+%H:%M:%S')" | tee -a "$LOG"; python3 hpr.py usage --days 2 | head -3
