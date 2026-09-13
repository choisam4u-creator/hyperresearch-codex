"""Codex 호출 없이(HPR_BACKEND=mock) 로컬 HTTP 고정 페이지로 Light/Full 파이프라인·게이트·부품을 검증한다."""
import http.server
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hprc import cli, cluster, codex_runner, fetch, gates, pipeline, search, vault  # noqa: E402

PAGE = """<html><head><title>{title}</title><meta property="article:published_time" content="{date}T09:00:00+09:00">
<link rel="canonical" href="{canon}"><script type="application/ld+json">{{"@type":"Article","datePublished":"2020-01-01"}}</script></head>
<body><nav>메뉴 메뉴</nav><article><h1>{title}</h1><p>{body}</p><p>이 문서는 테스트용 고정 페이지이며 충분히 긴 본문을 가지고 있어야 출처로 채택됩니다. {pad}</p></article>
<script>ignored()</script></body></html>"""
PAD = " ".join(f"단어{i}" for i in range(220))


def pad_for(i):
    return PAD if i in (0, 2) else " ".join(f"{i}번문서 고유단어{j}" for j in range(220))


class Server:
    def __init__(self, directory: Path):
        handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=str(directory), **k)
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown(); self.httpd.server_close()


class Base(unittest.TestCase):
    def setUp(self):
        os.environ["HPR_BACKEND"] = "mock"
        self.tmp = Path(tempfile.mkdtemp(prefix="hpr-test-"))
        self.site = self.tmp / "site"; self.site.mkdir()
        pages = [("첫 번째 출처", "강화학습 프레임워크는 게임을 훈련장으로 쓴다.", "2026-09-01", "https://a.example/one"),
                 ("두 번째 출처", "자바스크립트 게임은 브라우저에서 바로 플레이할 수 있다.", "2026-08-15", "https://b.example/two"),
                 ("첫 번째 출처 복사본", "강화학습 프레임워크는 게임을 훈련장으로 쓴다.", "", "https://a.example/one"),
                 ("짧은 페이지", "짧다.", "", "")]
        for i, (title, body, date, canon) in enumerate(pages):
            pad = pad_for(i) if i < 3 else ""
            (self.site / f"p{i}.html").write_text(PAGE.format(title=title, body=body, date=date or "2021-05-05", canon=canon, pad=pad), encoding="utf-8")
        self.server = Server(self.site)
        self.proj = self.tmp / "proj"; self.proj.mkdir()
        shutil.copytree(ROOT / "hprc", self.proj / "hprc")
        self.urls = self.tmp / "urls.txt"
        self.urls.write_text("\n".join(f"http://127.0.0.1:{self.server.port}/p{i}.html" for i in range(4)) + "\n")

    def tearDown(self):
        self.server.stop(); shutil.rmtree(self.tmp, ignore_errors=True)


class LightTests(Base):
    def test_full_light_run(self):
        prompt = "강화학습 프레임워크에서 JS 게임을 쓰면 무엇이 좋은가?"
        out = pipeline.run(self.proj, prompt, "light", urls_file=str(self.urls), run_id="t1", no_search=True)
        text = out.read_text(encoding="utf-8")
        self.assertIn(f"# 질문: {prompt}", text)
        self.assertIn("다만 반대 사례도 있다.", text)                  # 비평 → 부분 수정
        self.assertNotIn("이 문장은 초안에 없습니다", text)             # 지어낸 비평 폐기
        self.assertIn("## 출처 상세(자동 생성)", text)
        self.assertIn("| 2026-09-01 |", text)                        # 게시일 추출
        src = json.loads((self.proj / "research/runs/t1/sources.json").read_text())
        self.assertEqual(3, len(src["sources"]))                     # 짧은 페이지 제외
        self.assertEqual(2, src["independent_groups"])               # 복사본은 같은 묶음
        m = json.loads((self.proj / "research/runs/t1/manifest.json").read_text())
        self.assertEqual({"search", "fetch", "analyst", "draft", "critics", "patch", "citecheck", "final"},
                         {s["name"] for s in m["steps"] if s["status"] in ("ok", "warn")})
        before = len(m["usage"])
        pipeline.run(self.proj, prompt, "light", run_id="t1")       # resume: 모델 무호출
        self.assertEqual(before, len(json.loads((self.proj / "research/runs/t1/manifest.json").read_text())["usage"]))
        self.assertTrue(vault.search(self.proj, "강화학습"))


