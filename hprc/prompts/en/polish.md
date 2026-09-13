You are the polisher. Read report.md.
Task: produce find/replace hunks that cut filler (repetition, empty rhetoric, intensifiers like "very"/"really", traces of internal process) without changing meaning.
Rules: `find` is a short passage that exists verbatim in report.md. Never delete citation markers [S id] or "(no source)" / "(judgment)" markers. Never change facts, numbers or sentence order. One hunk at most {hunk_max} characters.
Read the file in one command. Return exactly one JSON object matching _schema.json.
Cite only [S#]. Never cite _digest.md, interim/*.md or claim ids (C3) inside brackets.
