# Contributing

- Run tests without spending Codex usage: `HPR_BACKEND=mock python3 -m unittest tests/test_pipeline_mock.py`.
- Keep the three rules: Python orchestrates; models only read (read-only sandbox, JSON schema); every model output passes a gate.
- Prompts live in `hprc/prompts/*.md`. If you tune them for a model, say which model and show a before/after run header line.
- Do not commit anything under `research/` (fetched third-party page text, run logs).
- Korean and English are both welcome in issues and PRs.