class FullTests(Base):
    def test_full_tier_run(self):
        prompt = "JS 게임 기반 강화학습의 장단점은?"
        out = pipeline.run(self.proj, prompt, "full", urls_file=str(self.urls), run_id="f1", no_search=True)
        text = out.read_text(encoding="utf-8")
        self.assertIn("종합 결론", text)                                # 초안 3개 → 종합
        self.assertIn("한계: 출처 수가 적습니다", text)                  # 다듬기 적용(모의 → 제거)
        run = self.proj / "research/runs/f1"
        self.assertEqual(3, len(list((run / "drafts").glob("draft_*.md"))))
        self.assertTrue((run / "interim/L1.md").exists())
        m = json.loads((run / "manifest.json").read_text())
        names = [s["name"] for s in m["steps"]]
        for n in ("depth", "draft", "critics", "polish", "final"):
            self.assertIn(n, names)
        steps = {u["step"] for u in m["usage"]}
        self.assertTrue({"loci", "investigator_L1", "draft_1", "draft_2", "draft_3", "synth", "critic_width", "polish"} <= steps)


class DietTests(Base):
    """토큰 다이어트: 비평·수정 단계에는 발췌본만, 종합에는 노트 원문이 없어야 한다. 예산 상한이 멈춤을 만든다."""

    def test_step_inputs_are_narrowed(self):
        seen = {}
        original = pipeline.run_step

        def recording(name, prompt, schema, inputs, role_cfg, codex_cfg, log_dir, mock=None, web_search=False, **kw):
            seen[name] = sorted(inputs)
            return original(name, prompt, schema, inputs, role_cfg, codex_cfg, log_dir, mock=mock, web_search=web_search, **kw)
        pipeline.run_step = recording
        try:
            pipeline.run(self.proj, "질문", "full", urls_file=str(self.urls), run_id="d1", no_search=True, quiet=True)
        finally:
            pipeline.run_step = original
        self.assertTrue(any(k.endswith("-note.md") for k in seen["analyst"]))               # 분석가: 노트 원문
        self.assertFalse(any(k.endswith("-note.md") for k in seen["critic_dialectic"]))     # 비평가: 발췌만
        self.assertTrue(any(k.endswith("-excerpt.md") for k in seen["critic_dialectic"]))
        self.assertIn("_digest.md", seen["critic_dialectic"])
        self.assertFalse(any(k.endswith("-note.md") for k in seen["synth"]))                # 종합: 노트 원문 없음
        self.assertTrue(any(k.startswith("drafts/") for k in seen["synth"]))
        self.assertEqual(["report.md"], seen["polish"])                                     # 다듬기: 보고서만
        run = self.proj / "research/runs/d1"
        self.assertTrue((run / "relevant.json").exists() and (run / "state.json").exists())
        text = (run / "final_report.md").read_text(encoding="utf-8")
        self.assertIn("| 인용됨 |", text)

    def test_budget_stops_before_next_step(self):
        with self.assertRaises(pipeline.Blocked) as ctx:
            pipeline.run(self.proj, "질문", "light", urls_file=str(self.urls), run_id="b1", no_search=True, quiet=True, budget=1)
        self.assertIn("예산", str(ctx.exception))
        m = json.loads((self.proj / "research/runs/b1/manifest.json").read_text())
        self.assertEqual(1, len(m["usage"]))       # 분석가 1회 뒤 상한 초과 → 초안 전에 멈춤
        state = json.loads((self.proj / "research/runs/b1/state.json").read_text())
        self.assertEqual("budget_stop", state["status"])
        # 예산을 올려 resume 하면 이어서 끝난다
        out = pipeline.run(self.proj, "질문", "light", run_id="b1", quiet=True, budget=10_000_000)
        self.assertTrue(out.exists())

    def test_domain_skew_and_truncation_flags(self):
        (self.proj / "research/config.json").parent.mkdir(exist_ok=True)
        (self.proj / "research/config.json").write_text(json.dumps({"note_max_chars": 300, "domain_skew_warn": 0.5}))
        pipeline.run(self.proj, "질문", "light", urls_file=str(self.urls), run_id="s1", no_search=True, quiet=True)
        src = json.loads((self.proj / "research/runs/s1/sources.json").read_text())
        self.assertTrue(any(w.startswith("domain_skew:127.0.0.1") for w in src["warnings"]))
        r = pipeline.Run(self.proj, "질문", "light", "s1", quiet=True); r.load_sources()
        self.assertIn("truncated: true", next(iter(r.notes().values())))


