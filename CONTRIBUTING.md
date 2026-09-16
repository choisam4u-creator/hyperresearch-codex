# Contributing

Korean and English issues and pull requests are welcome. Start with a small, reproducible change and state whether it affects orchestration, prompts, deterministic gates, packaging, or documentation.

## Local setup

```bash
git clone https://github.com/choisam4u-creator/hyperresearch-codex
cd hyperresearch-codex
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
hpr demo
```

`hpr demo` is the safe first check: it uses a synthetic local fixture and makes no model or network calls.

## Verification

Run the complete mock suite before opening a pull request:

```bash
HPR_BACKEND=mock python -m unittest discover -s tests -p 'test*.py' -v
python -m compileall -q hprc hpr.py
python -m pip wheel --no-deps . --wheel-dir dist
```

Add focused regression coverage for behavior changes. Do not spend Codex usage solely to satisfy a pull request. If a change depends on a real-model comparison, describe the fixed input, model, configuration, stopping rule, measured usage and limitations; keep token savings and quality preservation as separate claims.

## Project invariants

- Python owns ordering, retries, writes and resume state. Model calls stay read-only and schema-bound.
- Every model output passes deterministic gates before it changes a report.
- Prompts live in both `hprc/prompts/ko/` and `hprc/prompts/en/`. Prompt changes should identify the tested model and show scoped before/after evidence.
- Never commit `research/`; it can contain fetched third-party text, run logs and local usage records.
- Keep private credentials, Codex configuration and personal vault data out of tests and fixtures.

## Pull requests

Explain the trigger, the behavior before and after, the validation run, and any remaining limit. CI runs Linux Python 3.11–3.13, Windows Python 3.12, wheel isolation checks and CodeQL. A maintainer creates releases; contributors should not change version metadata unless the change is explicitly a release preparation.

Documentation screenshots must come from real logs. Generate them with:

```bash
python3 scripts/render-log-svg.py research/logs/<run>.log docs/assets/<name>.svg
```

Add `--static` for a still image.
