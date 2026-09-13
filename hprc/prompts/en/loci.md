You plan the investigation. Read question.txt, claims.json, _independence.md and the source excerpts S*-excerpt.md.
Task: choose at most {loci_max} **loci** — points that must be investigated in depth so the report is not shallow. Each locus has a one-sentence question, why the current notes are not enough, and the related note ids.
Rules: do not pick points the notes already answer well. No invented sources.
Read every file in one command (e.g. `cat *.md *.json`). Return exactly one JSON object matching _schema.json.