class LangAndBudgetTests(Base):
    def test_english_run_sections_and_judgment_skip(self):
        out = pipeline.run(self.proj, "What does the fixture say?", "light", urls_file=str(self.urls), run_id="en1", no_search=True, quiet=True, lang="en")
        text = out.read_text(encoding="utf-8")
        for section in ("# Question: What does the fixture say?", "## Answer", "## Evidence", "## Counter-evidence and limits", "## Sources", "## Source details (auto-generated)"):
            self.assertIn(section, text)
        m = json.loads((self.proj / "research/runs/en1/manifest.json").read_text())
        self.assertEqual("en", m["lang"])
        samples = json.loads((self.proj / "research/runs/en1/citecheck.json").read_text())["checks"]
        self.assertFalse(any("(judgment)" in c["sentence"] for c in samples))   # 판단 문장은 검사 표본에서 제외
        self.assertIn("linting", "linting")  # placeholder to keep structure simple

    def test_ledger_records_every_call_and_preset_lean(self):
        from hprc import ledger
        pipeline.run(self.proj, "질문", "full", urls_file=str(self.urls), run_id="p1", no_search=True, quiet=True, preset="lean")
        m = json.loads((self.proj / "research/runs/p1/manifest.json").read_text())
        self.assertEqual("lean", m["preset"])
        steps = [u["step"] for u in m["usage"]]
        self.assertEqual(2, sum(1 for s in steps if s.startswith("draft_")))     # lean: 초안 2개
        self.assertNotIn("critic_width", steps)                                    # lean: 비평 3종
        rows = ledger.rows(self.proj)
        self.assertEqual(len(m["usage"]), len([r for r in rows if r["run_id"] == "p1"]))
        summary = ledger.summarize(self.proj, 1, include_mock=True)
        self.assertEqual(summary["by_run"]["p1"]["calls"], len(m["usage"]))
        self.assertEqual(0, ledger.summarize(self.proj, 1)["total"]["calls"])    # 기본 요약은 mock 제외
        self.assertEqual(3_500_000, pipeline.Run(self.proj, "질문", "full", "p1", quiet=True).cfg["budget"]["max_input_tokens"])  # tier 기본 예산


