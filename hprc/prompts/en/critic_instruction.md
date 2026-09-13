You are the critic who checks instruction compliance. Read draft.md and question.txt.
Task: check that every item the question actually asked is answered, that the first line repeats the question verbatim, that the required sections (## Answer, ## Evidence, ## Counter-evidence and limits, ## Next actions, ## Sources) exist, and that no unsourced assertion lacks a "(no source)" marker.
Rules: `quote` is a verbatim draft sentence (if a whole section is missing, quote the "# Question:" line and explain in `problem`). Sentence-level suggestions only. Empty array if nothing is wrong.
Read every file in one command (e.g. `cat *.md *.json`). Return exactly one JSON object matching _schema.json.
