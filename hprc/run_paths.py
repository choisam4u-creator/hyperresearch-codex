"""실행 ID를 프로젝트의 ``research/runs`` 아래 안전한 경로로 바꾼다."""
from pathlib import Path
import unicodedata


class InvalidRunId(ValueError):
    """run_id 또는 실행 저장 경로가 안전한 단일 경로 성분이 아닐 때."""


def runs_directory(root: Path) -> Path:
    """프로젝트 밖을 가리키지 않는, 정규화된 실행 저장 경로를 반환한다."""
    root_path = Path(root).resolve()
    try:
        runs = (root_path / "research" / "runs").resolve()
    except (OSError, RuntimeError) as error:
        raise InvalidRunId(f"실행 저장 경로를 확인할 수 없습니다: {error}") from error
    if not runs.is_relative_to(root_path):
        raise InvalidRunId("실행 저장 경로가 프로젝트 밖을 가리킵니다")
    return runs


def run_directory(root: Path, run_id: str) -> Path:
    """검증한 ``run_id``의 정규화된 실행 디렉터리를 반환한다.

    ``run_id``는 기존 한글 이름을 포함한 단일 경로 성분이어야 한다. 경로
    구문이나 심볼릭 링크를 통해 ``research/runs`` 밖으로 나가면 거부한다.
    """
    if not isinstance(run_id, str):
        raise InvalidRunId("run_id는 문자열이어야 합니다")
    if not run_id or not run_id.strip():
        raise InvalidRunId("run_id는 비어 있을 수 없습니다")
    if run_id in {".", ".."}:
        raise InvalidRunId("run_id에 현재/상위 경로를 사용할 수 없습니다")
    if Path(run_id).is_absolute() or "/" in run_id or "\\" in run_id:
        raise InvalidRunId("run_id는 경로가 아닌 단일 이름이어야 합니다")
    if any(unicodedata.category(char) == "Cc" for char in run_id):
        raise InvalidRunId("run_id에 제어 문자를 사용할 수 없습니다")

    runs = runs_directory(root)
    try:
        candidate = (runs / run_id).resolve()
    except (OSError, RuntimeError) as error:
        raise InvalidRunId(f"run_id 경로를 확인할 수 없습니다: {error}") from error
    if candidate.parent != runs:
        raise InvalidRunId("run_id는 research/runs 바로 아래의 실행 폴더여야 합니다")
    return candidate


__all__ = ["InvalidRunId", "run_directory", "runs_directory"]