class PartTests(unittest.TestCase):
    def test_patch_gate_rejects_rewrite(self):
        draft = "가나다라마바사. " * 20
        with self.assertRaises(gates.GateError):
            gates.apply_hunks(draft, [{"find": "가나다라마바사. " * 15, "replace": "전부 새로 씀", "finding_ids": []}], 0.3, 5000)

    def test_lint_accepts_alias_section(self):
        problems = gates.report_lint("# 질문: q\n## 답\nx [S1]\n## 근거\n## 반대 근거와 한계\n## 출처\n", "q", {"S1"})
        self.assertNotIn("section_missing:## 한계", problems)

    def test_published_date_priority(self):
        html = '<html><head><meta property="article:published_time" content="2026-09-01T09:00:00Z"><script type="application/ld+json">{"datePublished":"2020-01-01"}</script></head><body><p>x</p></body></html>'
        _, _, meta = fetch.html_to_text(html)
        self.assertEqual("2026-09-01", meta["published"])
        _, _, meta = fetch.html_to_text('<html><head><script type="application/ld+json">{"@graph":[{"datePublished":"2025-02-03"}]}</script></head><body><time datetime="2024-01-01">t</time></body></html>')
        self.assertEqual("2025-02-03", meta["published"])

    def test_cluster_by_text_and_canonical(self):
        srcs = [{"id": "S1", "canonical": ""}, {"id": "S2", "canonical": ""}, {"id": "S3", "canonical": "https://x/a"}, {"id": "S4", "canonical": "https://x/a"}]
        same = " ".join(f"w{i}" for i in range(100))
        assign = cluster.cluster(srcs, {"S1": same, "S2": same, "S3": "완전히 다른 글 " * 30, "S4": "또 다른 글 " * 30}, 0.6)
        self.assertEqual(assign["S2"], "S1"); self.assertEqual(assign["S4"], "S3"); self.assertNotEqual(assign["S1"], assign["S3"])

    def test_prioritize_official_first_and_dedupe(self):
        rows = [{"url": "https://blog.x/a"}, {"url": "https://github.com/o/r/tree/main", "official": True},
                {"url": "https://github.com/o/r"}, {"url": "https://developers.openai.com/codex"}]
        out = search.prioritize(rows, ["developers.openai.com"])
        self.assertEqual("https://github.com/o/r/tree/main", out[0]["url"])
        self.assertEqual(3, len(out))
        self.assertEqual("https://developers.openai.com/codex", out[1]["url"])

    def test_citecheck_skips_judgment_sentences(self):
        text = "이게 낫다. (판단) [S1] 사실 문장이다. [S2]"
        pieces = [x.strip() for x in __import__("re").split(r"(?<=[.!?。\]])\s+(?!\[S)|\n", text)]
        kept = [x for x in pieces if "[S" in x and "(판단)" not in x]
        self.assertEqual(["사실 문장이다. [S2]"], kept)

    def test_text_select_keeps_relevant_paragraphs(self):
        from hprc import text_select
        body = "\n\n".join(["도입 문단입니다. 이 문서는 ComfyUI 설치 안내입니다."] +
                            [f"관계없는 문단 {i} " + "잡담 " * 60 for i in range(20)] +
                            ["FLUX schnell 은 4단계로 생성하며 메모리 12GB 가 필요하다. " * 3] +
                            [f"또 관계없는 문단 {i} " + "잡담 " * 60 for i in range(20)])
        text, truncated = text_select.select(body, "FLUX schnell 메모리 단계", 1500)
        self.assertTrue(truncated); self.assertIn("도입 문단", text); self.assertIn("FLUX schnell", text)
        self.assertNotIn("관계없는 문단 3 ", text); self.assertLessEqual(len(text), 1900)
        same, cut = text_select.select("짧다", "q", 100)
        self.assertEqual(("짧다", False), (same, cut))
        # 한국어 질의로 영어 노트를 고를 때: 조사가 붙은 영문 낱말(Google은)도 겹치고, 겹침이 없어도 빈 노트를 주지 않는다
        eng = "\n\n".join(["# Intro to structured data", "Skip to main content", "Sign in", "Deutsch", "Español"] +
                            [f"Unrelated paragraph {i} " + "filler " * 40 for i in range(12)] +
                            ["Google uses structured data to understand the content of the page and to enable rich results. " * 2] +
                            [f"More unrelated {i} " + "filler " * 40 for i in range(12)])
        text, truncated = text_select.select(eng, "Google은 구조화 데이터를 이해하고 리치결과를 표시하는 데 활용합니다.", 2000)
        self.assertTrue(truncated); self.assertIn("rich results", text); self.assertNotIn("Unrelated paragraph", text)
        text2, _ = text_select.select(eng, "전혀 겹치지 않는 한국어 질의", 2000)
        self.assertGreater(len(text2), 1000); self.assertNotIn("\n\nSign in\n", text2)
        self.assertIn("google", text_select.terms("Google은 JSON-LD를"))

    def test_internal_cites_cleaned_and_judgment_preserved(self):
        text = "A claim. [_digest.md, C4; interim/L1.md; S6] Another. [S2; interim/L2.md] None. [_digest.md; _independence.md] Fine. [S1]"
        out, fixed = gates.clean_internal_cites(text, "en")
        self.assertEqual(3, fixed)
        self.assertEqual("A claim. [S6] Another. [S2] None. (no source) Fine. [S1]", out)
        with self.assertRaises(gates.GateError):
            # 다듬기가 판단 표시를 지우면 거부되어야 한다 (파이프라인 게이트와 같은 판정)
            before, after = "x (judgment) [S1]", "x [S1]"
            if gates.judgment_sentences(after, "en") < gates.judgment_sentences(before, "en"):
                raise gates.GateError("removed")
        self.assertEqual("https://arxiv.org/abs/2305.06360", search.normalize_url("https://arxiv.org/pdf/2305.06360"))
        self.assertEqual("https://arxiv.org/abs/2305.06360v2", search.normalize_url("https://arxiv.org/pdf/2305.06360v2.pdf"))
        self.assertEqual("https://example.com/a.pdf", search.normalize_url("https://example.com/a.pdf"))
        # Google 문서: 중국 미러·언어 매개변수는 같은 문서의 번역본이라 원본으로 돌린다 (tp-light-ko-1b 에서 독일어 페이지가 잡힘)
        self.assertEqual("https://developers.google.com/search/docs/appearance/structured-data/article",
                         search.normalize_url("https://developers.google.cn/search/docs/appearance/structured-data/article?hl=de"))
        self.assertEqual("https://developers.google.com/x?a=1", search.normalize_url("https://developers.google.com/x?hl=ko&a=1"))
        self.assertEqual("https://blog.example.com/p?hl=de", search.normalize_url("https://blog.example.com/p?hl=de"))

    def test_citecheck_notes_selected_per_source(self):
        # 출처마다 그 출처를 인용한 문장으로 문단을 골라야 한다. 모든 문장을 한 질의로 쓰면 S2 의 근거 문단이 밀려난다.
        from hprc import text_select
        filler = "\n\n".join(f"관계없는 문단 {i} " + "잡담 " * 60 for i in range(30))
        s2 = "도입.\n\n" + filler + "\n\nGooglebot 은 JSON-LD 를 읽어 리치결과 자격을 판단한다. " * 3 + "\n\n" + filler
        joint = "FLUX schnell 메모리 단계 GGUF 양자화 " * 5 + "\nGooglebot 리치결과"
        text_joint, _ = text_select.select(s2, joint, 1500)
        text_own, _ = text_select.select(s2, "Googlebot 은 JSON-LD 를 읽어 리치결과 자격을 판단한다.", 1500)
        self.assertIn("Googlebot", text_own)
        self.assertGreaterEqual(text_own.count("Googlebot"), text_joint.count("Googlebot"))

    def test_usage_limit_detection(self):
        ok, when = codex_runner.detect_usage_limit("Error: You have hit your usage limit. Try again at 9:00 AM PT.")
        self.assertTrue(ok); self.assertIn("9:00", when)
        ok, when = codex_runner.detect_usage_limit("stream error: 429 Too Many Requests; resets in 3 hours")
        self.assertTrue(ok); self.assertIn("3", when)
        self.assertEqual((False, ""), codex_runner.detect_usage_limit("schema validation failed"))

    def test_estimate_cost(self):
        usage = [{"usage": {"input_tokens": 1_000_000, "cached_input_tokens": 500_000, "output_tokens": 10_000}}]
        c = pipeline.estimate_cost(usage, {"price_input_per_m": 10, "price_output_per_m": 50, "price_cached_per_m": None})
        self.assertEqual(10.5, c["usd_upper"])
        c = pipeline.estimate_cost(usage, {"price_input_per_m": 10, "price_output_per_m": 50, "price_cached_per_m": 1})
        self.assertEqual(6.0, c["usd_upper"])

    def test_usage_parse_and_cmd(self):
        with tempfile.TemporaryDirectory() as d:
            ev = Path(d) / "e.jsonl"
            ev.write_text('{"type":"item.completed","item":{"type":"web_search"}}\n{"type":"turn.completed","usage":{"input_tokens":100,"output_tokens":5}}\n')
            parsed = codex_runner.parse_events(ev)
            self.assertEqual(100, parsed["usage"]["input_tokens"]); self.assertEqual({"web_search": 1}, parsed["items"])
        cmd = codex_runner.build_cmd(Path("/w"), Path("/w/s.json"), Path("/w/o.txt"), {"model": "m", "effort": "low"},
                                     {"ignore_user_config": True, "extra_args": ["--ephemeral"]}, web_search=True)
        self.assertEqual(["codex", "--search", "exec"], cmd[:3]); self.assertIn("--ignore-user-config", cmd); self.assertIn("-s", cmd)

    def test_write_inputs_creates_subdirs_and_blocks_escape(self):
        with tempfile.TemporaryDirectory() as d:
            work = Path(d)
            codex_runner.write_inputs(work, {"question.txt": "q", "interim/L1.md": "x", "drafts/draft_1.md": "y"})
            self.assertTrue((work / "interim/L1.md").exists() and (work / "drafts/draft_1.md").exists())
            with self.assertRaises(codex_runner.CodexError):
                codex_runner.write_inputs(work, {"../escape.md": "z"})

    def test_mcp_server_handshake(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d); shutil.copytree(ROOT / "hprc", proj / "hprc"); shutil.copy(ROOT / "hpr.py", proj / "hpr.py")
            notes = proj / "research/notes"; notes.mkdir(parents=True)
            (notes / "S1-x.md").write_text('---\nid: "S1"\ntitle: "테스트 노트"\nurl: "https://e/x"\n---\n\n본문 강화학습 내용\n', encoding="utf-8")
            msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}},
                    {"jsonrpc": "2.0", "method": "notifications/initialized"},
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                    {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "search_notes", "arguments": {"query": "강화학습"}}},
                    {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "read_note", "arguments": {"path": "/etc/passwd"}}}]
            proc = subprocess.run([sys.executable, str(proj / "hpr.py"), "mcp"], input="\n".join(json.dumps(m) for m in msgs) + "\n",
                                  capture_output=True, text=True, timeout=30)
            out = [json.loads(l) for l in proc.stdout.splitlines() if l.strip()]
            self.assertEqual([1, 2, 3, 4], [o["id"] for o in out])
            self.assertEqual("hyperresearch-codex", out[0]["result"]["serverInfo"]["name"])
            self.assertEqual(6, len(out[1]["result"]["tools"]))
            self.assertIn("S1", out[2]["result"]["content"][0]["text"])
            self.assertIn("밖 경로", out[3]["result"]["content"][0]["text"])


