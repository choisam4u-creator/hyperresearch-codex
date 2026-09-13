You write one draft of the report from the angle "{angle}". The current folder holds question.txt, claims.json, _digest.md, interim/*.md (depth investigations), _independence.md and the source notes S*.md.
Format (Markdown, English, about {target_words} words): first line "# Question: " + question.txt verbatim / "## Answer" / "## Evidence" (every sentence cited like [S3]) / "## Counter-evidence and limits" / "## Next actions" / "## Sources" (ids and titles only).
Rules:
- Append "(judgment)" only to recommendation / priority / ordering sentences that the sources do not state themselves. Never on factual, source-description or limitation sentences. At most 8 in the whole draft.
- The angle changes emphasis, never facts. Sources in the same cluster (_independence.md) count as one piece of evidence and must be described that way. Sentences without a source get "(no source)".
Read every file in one command (e.g. `cat *.md *.json`). Return exactly one JSON object matching _schema.json (field `markdown`).
Cite only [S#]. Never cite _digest.md, interim/*.md or claim ids (C3) inside brackets.
Put "(judgment)" at the end of the sentence on the same line (never on its own line).
