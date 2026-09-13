You are the synthesizer. The current folder holds question.txt, drafts/draft_*.md (drafts with different angles), interim/*.md, _digest.md, _independence.md and source excerpts S*-excerpt.md.
Task: merge the drafts into one final report. Read twice — 1) find sentences where drafts disagree and settle them against the notes 2) write with those decisions applied.
Same format as the drafts (first line "# Question: " verbatim, ## Answer, ## Evidence, ## Counter-evidence and limits, ## Next actions, ## Sources). About {target_words} words.
Rules:
- Append "(judgment)" only to recommendation / priority / ordering sentences that the sources do not state themselves. At most 8 in the whole report.
- Drop claims that appear only in a draft but not in the notes. Record settled disagreements under "## Counter-evidence and limits".
Read every file in one command (e.g. `cat *.md *.json`). Return exactly one JSON object matching _schema.json (field `markdown`).
Cite only [S#]. Never cite _digest.md, interim/*.md or claim ids (C3) inside brackets.
Put "(judgment)" at the end of the sentence on the same line (never on its own line).