class DoctorMockRunTests(unittest.TestCase):
    def test_run_codex_command_passes_timeout(self):
        with mock.patch("hprc.cli.subprocess.run") as run:
            cp = subprocess.CompletedProcess(["codex", "--version"], 0, stdout="codex 0.153.4")
            run.return_value = cp
            cli._run_codex_command(["codex", "--version"])
        run.assert_called_once_with(["codex", "--version"], capture_output=True, text=True, timeout=cli.CODEX_DOCTOR_TIMEOUT)

    def test_login_status_anchor_unauthenticated(self):
        self.assertFalse(cli._login_status("Error: Unauthenticated", 0)[0])
        self.assertTrue(cli._login_status("You are logged in as test", 0)[0])

    def test_doctor_login_nonzero_returncode(self):
        version = subprocess.CompletedProcess(["codex", "--version"], 0, stdout="codex 0.153.4")
        login = subprocess.CompletedProcess(["codex", "login", "status"], 1, stdout="Not logged in", stderr="")
        with mock.patch("hprc.cli.shutil.which", return_value="/usr/bin/codex"), \
                mock.patch("hprc.cli._run_codex_command", side_effect=[version, login]), \
                mock.patch("sys.stdout", new=io.StringIO()) as out:
            rc = cli.doctor()
        self.assertEqual(1, rc)
        self.assertIn("로그인: 종료코드 1", out.getvalue())

    def test_doctor_login_empty_output(self):
        version = subprocess.CompletedProcess(["codex", "--version"], 0, stdout="codex 0.153.4")
        login = subprocess.CompletedProcess(["codex", "login", "status"], 0, stdout="", stderr="")
        with mock.patch("hprc.cli.shutil.which", return_value="/usr/bin/codex"), \
                mock.patch("hprc.cli._run_codex_command", side_effect=[version, login]), \
                mock.patch("sys.stdout", new=io.StringIO()) as out:
            rc = cli.doctor()
        self.assertEqual(1, rc)
        self.assertIn("로그인: 출력 없음", out.getvalue())

    def test_doctor_login_timeout(self):
        version = subprocess.CompletedProcess(["codex", "--version"], 0, stdout="codex 0.153.4")
        with mock.patch("hprc.cli.shutil.which", return_value="/usr/bin/codex"), \
                mock.patch("hprc.cli._run_codex_command", side_effect=[version, subprocess.TimeoutExpired(["codex", "login", "status"], 1)]), \
                mock.patch("sys.stdout", new=io.StringIO()) as out:
            rc = cli.doctor()
        self.assertEqual(1, rc)
        self.assertIn("로그인: codex login status 호출 타임아웃", out.getvalue())

    def test_doctor_login_oserror(self):
        version = subprocess.CompletedProcess(["codex", "--version"], 0, stdout="codex 0.153.4")
        with mock.patch("hprc.cli.shutil.which", return_value="/usr/bin/codex"), \
                mock.patch("hprc.cli._run_codex_command", side_effect=[version, OSError("missing")]), \
                mock.patch("sys.stdout", new=io.StringIO()) as out:
            rc = cli.doctor()
        self.assertEqual(1, rc)
        self.assertIn("로그인: codex login status 실행 오류", out.getvalue())


