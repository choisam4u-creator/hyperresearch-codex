# Release guide

Only a maintainer publishes a release. Use a clean `main` checkout and keep `research/` and `docs/internal/` out of the commit and artifacts.

## Prepare

1. Update `pyproject.toml`, `CITATION.cff`, README status badges and `CHANGELOG.md` to the same version and date.
2. Run the full mock suite and compile check.
3. Build both distributions in a temporary environment, run `twine check`, inspect the wheel, and install it outside the checkout. Confirm `hpr --help`, `hpr demo` and the mock wheel smoke test.
4. Review the complete diff and wait for required GitHub checks on the exact commit.

## GitHub release

Create an annotated `vX.Y.Z` tag on the verified commit. Build artifacts from that tag, attach the wheel and source archive to the GitHub release, and use the matching changelog section as release notes. Read back the tag target, release URL and asset checksums.

## PyPI Trusted Publishing

The workflow is `.github/workflows/release.yml`, repository owner is `choisam4u-creator`, repository is `hyperresearch-codex`, and the GitHub environment is `pypi`. Configure those exact values as a PyPI pending or existing-project Trusted Publisher before dispatching the workflow. Configure the GitHub environment with a required maintainer reviewer, prevent self-review when another maintainer is available, and limit deployments to tags matching `v*`.

Dispatch the workflow with an existing, published GitHub release tag. It checks out that tag without persisted credentials, verifies `vX.Y.Z` against package metadata and the GitHub release, runs the full mock suite, and builds and checks artifacts in a job without OIDC permission. Its publish job only downloads the artifact and invokes `pypa/gh-action-pypi-publish`; `id-token: write` is limited to that job. No API token is stored.

After publishing, verify the PyPI page, version, file hashes, project links and a clean-environment `pip install hyperresearch-codex`. PyPI files and versions are immutable; a bad upload requires a new version rather than replacement.
