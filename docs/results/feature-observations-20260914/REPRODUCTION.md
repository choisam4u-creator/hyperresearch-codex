# Offline reproduction

These probes record mock observations, not model, API, web, token, cost, latency, or quality measurements. Run them only from a checkout of this repository.

```sh
HPR_BACKEND=mock python3 docs/results/feature-observations-20260914/run_offline_probe.py
HPR_BACKEND=mock python3 docs/results/feature-observations-20260914/full_route_probe.py
```

The scripts find the repository by locating `hpr.py`; no local private path is required. They overwrite only the JSON observation file beside each script and use temporary workspaces for pipeline output. `phase4-preflight.mock.json` is retained evidence from a mock-only private harness; this capsule does not include that harness because it was not a standalone public reproduction script.

`offline-observations.json` records prepared byte counts, mock call paths, exact-key cache behavior, and replay update branches. `full-route-observations.json` records mock route steps. Neither file supports a claim about real Codex token use, cost, elapsed time, factual accuracy, or quality.

Parallel draft/critic completion order may differ between replays; compare call counts and step membership separately from sequence. A private-copy replay of both scripts matched all recorded fields after sorting only `steps`/`critic_steps`; no real model calls were used. To preserve the published observation files, copy the two scripts into a new ignored folder under this checkout (for example, `docs/internal/feature-reproduction/`) and run those copies instead.

The retained observations and the matching private-copy check used research code `53e6b790c79048edd782240e20374fc27cb6fec2`. Copy these probes into an ignored folder of a clean checkout at that revision to compare the original code hashes. A replay on later code is a new observation and may have different code/configuration hashes and behavior; do not overwrite the retained JSON and call it the original result.