class DoctorTests(unittest.TestCase):
    def _mock_subprocess(self, responses):
        calls = []

        def _run(cmd, *args, **kwargs):
            calls.append(cmd)
            self.assertTrue(len(calls) <= len(responses), f"예상보다 많은 subprocess 호출: {cmd}")
            out = responses[len(calls) - 1]
            if "timeout" in out:
                raise subprocess.TimeoutExpired(cmd, out["timeout"])
            return subprocess.CompletedProcess(cmd, out.get("returncode", 0), out.get("stdout", ""), out.get("stderr", ""))

        return _run, calls

    def _run_doctor(self, responses):
        from hprc import cli
        old_root = cli.ROOT
        fake_run, calls = self._mock_subprocess(responses)
        try:
            cli.ROOT = Path(self.tmp) if hasattr(self, "tmp") else Path.cwd()
            with (
                mock.patch("hprc.cli.shutil.which", return_value="/usr/bin/codex"),
                mock.patch("subprocess.run", side_effect=fake_run),
                contextlib.redirect_stdout(buf := io.StringIO())
            ):
                result = cli.doctor()
        finally:
            cli.ROOT = old_root
        return result, buf.getvalue(), calls

    def test_doctor_reported_ok_when_tested_version_matches(self):
        out, text, calls = self._run_doctor([
            {"returncode": 0, "stdout": "codex 0.153.4\n"},
            {"returncode": 0, "stdout": "Logged in as user@example.com\n"}
        ])
        self.assertEqual(0, out)
        self.assertIn("테스트 기준 버전 0.153.4과 일치", text)
        self.assertIn("로그인됨 - Logged in as user@example.com", text)
        self.assertEqual(2, len(calls))

    def test_doctor_warns_when_version_differs(self):
        out, text, calls = self._run_doctor([
            {"returncode": 0, "stdout": "codex 0.154.0-alpha.6.2\n"},
            {"returncode": 0, "stdout": "Logged in as user@example.com\n"}
        ])
        self.assertEqual(0, out)
        self.assertIn("경고: 테스트 기준 버전(0.153.4)과 다름", text)
        self.assertEqual(2, len(calls))

    def test_doctor_fails_when_version_output_empty(self):
        out, text, calls = self._run_doctor([
            {"returncode": 0, "stdout": ""},
            {"returncode": 0, "stdout": "Logged in as user@example.com\n"}
        ])
        self.assertEqual(1, out)
        self.assertIn("버전 문자열", text)
        self.assertEqual(2, len(calls))

    def test_doctor_fails_when_version_command_times_out(self):
        out, text, calls = self._run_doctor([
            {"timeout": 3},
            {"returncode": 0, "stdout": "Logged in as user@example.com\n"}
        ])
        self.assertEqual(1, out)
        self.assertIn("codex --version 호출 타임아웃", text)
        self.assertEqual(2, len(calls))

    def test_doctor_fails_when_version_command_fails(self):
        out, text, calls = self._run_doctor([
            {"returncode": 2, "stderr": "permission denied"},
            {"returncode": 0, "stdout": "Logged in as user@example.com\n"}
        ])
        self.assertEqual(1, out)
        self.assertIn("codex --version 종료코드", text)
        self.assertEqual(2, len(calls))

    def test_doctor_fails_when_login_not_confirmed(self):
        out, text, calls = self._run_doctor([
            {"returncode": 0, "stdout": "0.153.4"},
            {"returncode": 0, "stdout": "You are not logged in. Run `codex login`"}
        ])
        self.assertEqual(1, out)
        self.assertIn("로그인 필요", text)
        self.assertEqual(2, len(calls))



