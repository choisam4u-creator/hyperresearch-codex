"""hyperresearch-codex: Codex 전용 리서치 파이프라인 (Light 모드 MVP).

원리: 지휘자는 파이썬, 모델(codex exec)은 단계마다 한 가지 판단만 한다.
모든 모델 호출은 읽기전용 샌드박스 + JSON 스키마 출력이며, 파일 쓰기는 파이썬만 한다.
"""
__version__ = "0.3.0"
