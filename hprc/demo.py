"""네트워크나 모델 호출 없이 설치 상태를 둘러보는 합성 데모."""
import json


def demo_payload() -> dict:
    return {
        "demo": "synthetic_preview",
        "research_run": False,
        "quality_proof": False,
        "network_calls": 0,
        "model_calls": 0,
        "preview": {
            "report_status": "review_required",
            "claims": 2,
            "supported_claims": 1,
            "unchecked_claims": 1,
        },
    }


def render_demo() -> str:
    heading = "합성 데모 미리보기 — 실제 조사 결과나 품질 증명이 아닙니다."
    report = ("\n\n[합성 보고서]\n합성 출처 S1은 예시 실험의 성공률이 60%라고 적고 있습니다. [S1]\n"
              "이 문장은 데모용 가상 자료를 요약한 것이며 현실의 사실이 아닙니다.")
    review = ("\n\n[합성 검토]\n수정 전: 예시 실험은 항상 성공합니다.\n"
              "⚠ 검토: S1의 60%와 충돌하므로 과장된 문장입니다.\n"
              "수정 후: 합성 출처 S1에서 예시 실험의 성공률은 60%입니다. [S1]")
    return heading + "\n" + json.dumps(demo_payload(), ensure_ascii=False, sort_keys=True, indent=2) + report + review