if __name__ == "__main__":
    unittest.main()


FAKE_CODEX = """#!/bin/sh
# 테스트용 가짜 codex: FAKE_CODEX_MODE 파일의 한 단어로 동작을 고른다. -o 뒤 경로에 마지막 답을 쓴다.
mode=$(cat "$FAKE_CODEX_MODE")
out=""; prev=""
for a in "$@"; do if [ "$prev" = "-o" ]; then out="$a"; fi; prev="$a"; done
case "$mode" in
  limit)   echo "Error: You've hit your usage limit. Try again at 9:00 AM PT." >&2; exit 1;;
  auth)    echo "Error: Not logged in. Run \\`codex login\\` first." >&2; exit 1;;
  garbage) echo "이건 JSON 이 아니다" > "$out"; exit 0;;
  slow)    sleep 5; echo '{}' > "$out"; exit 0;;
  ok)      echo '{"ok": true}' > "$out"; echo '{"type":"turn.completed","usage":{"input_tokens":10,"cached_input_tokens":4,"output_tokens":1}}'; exit 0;;
esac
"""


class FailurePathTests(Base):
    """계획 8: 로그인 만료·네트워크 차단·잘못된 URL·codex 없음·시간 초과가 traceback 이 아니라 읽을 수 있는 BLOCKED 로 끝나야 한다."""

    def _state(self, rid):
        return json.loads((self.proj / "research/runs" / rid / "state.json").read_text())

    def test_network_down_blocks_readably(self):
        self.server.stop()                                     # 모든 URL 이 연결 거부
        with self.assertRaises(pipeline.Blocked) as ctx:
            pipeline.run(self.proj, "질문", "light", urls_file=str(self.urls), run_id="n1", no_search=True, quiet=True)
        self.assertIn("출처가 0개", str(ctx.exception))
        src = json.loads((self.proj / "research/runs/n1/sources.json").read_text())
        self.assertEqual(4, len(src["skipped"])); self.assertTrue(all(x["skipped"].startswith("fetch_failed:") for x in src["skipped"]))
        self.assertEqual("blocked", self._state("n1")["status"])

    def test_bad_urls_are_skipped_not_fatal(self):
        bad = ["not a url", "htp://bad.example/x", "http://127.0.0.1:9/closed", "https://[::1"]
        good = [f"http://127.0.0.1:{self.server.port}/p{i}.html" for i in range(3)]
        self.urls.write_text("\n".join(bad + good) + "\n")
        out = pipeline.run(self.proj, "질문", "light", urls_file=str(self.urls), run_id="u1", no_search=True, quiet=True)
        self.assertTrue(out.exists())
        src = json.loads((self.proj / "research/runs/u1/sources.json").read_text())
        skipped = {x["url"]: x["skipped"] for x in src["skipped"]}
        for u in bad:
            self.assertTrue(skipped[u].startswith("fetch_failed:"), (u, skipped.get(u)))
        self.assertGreaterEqual(len(src["sources"]), 2)

    def test_missing_urls_file_and_unknown_resume(self):
        with self.assertRaises(pipeline.Blocked) as ctx:
            pipeline.run(self.proj, "질문", "light", urls_file=str(self.tmp / "없음.txt"), run_id="m1", no_search=True, quiet=True)
        self.assertIn("URL 파일 없음", str(ctx.exception)); self.assertEqual("blocked", self._state("m1")["status"])
        from hprc import cli
        old_root, old_argv = cli.ROOT, sys.argv
        try:
            cli.ROOT, sys.argv = self.proj, ["hpr", "resume", "nope-42"]
            self.assertEqual(2, cli.main())                    # traceback 없이 종료코드 2
        finally:
            cli.ROOT, sys.argv = old_root, old_argv

    def test_search_providers_all_fail(self):
        (self.proj / "research").mkdir(exist_ok=True)
        (self.proj / "research/config.json").write_text(json.dumps({"search": {"providers": ["duckduckgo"]}}))
        original = pipeline.searchmod.duckduckgo
        pipeline.searchmod.duckduckgo = lambda *a, **k: [{"error": "search_failed:ConnectError"}]
        try:
            with self.assertRaises(pipeline.Blocked) as ctx:
                pipeline.run(self.proj, "질문", "light", run_id="s0", quiet=True)
        finally:
            pipeline.searchmod.duckduckgo = original
        self.assertIn("검색 결과도 URL 목록도 없음", str(ctx.exception)); self.assertEqual("blocked", self._state("s0")["status"])

    def test_usage_limit_mid_run_then_resume(self):
        original, calls = pipeline.run_step, []
        def limited(name, *a, **kw):
            calls.append(name)
            if name == "writer":
                raise codex_runner.UsageLimit("writer: 사용량 한도 도달 (리셋 9:00 AM)", "9:00 AM")
            return original(name, *a, **kw)
        pipeline.run_step = limited
        try:
            with self.assertRaises(pipeline.HardStop) as ctx:
                pipeline.run(self.proj, "질문", "light", urls_file=str(self.urls), run_id="l1", no_search=True, quiet=True)
        finally:
            pipeline.run_step = original
        self.assertIn("hpr resume l1", str(ctx.exception))
        st = self._state("l1"); self.assertEqual(("usage_limit", "9:00 AM", "writer"), (st["status"], st["resets_at"], st["step"]))
        self.assertEqual(1, calls.count("writer"))             # 한도에서는 재시도하지 않는다
        out = pipeline.run(self.proj, "질문", "light", run_id="l1", quiet=True)   # 리셋 뒤 resume: 분석가는 건너뛰고 초안부터
        self.assertTrue(out.exists())
        self.assertEqual(1, sum(1 for u in json.loads((self.proj / "research/runs/l1/manifest.json").read_text())["usage"] if u["step"] == "analyst"))

    def test_auth_error_stops_without_retry_even_in_scout(self):
        (self.proj / "research").mkdir(exist_ok=True)
        (self.proj / "research/config.json").write_text(json.dumps({"search": {"providers": ["codex_scout", "duckduckgo"]}}))
        original, calls = pipeline.run_step, []
        def unauthorized(name, *a, **kw):
            calls.append(name); raise codex_runner.AuthRequired(f"{name}: 로그인이 만료됐거나 인증 실패. `codex login` 뒤 `hpr resume`")
        pipeline.run_step = unauthorized
        try:
            with self.assertRaises(pipeline.HardStop) as ctx:
                pipeline.run(self.proj, "질문", "light", urls_file=str(self.urls), run_id="a1", quiet=True)
        finally:
            pipeline.run_step = original
        self.assertIn("codex login", str(ctx.exception))
        self.assertEqual(["scout"], calls)                     # 정찰에서 바로 멈춤: 덕덕고로 넘어가 분석가까지 가지 않는다
        self.assertEqual("auth_required", self._state("a1")["status"])

    def test_real_subprocess_path_with_fake_codex(self):
        """HPR_BACKEND 를 비우고 가짜 codex 실행 파일로 진짜 subprocess 경로를 지나 본다(토큰 0)."""
        bindir = self.tmp / "bin"; bindir.mkdir()
        (bindir / "codex").write_text(FAKE_CODEX); (bindir / "codex").chmod(0o755)
        mode = self.tmp / "mode"; logs = self.tmp / "logs"
        env = {"HPR_BACKEND": "codex", "PATH": f"{bindir}:{os.environ['PATH']}", "FAKE_CODEX_MODE": str(mode)}
        role, cfg = {"model": "m", "effort": "low"}, {"timeout": 1, "ignore_user_config": True, "extra_args": []}
        saved = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            mode.write_text("ok")
            result, usage = codex_runner.run_step("t", "p", {"type": "object"}, {"a.md": "x"}, role, cfg, logs)
            self.assertEqual(({"ok": True}, 10, 4), (result, usage["usage"]["input_tokens"], usage["usage"]["cached_input_tokens"]))
            mode.write_text("limit")
            with self.assertRaises(codex_runner.UsageLimit) as ctx:
                codex_runner.run_step("t", "p", {}, {}, role, cfg, logs)
            self.assertEqual("9:00 AM PT", ctx.exception.resets_at)
            mode.write_text("auth")
            with self.assertRaises(codex_runner.AuthRequired):
                codex_runner.run_step("t", "p", {}, {}, role, cfg, logs)
            mode.write_text("garbage")
            with self.assertRaises(codex_runner.CodexError) as ctx:
                codex_runner.run_step("t", "p", {}, {}, role, cfg, logs)
            self.assertIn("JSON", str(ctx.exception)); self.assertNotIsInstance(ctx.exception, (codex_runner.UsageLimit, codex_runner.AuthRequired))
            mode.write_text("slow")
            started = __import__("time").time()
            with self.assertRaises(codex_runner.CodexError) as ctx:
                codex_runner.run_step("t", "p", {}, {}, role, cfg, logs)
            self.assertIn("시간 초과", str(ctx.exception)); self.assertLess(__import__("time").time() - started, 4)   # 기다리지 않고 죽임
            os.environ["PATH"] = str(self.tmp / "empty-bin")
            with self.assertRaises(codex_runner.CodexMissing):
                codex_runner.run_step("t", "p", {}, {}, role, cfg, logs)
        finally:
            for k, v in saved.items():
                if v is None: os.environ.pop(k, None)
                else: os.environ[k] = v
