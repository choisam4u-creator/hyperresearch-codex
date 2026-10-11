베타: 자동 품질 검사가 review_required(종료 코드 3) 경고를 낼 수 있습니다. 결과를 사람이 검토하세요.

# hyperresearch-codex

`hyperresearch-codex` turns one research question into a sourced, adversarially reviewed brief. Python controls the pipeline, Codex model calls run in a read-only sandbox, and deterministic gates check citations and bounded edits.

## Safe first run

```bash
pip install hyperresearch-codex
hpr demo
```

`hpr demo` is local and synthetic: it does not require a Codex login, access the network, or use model tokens.

Before real research, log in to the [Codex CLI](https://developers.openai.com/codex/cli/) and inspect the plan:

```bash
hpr doctor
hpr run "your question" --dry-run
hpr run "your question"
```

Real runs consume the configured Codex allowance. Input-token thresholds can stop before a later call, but an in-flight call can exceed them and they are not billing caps.

Full documentation, measured cost boundaries, examples, security notes and contribution instructions are in the [GitHub repository](https://github.com/choisam4u-creator/hyperresearch-codex).

- [English README](https://github.com/choisam4u-creator/hyperresearch-codex/blob/main/README.md)
- [한국어 README](https://github.com/choisam4u-creator/hyperresearch-codex/blob/main/README.ko.md)
- [Security policy](https://github.com/choisam4u-creator/hyperresearch-codex/blob/main/SECURITY.md)
- [Changelog](https://github.com/choisam4u-creator/hyperresearch-codex/blob/main/CHANGELOG.md)

MIT licensed. Inspired by `jordan-gibbs/hyperresearch`; this is an independent implementation and shares no code or prompts with it.
