"""설치된 wheel만으로 네트워크 없는 mock Light 파이프라인을 확인한다."""
import hashlib
import json
import os
import site
import tempfile
from pathlib import Path
from unittest import mock


def _assert_installed_package(module_file: str) -> None:
    path = Path(module_file).resolve()
    site_roots = [Path(p).resolve() for p in site.getsitepackages()]
    assert any(root == path or root in path.parents for root in site_roots), path
    assert "hyperresearch-codex" not in str(path.parent.parent), path


def _page(url: str, title: str, body: str) -> dict:
    return {"url": url, "final_url": url, "title": title, "domain": "example.test",
            "published": "2026-01-01", "published_source": "synthetic", "modified": "",
            "modified_source": "", "canonical": url, "via": "user", "official": True,
            "status": 200, "error": "", "text": body,
            "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest()}


def main() -> None:
    os.environ["HPR_BACKEND"] = "mock"
    from hprc import fetch, pipeline, scholar, search
    import hprc

    _assert_installed_package(hprc.__file__)
    preserved = Path(tempfile.mkdtemp(prefix="hpr-wheel-smoke-"))
    (preserved / "research").mkdir()
    urls = preserved / "urls.txt"
    urls.write_text("https://example.test/one\nhttps://example.test/two\n", encoding="utf-8")
    body = "합성 고정 본문입니다. " * 80
    pages = [_page("https://example.test/one", "첫 출처", body),
             _page("https://example.test/two", "둘째 출처", body + "추가 근거입니다. ")]

    def no_network(*args, **kwargs):
        raise AssertionError("wheel smoke attempted network access")

    def fake_fetch_all(candidates, config):
        assert {row["url"] for row in candidates} == {page["url"] for page in pages}
        return pages

    run_id = "wheel-smoke"
    with mock.patch.object(pipeline, "fetch_all", side_effect=fake_fetch_all), \
         mock.patch.object(search, "duckduckgo", side_effect=no_network), \
         mock.patch.object(search, "searxng", side_effect=no_network), \
         mock.patch.object(scholar, "arxiv", side_effect=no_network), \
         mock.patch.object(scholar, "openalex", side_effect=no_network), \
         mock.patch.object(fetch.httpx, "Client", side_effect=no_network), \
         mock.patch.object(search.httpx, "get", side_effect=no_network), \
         mock.patch.object(scholar.httpx, "get", side_effect=no_network):
        final = pipeline.run(preserved, "합성 출처에서 확인할 수 있는 내용은?", "light",
                             urls_file=str(urls), run_id=run_id, no_search=True, quiet=True)
        assert final.is_file(), final
        manifest = json.loads((preserved / "research/runs" / run_id / "manifest.json").read_text())
        calls_before = len(manifest["usage"])
        resumed = pipeline.run(preserved, "합성 출처에서 확인할 수 있는 내용은?", "light",
                               run_id=run_id, no_search=True, quiet=True)
        assert resumed == final and resumed.is_file()
        manifest_after = json.loads((preserved / "research/runs" / run_id / "manifest.json").read_text())
        assert calls_before > 0
        assert len(manifest_after["usage"]) == calls_before, (calls_before, len(manifest_after["usage"]))

    print(f"wheel_smoke=ok root={preserved} model_calls=0 resume_calls=0")


if __name__ == "__main__":
    main()
