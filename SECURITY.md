# Security policy

## Supported versions

Security fixes are made on the current `0.5.x` release line and `main`. Older releases may receive documentation updates, but users should upgrade before reporting a runtime issue.

## Reporting a vulnerability

Use the repository's **Security → Report a vulnerability** private advisory flow. Include the affected version or commit, a minimal reproduction, impact and any known workaround. Do not open a public issue for credentials, sandbox escapes, arbitrary file access, prompt-injection paths that cross a deterministic gate, or package-publishing compromise.

The maintainer will acknowledge a complete report when it is reviewed, keep discussion in the private advisory, and coordinate a fix and disclosure. There is no paid bounty program.

## Security properties and limits

- Every model call uses `codex exec -s read-only` in a temporary directory containing only that step's inputs. Python owns file writes and applies bounded find/replace hunks.
- `--ignore-user-config` is enabled by default, so pipeline calls do not load `~/.codex/config.toml`, skills or hooks. Authentication still comes from `CODEX_HOME`.
- Fetched pages are untrusted text. Prompts label them as data; gates reject unknown citations and oversized edits. These controls reduce risk but cannot prove that generated prose is safe or true. Review reports before acting on them.
- The MCP server exposes read-only tools and rejects paths outside `research/`.
- Expected network access is limited to enabled search providers, candidate URL fetches, optional arXiv/OpenAlex APIs, and Codex web search during the scout step.
- Releases use GitHub OIDC Trusted Publishing, so no long-lived PyPI token belongs in repository secrets.

See [the threat model](docs/THREAT-MODEL.md) for trust boundaries and [the release guide](docs/RELEASE.md) for publishing controls.
