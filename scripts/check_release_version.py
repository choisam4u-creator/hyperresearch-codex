"""릴리스 태그와 패키지 버전이 같은지 검사한다(release.yml과 시험이 함께 쓴다).

태그는 `v` + PEP 440 공개 버전이다. 정식(`v0.5.0`)과 사전배포(`v0.5.0b1`, `v0.5.0a2`,
`v0.5.0rc1`)를 받고, 로컬 버전·dev·post·`v0.5`처럼 자리가 빠진 형식은 거절한다.
pyproject.toml, hprc/__init__.py의 __version__, CITATION.cff의 version이 모두 같아야 한다.
"""
from __future__ import annotations

import pathlib
import re
import sys
import tomllib

TAG_RE = re.compile(r"v([0-9]+\.[0-9]+\.[0-9]+(?:(?:a|b|rc)[0-9]+)?)")


def tag_version(tag: str) -> str:
    match = TAG_RE.fullmatch(tag)
    if not match:
        raise ValueError(f"invalid release tag: {tag}")
    return match.group(1)


def package_versions(root: pathlib.Path) -> dict[str, str]:
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    init = re.search(r'^__version__ = "([^"]+)"$', (root / "hprc" / "__init__.py").read_text(encoding="utf-8"), re.M)
    citation = re.search(r"^version: (\S+)$", (root / "CITATION.cff").read_text(encoding="utf-8"), re.M)
    return {
        "pyproject.toml": pyproject,
        "hprc/__init__.py": init.group(1) if init else "",
        "CITATION.cff": citation.group(1) if citation else "",
    }


def check(tag: str, root: pathlib.Path) -> str:
    version = tag_version(tag)
    for where, found in package_versions(root).items():
        if found != version:
            raise ValueError(f"tag {tag} does not match {where} version {found or '(missing)'}")
    return version


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: check_release_version.py <tag>", file=sys.stderr)
        return 2
    try:
        version = check(argv[1], pathlib.Path(__file__).resolve().parent.parent)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"release {argv[1]} matches package version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
