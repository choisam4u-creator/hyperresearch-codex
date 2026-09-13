# Changelog

## 0.3.1 - 2026-09-13
- Cite-check reads each cited note selected by the sentences that cite *that* source, not by all sample sentences at once (a Korean-vs-English mismatch left a 93-char note and produced false "unsupported" verdicts in the variance run). Verified with one more real run of the same question: unsupported 4/5 → 1/5, the English Google notes now reach the checker at 4–6k chars.
- Paragraph selection tokenizes Latin and Hangul runs separately ("Google은" now matches "Google") and, when nothing overlaps, fills the cap in document order instead of returning only the title.
- URL normalization maps developers.google.cn to developers.google.com and drops `hl=` on Google docs (a German translation had been fetched as a source).
- Test plan results for the four Light lean runs recorded in docs/TEST-PLAN.md.
- Failure paths are readable stops, not tracebacks: login expired → `state.json` `auth_required` with a `codex login` hint; codex binary missing → `codex_missing`; usage limit, auth and missing binary no longer retry or fall through to the next search provider (`HardStop`); a missing `--urls` file, an unknown `resume` id, and malformed URLs (`https://[::1`) are skipped or reported instead of crashing; a step that fails twice records `failed`.
- Timeout is enforced with the remaining time, not in 30-second heartbeat steps.
- Examples and a picture: `examples/report-en-light-lean.md` and `examples/report-ko-light-lean.md` are unedited real reports; `scripts/render-log-svg.py` turns a run log into the animated terminal SVG shown in the README (no external tools).
- Packaging for GitHub: author `samchoi`, project URLs, issue/PR templates, CI installs the package and runs the 28 mock tests on Python 3.11–3.13, comparison table and credits in both READMEs.
- 7 failure-path tests (network down, bad URLs, missing file, all search providers failing, usage limit mid-run then resume, auth error in scout, and a fake `codex` executable exercising the real subprocess path for ok/limit/auth/garbage/timeout/missing).

## 0.3.0 - 2026-09-13
- Token diet: per-step inputs. Analyst sees all notes; drafts see only sources the analyst actually cited; critics/patcher see a claims digest + 2,500-char excerpts; synthesis sees drafts + interim + digest only; cite-check sees only the cited notes; polish sees the report only.
- Live progress on stderr (`[hpr HH:MM:SS] step …`), per-run `state.json` (current step, pid, running cost) and `--quiet`.
- `--budget N` stops before the next step once cumulative input tokens exceed N; `resume --budget` continues. `status` shows an upper-bound USD estimate (configurable prices).
- `--dry-run` prints steps, expected calls and rough cost without running.
- Accuracy: truncated notes are flagged to the model; recommendation sentences are marked "(판단)" and skipped by cite-check; scout is told to stay on-topic and capped at N searches; Last-Modified header as a published-date fallback (marked with *); domain-skew warning when one domain exceeds 60 % of sources; provenance table shows which sources were actually cited.
- Prompts ask the model to read all files in one command (fewer turns → fewer re-sent tokens).
- Heartbeat every 30 s during a model call (elapsed, tool usage) and `[k/N]` step tags; final header line printed at the end.
- Relevance-based note selection (`hprc/text_select.py`): when a note exceeds its cap, keep the intro plus the paragraphs most related to the question/draft/findings instead of the head.
- `pip install .` installs the `hpr` command (CLI moved into `hprc/cli.py`; `hpr.py` is a thin wrapper); `HPR_HOME` selects the workspace; `hpr doctor` shows Codex login state.
- English README is now the default (`README.md`), Korean in `README.ko.md`; 60-second start, live-output sample, how-it-works diagram, troubleshooting table.
- `--lang ko|en`: full English prompt set (14 files) with language-aware sections, markers and lint; the language is fixed in the run manifest.
- `--preset lean` for subscription accounts (2 critics, 2 drafts, smaller caps); per-tier default budgets (light 1.2 M, full 3.5 M input tokens).
- Usage ledger `research/usage-ledger.jsonl` (every call) with `hpr usage` (per day / per run) and `--backfill` for older runs.
- Usage-limit detection: a Codex call that fails with a usage/rate-limit message stops the run without burning the retry, writes `state.json` (`usage_limit`, reset hint) and tells you how to resume; `run`/`resume --at 'HH:MM'` waits for the reset. `scripts/run-test-plan.sh` runs the pre-release test plan with lean presets and budgets.
- `install-skill --yes` copies the Codex skill; mock backend now reports approximate tokens so budget logic is testable (15 tests).

## 0.2.0 - 2026-09-13
- Full tier: depth loci → parallel investigators → 3 angle drafts → synthesis → 4 critics → patch → cite-check → polish.
- Codex scout search (`codex --search`), DuckDuckGo query variants, arXiv/OpenAlex (`--scholar`).
- Published-date and canonical-URL extraction; source independence clustering; provenance table in final report.
- Token accounting from `--json` events; `--ignore-user-config` default (measured 119,520 → 18,781 input tokens per call).
- Read-only vault MCP server (stdio, 6 tools).

## 0.1.0 - 2026-09-13
- Light tier MVP: search → fetch → analyst → writer → 3 critics → patch → cite-check → lint. Mock backend tests.
