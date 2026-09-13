# Security notes

- Every model call runs `codex exec -s read-only` inside a throwaway temp directory that contains only the step's input files. Models never write files; Python applies bounded find/replace hunks.
- `--ignore-user-config` is on by default, so your `~/.codex/config.toml`, skills and hooks are not loaded into pipeline calls. Auth is still read from `CODEX_HOME`.
- Fetched pages are untrusted text. Prompts tell the model to treat them as data; gates reject citations to unknown sources and edits above a size cap. This does not make prompt injection impossible — review reports before acting on them.
- The MCP server exposes read-only tools and refuses paths outside `research/`.
- No network calls are made except: DuckDuckGo HTML search, arXiv/OpenAlex APIs (opt-in), fetching candidate URLs, and Codex's own web search when the scout step runs.

Report issues privately via GitHub security advisories.
