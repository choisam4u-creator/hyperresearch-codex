# Threat model

## Assets

The pipeline must protect local files outside the selected workspace, Codex credentials, the integrity of saved source notes and reports, usage budgets, and the package release channel.

## Trust boundaries

| Boundary | Untrusted input | Control | Remaining limit |
|---|---|---|---|
| Web → fetcher/vault | HTML, metadata, redirects and encodings | URL policy, bounded downloads, immutable note snapshots | A permitted page can still contain misleading or hostile prose |
| Vault → model | Source text and prior artifacts | Step-specific temporary directory, read-only sandbox, explicit data instructions | Prompt injection cannot be ruled out by instructions alone |
| Model → report | Structured findings, drafts and edit hunks | JSON schemas, known-source checks, quote checks, edit-size caps, citation sampling | Gates test defined properties, not universal truth or reasoning quality |
| CLI → filesystem | Run IDs, paths and resume state | Canonical run-path validation, workspace boundary, locks and atomic writes | A user who grants the process broader OS access keeps that authority |
| CI → PyPI | Release artifacts and workflow identity | Dedicated workflow, GitHub environment, OIDC short-lived credential | A malicious maintainer change to the trusted workflow can compromise publishing |

## Attacker goals considered

- Read or overwrite files outside the research workspace.
- Turn fetched text into an instruction that bypasses report gates.
- Forge a citation, source identity, usage record or completed step.
- Exhaust usage through retries, duplicate work or unsafe resume behavior.
- Publish modified artifacts under the project name.

## Maintainer checks

CI runs mock failure paths, path and source validation, package-isolation checks and CodeQL. Releases are built from a published tag, checked against package metadata and GitHub release state, tested, checked with `twine check`, attached to GitHub, and published through a `pypi` environment configured with reviewer and tag restrictions. Dependency and workflow updates arrive through Dependabot.

Security controls do not establish factual accuracy, general report quality, model compatibility or a hard billing cap. Those remain separate evaluation and user-review responsibilities.
