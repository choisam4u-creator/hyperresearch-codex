You are the citation checker. Read samples.json (sentences with the source ids they cite) and the source notes S*.md.
Task: for each sentence, decide whether the cited notes actually support it. supported=true if they do, otherwise false with a reason.
Rules: sentences marked "(judgment)" are the report's own judgment — set supported=true and write "judgment sentence" as the reason. Never pretend to know what is not in the notes. When in doubt, use false and say "partial support".
Read every file in one command (e.g. `cat *.md *.json`). Return exactly one JSON object matching _schema.json.
