# v0.5.0 release notes (draft)

v0.5.0 prepares five reliability and support improvements found during local dogfooding.

## User-visible changes

- Ranked search candidates are interleaved by hostname, reducing early source-set concentration without changing the ranking score.
- Numbers inside an explicit “not verified/measured” disclosure no longer create a misleading factual-number warning. Unsupported quantitative claims still do.
- After a bounded patch, aliases cited in the report body are added to the human-readable Sources section when matching source metadata exists.
- `hpr status` distinguishes `passed`, `review_required`, `missing`, and `malformed` quality records.
- The feedback guide and GitHub issue form explain how to report a `review_required` result without sharing private prompts or report text.

## Evidence boundary

The changes are covered by deterministic mock and unit tests. They do not establish a general improvement in factual accuracy, report quality, or token consumption, and v0.5.0 adds no new live research run.

## Release checklist

- [ ] Full test suite and bytecode compilation pass.
- [ ] Source and wheel artifacts contain no `research/`, `docs/internal/`, or `docs/open-source-intake/` paths.
- [ ] Built wheel installs in an isolated environment and `hpr demo` succeeds.
- [ ] GitHub Actions and CodeQL pass for the release commit.
- [ ] Maintainer creates and verifies the tag, GitHub release, and PyPI publication.
